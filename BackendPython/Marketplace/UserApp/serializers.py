import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.files.storage import default_storage
from rest_framework import serializers

from ProfessionalUser.models import *
from UserApp.models import *


class CaseInsensitiveChoiceField(serializers.ChoiceField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            for key, label in self.choices.items():
                if data.lower() == str(key).lower():
                    return key
            self.fail("invalid_choice", input=data)
        return super().to_internal_value(data)
    
class AddressSerializer(serializers.ModelSerializer):
    """Serializer for Address model"""
    class Meta:
        model = Address
        fields = ['user','address1', 'address2', 'postalCode', 'city', 'country', 'lat', 'lang']


from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist


def safe_url(path):
    if path and not path.startswith("http"):
        return f"https://markerplacemobileapp.s3.us-east-1.amazonaws.com{path}"
    return path


class AdminProUserSerializer(serializers.ModelSerializer):
    manualAddress = AddressSerializer(required=False)
    automatic_address = AddressSerializer(required=False)
    categories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Category.objects.all(), write_only=True, required=False
    )
    subcategories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Subcategory.objects.all(), write_only=True, required=False
    )
    multipleCountry = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Country.objects.all(), write_only=True, required=False
    )
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), write_only=True, required=False
    )
    categories_display = serializers.SerializerMethodField(read_only=True)
    subcategories_display = serializers.SerializerMethodField(read_only=True)
    multipleCountry_display = serializers.SerializerMethodField(read_only=True)
    role_display = serializers.SerializerMethodField(read_only=True)

    password = serializers.CharField(write_only=True)
    confirmPassword = serializers.CharField(write_only=True)



    class Meta:
        model = Users
        fields = [
            'id', 'username', 'email', 'is_active', 'phone', 'password', 'confirmPassword',
            'firstName', 'lastName', 'countryCode', 'dob', 'gender', 'manualAddress',
            'automatic_address', 'identityCardImage', 'profileImage', 'language',
            'categories', 'subcategories', 'multipleCountry', 'role',
            'categories_display', 'subcategories_display', 'multipleCountry_display', 'role_display',
            'termCondition', 'created_by_user', 'created_by_user_id', 'marketingReference'
        ]
        extra_kwargs = {'password': {'write_only': True}}
        

    def get_categories_display(self, obj):
        return [{"id": cat.id, "name": cat.name} for cat in obj.categories.all()]

    def get_subcategories_display(self, obj):
        return [{"id": sub.id, "name": sub.name} for sub in obj.subcategories.all()]

    def get_multipleCountry_display(self, obj):
        return [{"id": c.id, "name": c.name} for c in obj.multipleCountry.all()]

    def get_role_display(self, obj):
        if obj.role:
            return {"id": obj.role.id, "name": obj.role.name}
        return None
    
    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirmPassword'):
            raise serializers.ValidationError({"confirmPassword": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        manual_address_data = self.context.get("manual_address_data")
        automatic_address_data = self.context.get("automatic_address_data")

        categories_data = validated_data.pop('categories', [])
        subcategories_data = validated_data.pop('subcategories', [])
        multiple_countries_data = validated_data.pop('multipleCountry', [])

        validated_data.pop('confirmPassword', None)
        validated_data['password'] = make_password(validated_data['password'])
        validated_data['is_active'] = True 

        if not manual_address_data and not automatic_address_data:
            raise serializers.ValidationError("User must have at least one address.")

        user = Users.objects.create(**validated_data)
        if manual_address_data:
            manual_address = Address.objects.create(**manual_address_data, user=user)
            user.manualAddress = manual_address

        if automatic_address_data:
            automatic_address = Address.objects.create(**automatic_address_data, user=user)
            user.automatic_address = automatic_address
        if categories_data:
            user.categories.set(categories_data)
        if subcategories_data:
            user.subcategories.set(subcategories_data)
        if multiple_countries_data:
            user.multipleCountry.set(multiple_countries_data)

        user.save()
        return user
    
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if "categories_display" in rep:
            rep["categories"] = rep.pop("categories_display")
        if "subcategories_display" in rep:
            rep["subcategories"] = rep.pop("subcategories_display")
        if "multipleCountry_display" in rep:
            rep["multipleCountry"] = rep.pop("multipleCountry_display")
        if "role_display" in rep:
            rep["role"] = rep.pop("role_display")
        if rep.get("identityCardImage"):
            rep["identityCardImage"] = safe_url(rep["identityCardImage"])
        if rep.get("profileImage"):
            rep["profileImage"] = safe_url(rep["profileImage"])
        rep.pop("confirmPassword", None)
        rep.pop("password", None)

        return rep



import jwt


class UserSerializer(serializers.ModelSerializer):
    manualAddress = AddressSerializer(required=False)
    automatic_address = AddressSerializer(required=False)
    
    multipleCountry = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True)
    categories = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True)
    confirmPassword = serializers.CharField(write_only=True)

    class Meta:
        model = Users
        fields = [
            'id', 'username', 'email','is_active', 'phone', 'password', 'confirmPassword', 'firstName', 'lastName',
            'countryCode', 'dob', 'gender', 'manualAddress', 'automatic_address',
            'identityCardImage', 'profileImage', 'language', 'categories',
            'subcategories', 'multipleCountry', 'termCondition','created_by_user','created_by_user_id', 'marketingReference'
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def validate(self, attrs):
        if attrs.get('password') != attrs.get('confirmPassword'):
            raise serializers.ValidationError({"confirmPassword": "Passwords do not match."})
        
        return attrs

    def get_categories(self, obj):
        return list(obj.categories.values_list("id", flat=True))

    def create(self, validated_data):
        validated_data.pop('confirmPassword')
        manual_address_data = self.context.get("manual_address_data")
        automatic_address_data = self.context.get("automatic_address_data")
        
        categories_data = validated_data.pop('categories', [])
        multiple_countries_data = validated_data.pop('multipleCountry', [])
        subcategories_data = validated_data.pop('subcategories', [])

        validated_data['password'] = make_password(validated_data['password'])
        validated_data['is_active'] = True 

        if not manual_address_data and not automatic_address_data:
            raise serializers.ValidationError("User must have at least one address.")
        

        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                token = request.headers.get('Authorization').split()[1]
                decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                role = decoded_token.get('role', 'null')  # Fallback to "user" if role is not present
                validated_data['created_by_user'] = role
                validated_data['created_by_user_id'] = request.user.id
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                raise serializers.ValidationError("Invalid or expired token.")
            except ObjectDoesNotExist:
                raise serializers.ValidationError("Authenticated user role not found.")
        user = Users.objects.create(**validated_data)
        if manual_address_data:
            manual_address = Address.objects.create(**manual_address_data, user=user)
            user.manualAddress = manual_address

        if automatic_address_data:
            automatic_address = Address.objects.create(**automatic_address_data, user=user)
            user.automatic_address = automatic_address
        
        

        if categories_data:
            user.categories.set(Category.objects.filter(id__in=categories_data))
        if subcategories_data:
            user.subcategories.set(Subcategory.objects.filter(id__in=subcategories_data))
        if multiple_countries_data:
            user.multipleCountry.set(Country.objects.filter(id__in=multiple_countries_data))
        user.save() 
        return user
class UserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = "__all__"


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = Users
        fields = '__all__'
        
    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])  # Hash password before saving
        return super().create(validated_data)


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users
        fields = '__all__'



User = get_user_model()
def upload_to_s3(file, folder):
    """Upload file to S3 and return the relative file path (not full URL)."""
    file_extension = file.name.split('.')[-1]
    file_name = f"{folder}/{uuid.uuid4()}.{file_extension}"
    file_path = default_storage.save(file_name, file)  
    return file_path
class UserRegistrationSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Category.objects.all(), required=False
    )
    subcategories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Subcategory.objects.all(), required=False
    )
    multipleCountry = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Country.objects.all(), required=False
    )
    language = serializers.PrimaryKeyRelatedField(
        queryset=Language.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Users
        fields = [
            "id", "email", "username", "password", "phone", "firstName", "lastName",
            "countryCode", "dob", "gender", "language",
            "identityCardImage", "profileImage",
            "categories", "subcategories", "multipleCountry",
            "termCondition", "marketingReference",
            "manualAddress", "automatic_address",
        ]
        read_only_fields = ["manualAddress", "automatic_address"]
        extra_kwargs = {
            "password": {"write_only": True},
        }

    def update(self, instance, validated_data):
        request = self.context.get("request")

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if request and "profileImage" in request.FILES:
            instance.profileImage = upload_to_s3(request.FILES["profileImage"], "profile_images")

        if request and "identityCardImage" in request.FILES:
            instance.identityCardImage = upload_to_s3(request.FILES["identityCardImage"], "identity_cards")

        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)

        def parse_address(address_instance):
            if not address_instance:
                return None
            return {
                "address1": address_instance.address1,
                "address2": address_instance.address2,
                "postalCode": address_instance.postalCode,
                "lat": address_instance.lat,
                "lang": address_instance.lang,
                "city": address_instance.city,
                "country": address_instance.country
            }

        data["manualAddress"] = parse_address(instance.manualAddress)
        data["automatic_address"] = parse_address(instance.automatic_address)

        if instance.profileImage:
            data["profileImage"] = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{instance.profileImage}"
        if instance.identityCardImage:
            data["identityCardImage"] = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{instance.identityCardImage}"

        data["multipleCountry"] = list(instance.multipleCountry.values("id", "name"))

        return data
class UserUpdateSerializer(serializers.ModelSerializer):
    manualAddress = AddressSerializer(required=False, allow_null=True)
    automatic_address = AddressSerializer(required=False, allow_null=True)  
    multipleCountry = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()  
    subcategories = serializers.SerializerMethodField()  

    class Meta:
        model = Users
        fields = [
            'id', 'username','is_active', 'phone', 'firstName', 'lastName', 'language',
            'identityCardImage', 'countryCode', 'dob', 'gender', 'manualAddress',
            'automatic_address', 'categories', 'subcategories', 'multipleCountry', 'profileImage'
        ]

    def get_multipleCountry(self, obj):
        """Retrieve multipleCountry as a list of country IDs."""
        return list(obj.multipleCountry.values_list("id", flat=True)) if obj.multipleCountry.exists() else []
    
    def get_categories(self, obj):
        """Retrieve categories as a list of category IDs."""
        return list(obj.categories.values_list("id", flat=True)) if obj.categories.exists() else []

    def get_subcategories(self, obj):  
        """Retrieve subcategories as a list of subcategory IDs."""  
        return list(obj.subcategories.values_list("id", flat=True)) if obj.subcategories.exists() else []

    def update(self, instance, validated_data):
        """Handle image updates properly"""
        request = self.context.get("request")
        profile_image = request.FILES.get("profileImage") if request else None
        identity_card_image = request.FILES.get("identityCardImage") if request else None

        if profile_image:
            instance.profileImage = profile_image

        if identity_card_image:
            instance.identityCardImage = identity_card_image
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance

    
    def to_representation(self, instance):
        """Ensure full image URLs are returned"""
        data = super().to_representation(instance)

        if instance.profileImage:
            data["profileImage"] = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{instance.profileImage}"
        if instance.identityCardImage:
            data["identityCardImage"] = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{instance.identityCardImage}"

        return data



class UpdatePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate_old_password(self, value):
        """Check if the old password is correct."""
        user = self.context["request"].user
        if not check_password(value, user.password):  
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate(self, data):
        """Ensure new_password and confirm_password match and prevent reusing old password."""
        user = self.context["request"].user
        if data["new_password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "New password and confirm password do not match."})
        if check_password(data["new_password"], user.password):
            raise serializers.ValidationError({"new_password": "New password cannot be the same as the old password."})

        return data

    def update(self, instance, validated_data):
        """Update the password securely."""
        instance.password = make_password(validated_data["new_password"])  # Hash the password before saving
        instance.save()
        return instance

class StoreImagessSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source='company_id.companyName', read_only=True)

    class Meta:
        model = StoreImage
        fields = ['id', 'company_id', 'company_name', 'category', 'subcategory', 'title', 'image', 'created_at']

class StoreReelSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreReel
        fields = ["id", "title", "video", "thumbnail", "m3u8_url", "views", "likes", "shares", "comments", "created_at","isActive","category"]

class StoreEventSerializer(serializers.ModelSerializer):
   
    startDate = serializers.DateField(format="%a %d %B %Y")  # e.g., 'Wed 05 March 2025'
    startTime = serializers.TimeField(format="%I:%M %p")     # e.g., '12:00 AM'
    endDate = serializers.DateField(format="%a %d %B %Y")    # e.g., 'Wed 05 March 2025'
    endTime = serializers.TimeField(format="%I:%M %p")  

    class Meta:
        model = StoreEvent
        fields = ["id","eventTitle","eventImage","startDate","startTime","description","endDate","endTime","eventAddress"]


class TicketsConcertSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketsConcert
        fields = ['id', 'name', 'description', 'members', 'quantity', 'price']
        
class NightClubTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = NightClubTicket
        fields = ['id', 'tableName', 'description', 'members', 'quantity', 'price']

class ProductcreateSerializer(serializers.ModelSerializer):
    
    
    endTime = serializers.TimeField(
        format="%I:%M %p",
        input_formats=["%I:%M %p", "%H:%M", "%H:%M:%S"], required=False
    )

    startTime = serializers.TimeField(
        format="%I:%M %p",
        input_formats=["%I:%M %p", "%H:%M", "%H:%M:%S"], required=False
    )
    promotionalPrice = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    cruiseFacility = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CruiseFacility.objects.all(),
        required=False,
        allow_null=True
    )
    roomFacility = serializers.PrimaryKeyRelatedField(queryset=RoomFacility.objects.all(), many=True)
    
    class Meta:
        model = Product
        fields = '__all__'

    def get_startAddress(self, obj):
        """ Fetch start address details if available """
        if obj.startAddress:
            return {
                "address1": obj.startAddress.address1,
                "address2": obj.startAddress.address2,
                "postalCode": obj.startAddress.postalCode,
                "lat": obj.startAddress.lat,
                "lang": obj.startAddress.lang,
                "city": obj.startAddress.city,
                "country": obj.startAddress.country,
            }
        return None

    def get_endAddress(self, obj):
        """ Fetch end address details if available """
        if obj.endAddress:
            return {
                "address1": obj.endAddress.address1,
                "address2": obj.endAddress.address2,
                "postalCode": obj.endAddress.postalCode,
                "lat": obj.endAddress.lat,
                "lang": obj.endAddress.lang,
                "city": obj.endAddress.city,
                "country": obj.endAddress.country,
            }
        return None    
    
    def validate(self, attrs):
        price = attrs.get('priceOnsite')
        attrs['isActive'] = True 
        attrs['onDelivery'] = True 
        attrs['onsite'] = True 
        attrs['clickandCollect'] = True 
        discount = attrs.get('discount', 0)

        if price is not None and discount is not None:
            attrs['promotionalPrice'] = price - (price * discount / 100)

        return attrs
    
        
    



class ProductdetailsSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Product
        fields = '__all__'
    
    def get_startAddress(self, obj):
        """ Fetch start address details if available """
        if obj.startAddress:
            return {
                "address1": obj.startAddress.address1,
                "address2": obj.startAddress.address2,
                "postalCode": obj.startAddress.postalCode,
                "lat": obj.startAddress.lat,
                "lang": obj.startAddress.lang,
                "city": obj.startAddress.city,
                "country": obj.startAddress.country,
            }
        return None

    def get_endAddress(self, obj):
        """ Fetch end address details if available """
        if obj.endAddress:
            return {
                "address1": obj.endAddress.address1,
                "address2": obj.endAddress.address2,
                "postalCode": obj.endAddress.postalCode,
                "lat": obj.endAddress.lat,
                "lang": obj.endAddress.lang,
                "city": obj.endAddress.city,
                "country": obj.endAddress.country,
            }
        return None


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'



class CartSerializer(serializers.ModelSerializer):
    product = ProductdetailsSerializer()  # Nested serializer to include product details

    class Meta:
        model = Cart
        fields = ['id', 'product', 'quantity'] 



class CartProductSerializer(serializers.ModelSerializer):
    product = ProductdetailsSerializer()
    price = serializers.SerializerMethodField()
    category_slug = serializers.SerializerMethodField()
    subcategory_slug = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'product', 'quantity', 'order_type', 'price','category_slug',
            'subcategory_slug']

    def get_price(self, obj):
        price_map = {
            'Onsite': obj.product.promotionalPrice,
            'Click and Collect': obj.product.priceClickAndCollect,
            'Delivery': obj.product.priceDelivery
        }
        return float(price_map.get(obj.order_type, 0) or 0)
    
    def get_category_slug(self, obj):
        return obj.product.categoryId.slug if obj.product and obj.product.categoryId else None

    def get_subcategory_slug(self, obj):
        return obj.product.subCategoryId.slug if obj.product and obj.product.subCategoryId else None


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'title', 'description', 'media', 'submitted_at']


class SupportOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportOption
        fields = ['id', 'title']


class CustomerSupportSerializer(serializers.ModelSerializer):
    support_option_name = serializers.CharField(source='support_option.title', read_only=True)

    class Meta:
        model = CustomerSupport
        fields = [
            'id', 'user', 'title', 'description', 'support_id',
            'support_option', 'support_option_name', 'image', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'user', 'support_id', 'support_option_name']




class UserAddressSerializer(serializers.ModelSerializer):
    address_type_icon = serializers.SerializerMethodField()
    address_type = serializers.SerializerMethodField()  # override this field to capitalize it

    class Meta:
        model = userAddress
        fields = '__all__'

    def get_address_type_icon(self, obj):
        address_type = obj.address_type.lower() if obj.address_type else ''
        icon_map = {
            'home': 'home',
            'work': 'briefcase',
        }
        return icon_map.get(address_type, None)

    def get_address_type(self, obj):
        return obj.address_type.capitalize() if obj.address_type else ''
    
            
class PrivacySettingSerializer(serializers.ModelSerializer):
    class Meta:

        activity_visibility = CaseInsensitiveChoiceField(choices=PrivacySetting.PRIVACY_CHOICES)
        identify_visibility = CaseInsensitiveChoiceField(choices=PrivacySetting.PRIVACY_CHOICES)
        id_visibility = CaseInsensitiveChoiceField(choices=PrivacySetting.PRIVACY_CHOICES)
        push_notification_status = CaseInsensitiveChoiceField(choices=PrivacySetting.PUSH_NOTIFICATION_CHOICES)

        model = PrivacySetting
        fields = '__all__'
        read_only_fields = ['user']        

class LoyaltyCardSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    company_name = serializers.CharField()
    profile_photo = serializers.CharField()
    total_points = serializers.IntegerField()





class OrderDetailSerializer(serializers.ModelSerializer):
    cart_items = CartSerializer(many=True)
    company = serializers.StringRelatedField()
    professional_user = serializers.StringRelatedField()
    user = serializers.StringRelatedField()
    promo_code = serializers.StringRelatedField()
    address = serializers.StringRelatedField()

    class Meta:
        model = Order
        fields = '__all__'



class OrderTrackingSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.companyName", read_only=True)
    profile_photo = serializers.SerializerMethodField()
    order_status_label = serializers.SerializerMethodField()
    last_updated = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "order_id", "orderStatus", "order_status_label", "order_type", "total_price",
            "company_name", "profile_photo", "last_updated"
        ]

    def get_profile_photo(self, obj):
        request = self.context.get('request')
        if obj.company and obj.company.profilePhoto:
            return request.build_absolute_uri(obj.company.profilePhoto.url)
        return None

    def get_order_status_label(self, obj):
        return dict(Order.STATUS_CHOICES).get(obj.orderStatus, obj.orderStatus)

    def get_last_updated(self, obj):
        return obj.updated_at.strftime("%d %B %Y, %I:%M %p")  
    

class RoomBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomBooking
        fields = '__all__'



class OrderCancelSerializer(serializers.Serializer):
    cancel_reasons = serializers.ChoiceField(choices=Order.CANCEL_REASONS)

    def validate(self, data):
        """
        Validate that the order is cancellable and belongs to the requesting user.
        """
        order = self.context.get('order')
        if not order:
            raise serializers.ValidationError("Order not found.")
        if order.orderStatus not in ["new order", "processing"]:
            raise serializers.ValidationError("Order cannot be cancelled. It is either fulfilled, already cancelled, or not in a valid state.")

        user = self.context['request'].user
        if order.user != user:
            raise serializers.ValidationError("You are not authorized to cancel this order.")

        return data

    def update(self, instance, validated_data):
        """
        Perform the update to the order status and cancellation reason.
        """
        instance.orderStatus = "cancelled"
        instance.cancel_reasons = validated_data['cancel_reasons']
        instance.save()
        return instance



class OrderBookingFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderBookingFeedback  
        fields = '__all__'
