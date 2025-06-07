import json

import timeago
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.utils.encoders import JSONEncoder
from rest_framework_simplejwt.tokens import RefreshToken


from django.utils import timezone
from Admin.models import Category, Subcategory, Subscription
from payment.models import Payment, UserPayment
from ProfessionalUser.models import *
from ProfessionalUser.models import ReelLike, StoreReel
from ProfessionalUser.utils import *
from UserApp.serializers import UserSerializer


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["id", "address1", "address2", "postalCode", "lat", "lang", "city", "country","dialCode","countryCode"]
        ref_name = "ProfessionalUserAddress"
        
        
class CompanyDetailsSerializer(serializers.ModelSerializer):
    companyID = serializers.SerializerMethodField()
    coverPhotos = serializers.SerializerMethodField()
    on_site_ordering = serializers.SerializerMethodField()
    manual_address = AddressSerializer()
    automatic_address = AddressSerializer()
    subcategories = serializers.SerializerMethodField()
    selectedCoverPhoto = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    facilities = serializers.SerializerMethodField()
    pro_email = serializers.SerializerMethodField()
    
    class Meta:
        model = CompanyDetails
        fields = "__all__"
        read_only_fields = ['created_at', 'updated_at']
        ref_name = "CompanyDetailsUnique" 

    def get_companyID(self, obj):
        return obj.id
    
    def get_pro_email(self, obj):
        professional = ProfessionalUser.objects.filter(company=obj).first()
        return professional.email if professional else None
    
    def get_coverPhotos(self, obj):
        """Returns full URLs for cover photos"""
        if obj.coverPhotos:
            return [f"https:/{settings.MEDIA_URL}{photo}" for photo in obj.coverPhotos]
        return None
    
    def get_selectedCoverPhoto(self, obj):
        """ Returns full URL of the selected cover photo"""
        if obj.selectedCoverPhoto:
            return f"https:/{settings.MEDIA_URL}{obj.selectedCoverPhoto}"
        return None
    
    def get_on_site_ordering(self, obj):
        """ Returns full URLs for onsite ordering images"""
        if obj.on_site_ordering:
            return [f"https:/{settings.MEDIA_URL}{photo}" for photo in obj.on_site_ordering]
        return None
    
    def get_categories(self, obj):
        """ Returns categories with id & name"""
        categories = [{"id": category.id, "name": category.name, "slug": category.slug} for category in obj.categories.all()]
        return categories if categories else None

    def get_subcategories(self, obj):
        """ Returns subcategories with id & name"""
        subcategories = [{"id": subcategory.id, "name": subcategory.name, "slug": subcategory.slug} for subcategory in obj.subcategories.all()]
        return subcategories if subcategories else None
        
    def get_facilities(self, obj):
        """ Returns facilities with id, name, and icon"""
        facilities = [
            {
                "id": facility.id,
                "name": facility.name,
                "icon": f"https:/{settings.MEDIA_URL}{facility.icon}" if facility.icon else None
            }
            for facility in obj.facilities.all()
        ]
        return facilities if facilities else None


class ProfessionalUserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    companyName = serializers.CharField(write_only=True)
    managerFullName = serializers.CharField(write_only=True)
    company_email = serializers.EmailField(write_only=True, required=False, allow_null=True)
    siret = serializers.CharField(write_only=True)
    sectorofActivity = serializers.CharField(write_only=True)
    vatNumber = serializers.CharField(write_only=True)
    phoneNumber = serializers.CharField(write_only=True, required=False, allow_null=True)

    iban = serializers.FileField(write_only=True)
    kbiss = serializers.FileField(write_only=True)
    identityCardFront = serializers.FileField(write_only=True, required=False)
    identityCardBack = serializers.FileField(write_only=True, required=False)
    proofOfAddress = serializers.FileField(write_only=True)
    manual_address = serializers.CharField(write_only=True, required=False,allow_null=True)
    automatic_address = serializers.CharField(write_only=True, required=False,allow_null=True)
    class Meta:
        model = ProfessionalUser
        fields = [
            'userName', 'email', 'password', 'confirm_password', 'phone', 'phoneCode',
            'companyName', 'managerFullName', 'company_email', 'siret', 'sectorofActivity',
            'iban', 'vatNumber', 'phoneNumber', 'kbiss', 'identityCardFront', 'identityCardBack',
            'proofOfAddress', 'manual_address', 'automatic_address'
        ]
    def validate(self, data):
        """ Validate password fields """
        password = data.get('password')
        confirm_password = data.get('confirm_password')

        if password != confirm_password:
            raise serializers.ValidationError({"password": "Passwords do not match!"})

        if len(password) < 8:
            raise serializers.ValidationError({"password": "Password must be at least 8 characters long."})

        if not any(char.isupper() for char in password):
            raise serializers.ValidationError({"password": "Password must contain at least one uppercase letter."})

        return data

    def validate_manual_address(self, value):
        """ Convert JSON string to dictionary """
        try:
            return json.loads(value) if isinstance(value, str) else value
        except json.JSONDecodeError:
            raise serializers.ValidationError("Invalid JSON format for manual_address.")

    def validate_automatic_address(self, value):
        """ Convert automatic_address JSON string to dictionary """
        try:
            return json.loads(value) if isinstance(value, str) else value
        except json.JSONDecodeError:
            raise serializers.ValidationError("Invalid JSON format for automatic_address.")

    @transaction.atomic  
    def create(self, validated_data):
        """ Extract company & address data, create user properly """

        try:
            company_data = {
                "companyName": validated_data.pop('companyName'),
                "managerFullName": validated_data.pop('managerFullName'),
                "email": validated_data.pop('company_email', None),
                "siret": validated_data.pop('siret'),
                "sectorofActivity": validated_data.pop('sectorofActivity'),
                "iban": validated_data.pop('iban', None),
                "vatNumber": validated_data.pop('vatNumber'),
                "phoneNumber": validated_data.pop('phoneNumber', None),
                "kbiss": validated_data.pop('kbiss', None),
                "identityCardFront": validated_data.pop('identityCardFront', None),
                "identityCardBack": validated_data.pop('identityCardBack', None),
                "proofOfAddress": validated_data.pop('proofOfAddress', None),
            }

            manual_address_data = validated_data.pop('manual_address', {})
            automatic_address_data = validated_data.pop('automatic_address', {})

            validated_data.pop('confirm_password')  
            validated_data['password'] = make_password(validated_data['password'])

            company = CompanyDetails.objects.create(**company_data)
            manual_address = Address.objects.create(**manual_address_data) if manual_address_data else None
            automatic_address = Address.objects.create(**automatic_address_data) if automatic_address_data else None
            user = ProfessionalUser.objects.create(
                **validated_data,
                company=company,
                manual_address=manual_address,
                automatic_address=automatic_address
            )

            return user

        except IntegrityError as e:
            if "siret" in str(e):
                raise serializers.ValidationError({
                    "statusCode": 400, "status": False, "message": "This SIRET number is already registered. Please use a unique SIRET."
                })
            if "vatNumber" in str(e):
                raise serializers.ValidationError({
                    "statusCode": 400, "status": False, "message": "This VAT number is already registered. Please use a unique VAT number."
                })
            raise serializers.ValidationError({
                "statusCode": 400, "status": False, "message": str(e)
            })

        except Exception as e:
            raise serializers.ValidationError({
                "statusCode": 500, "status": False, "error": f"Failed to create ProfessionalUser: {str(e)}"
            })


class SafeJSONEncoder(JSONEncoder):
    def default(self, obj):
        try:
            return obj.decode("utf-8", "ignore")  # Ignore invalid bytes
        except (UnicodeDecodeError, AttributeError):
            return str(obj)  # Convert non-decodable data to string


class StoreReelSerializer(serializers.ModelSerializer):
    is_m3u8_generated = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    subcategory = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    shares_count = serializers.IntegerField(source="shares", read_only=True)

    class Meta:
        model = StoreReel
        fields = [
            "id", "company", "category","subcategory", "video", "thumbnail", "likes_count", 
            "shares_count", "title", "views", "likes", "shares", "comments", 
            "isActive", "is_deleted", "deleted_at", "created_at", "company_id",'is_m3u8_generated'
        ]
        read_only_fields = ["created_at", "likes", "shares", "views"]
        
    def get_is_m3u8_generated(self, obj):
        return bool(obj.m3u8_url)

    def get_likes_count(self, obj):
        """Return the total likes count for the reel"""
        return ReelLike.objects.filter(reel=obj).count()

    def get_video(self, obj):
        """Return the full S3 URL of the video file"""
        return self.get_s3_url(obj.video)

    def get_thumbnail(self, obj):
        """Return the full S3 URL of the thumbnail"""
        return self.get_s3_url(obj.thumbnail)

    def get_category(self, obj):
        """ Returns category details with id & name"""
        if obj.category:
            return {"id": obj.category.id, "name": obj.category.name}
        return None
    
    def get_subcategory(self, obj):
        """ Returns subcategory details with id & name"""
        if obj.subcategory:
            return {"id": obj.subcategory.id, "name": obj.subcategory.name}
        return None
    
    def get_company(self, obj):
        """ Returns company details with id & name"""
        if obj.company_id:
            return {"id": obj.company_id.id, "name": obj.company_id.companyName}
        return None

    def get_s3_url(self, file_obj):
        """Ensure correct URL handling for FieldFile and string paths."""
        if not file_obj:
            return None
        if hasattr(file_obj, 'name'):
            file_path = file_obj.name
        else:
            file_path = str(file_obj)
        if file_path.startswith("http://") or file_path.startswith("https://"):
            return file_path

        return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{file_path.lstrip('/')}"

 
class ReelLikeSerializer(serializers.ModelSerializer):
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = ReelLike
        fields = ['id', 'user', 'reel', 'is_liked']

    def get_is_liked(self, obj):
        return True  


class ReelViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReelView
        fields = ["id", "user", "reel", "viewed_at"]
   
    
class ReelCommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()
    is_store_reply = serializers.SerializerMethodField()

    class Meta:
        model = ReelComment
        fields = ['id', 'user', 'reel', 'comment', 'parent', 'replies', 'is_store_reply', 'created_at']

    def get_replies(self, obj):
        """Fetch nested replies with a depth limit to prevent infinite recursion."""
        max_depth = self.context.get("depth", 2)  # Default depth = 2
        if max_depth > 0:
            return ReelCommentSerializer(
                obj.replies.all().order_by("-created_at"),  # Sort replies by latest first
                many=True, 
                context={"depth": max_depth - 1}
            ).data
        return []

    def get_is_store_reply(self, obj):
        """Check if the comment is from the store owner."""
        return obj.user == getattr(obj.reel.company_id, "user", None)  # Safely get store user

  
class ReelShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReelShare
        fields = ['id', 'user', 'reel', 'recipient_user', 'share_method', 'shared_at']
        read_only_fields = ['shared_at']
    
    def validate(self, data):
        
        user = data.get("user")
        recipient_user = data.get("recipient_user")

        if user and recipient_user and user == recipient_user:
            raise serializers.ValidationError("A user cannot share a reel with themselves.")
        return data

class StoreImageSerializer(serializers.ModelSerializer):
    company = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    subcategory = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(default=False)
    
    class Meta:
        model = StoreImage
        fields = ['id','title', 'image', 'company', 'category', 'isActive','subcategory']
        read_only_fields = ['created_at']

    def get_company(self, obj):
        return {
            "id": obj.company_id.id,
            "name": obj.company_id.companyName
        } if obj.company_id else None

    def get_category(self, obj):
        return {"id": obj.category.id, "name": obj.category.name} if obj.category else None

    def get_subcategory(self, obj):
        return {"id": obj.subcategory.id, "name": obj.subcategory.name} if obj.subcategory else None

    def create(self, validated_data):
        company_id = validated_data.pop('company_id', None)
        if not company_id:
            raise serializers.ValidationError({"company_id": "Company ID is required."})

        try:
            company = CompanyDetails.objects.get(id=company_id)
        except CompanyDetails.DoesNotExist:
            raise serializers.ValidationError({"company_id": "Invalid company ID."})

        image = validated_data.pop('image', None)
        if not image:
            raise serializers.ValidationError({"image": "This field is required."})

        instance = StoreImage.objects.create(company_id=company, image=image, **validated_data)
        return instance
class UpdateProfessionalUserSerializer(serializers.ModelSerializer):
    subscriptionplan = serializers.PrimaryKeyRelatedField(
        queryset=Subscription.objects.filter(is_active=True), required=False, allow_null=True
    )
    subscriptiontype = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.filter(is_active=True), required=False, allow_null=True
    )
    subscriptionplan_name = serializers.SerializerMethodField()
    subscriptiontype_name = serializers.SerializerMethodField()

    manual_address = AddressSerializer(required=False)
    automatic_address = AddressSerializer(required=False)
    company = CompanyDetailsSerializer(required=False)
    categories = serializers.SerializerMethodField()  
    subcategories = serializers.SerializerMethodField() 

    class Meta:
        model = ProfessionalUser
        fields = [
            'phone','email', 'subscriptionplan', 'subscriptionplan_name','subscriptiontype', 'subscriptiontype_name','manual_address', 'automatic_address',
            'company', 'categories', 'subcategories',"email_notifications","sms_notifications","push_notifications",
            "two_factor_authentication", "email_two_factor", "sms_two_factor",
        ]

    def get_subscriptionplan_name(self, obj):
        return obj.subscriptionplan.name if obj.subscriptionplan else None

    def get_subscriptiontype_name(self, obj):
        return obj.subscriptiontype.subscription_type if obj.subscriptiontype else None
    def get_categories(self, obj):
        return [
            {
                "id": c.id,
                "name": c.name,
                "slug": c.slug if hasattr(c, "slug") else ""
            } for c in obj.categories.all()
        ]

        
    def update(self, instance, validated_data):
        logger.info("Starting user update")
        two_fa = validated_data.pop("two_factor_authentication", None)
        email_2fa = validated_data.pop("email_two_factor", None)
        sms_2fa = validated_data.pop("sms_two_factor", None)

        logger.debug(f"2FA input extracted -> two_fa: {two_fa}, email_2fa: {email_2fa}, sms_2fa: {sms_2fa}")
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.update_two_factor_settings(two_fa, email_2fa, sms_2fa)

        logger.info("User update complete.")
        return instance





    def get_subcategories(self, obj):
        """Retrieve subcategories as a list of subcategory details including id, name, and slug."""
        return list(obj.subcategories.values("id", "name", "slug"))
    def validate(self, data):
        """
        Validate subscriptionplan, subscriptiontype, email, username, manual address, and category limits.
        """
        request = self.context.get("request")
        user = self.instance
        if request and request.data:
            if 'email' in request.data:
                raise serializers.ValidationError({
                    "message": "Invalid request data",
                    "statusCode": 400,
                    "status": False,
                    "error": "You cannot update the email."
                })

            if 'userName' in request.data:
                raise serializers.ValidationError({
                    "message": "Invalid request data",
                    "statusCode": 400,
                    "status": False,
                    "error": "You cannot update the username."
                })
            if "manual_address" in request.data:
                try:
                    data["manual_address"] = json.loads(request.data["manual_address"])
                except json.JSONDecodeError:
                    raise serializers.ValidationError({
                        "message": "Invalid manual address format. Expected a JSON object.",
                        "statusCode": 400,
                        "status": False
                    })

        subscriptiontype_id = data.get('subscriptiontype')
        subscriptiontype_instance = None  

        if subscriptiontype_instance and subscriptiontype_instance != user.subscriptiontype:
            latest_payment = Payment.objects.filter(
                user=user,
                subscription_plan=subscriptiontype_instance.subscription,
                status="succeeded"
            ).order_by('-created_at').first()

            if not latest_payment:
                raise serializers.ValidationError({
                    "message": "You must complete the payment before updating your subscription.",
                    "statusCode": 400,
                    "status": False
                })
        category_ids = request.data.get("categories", "")
        subcategory_ids = request.data.get("subcategories", "")

        if isinstance(category_ids, str):
            category_ids = [int(id.strip()) for id in category_ids.split(",") if id.strip().isdigit()]

        if isinstance(subcategory_ids, str):
            subcategory_ids = [int(id.strip()) for id in subcategory_ids.split(",") if id.strip().isdigit()]
        if subscriptiontype_instance:
            max_categories = subscriptiontype_instance.subscription.category_limit
            max_subcategories = subscriptiontype_instance.subscription.subcategory_limit

           
        return data





    def update(self, instance, validated_data):
        instance.email_notifications=validated_data.get('email_notifications',instance.email_notifications)
        instance.sms_notifications=validated_data.get('sms_notifications',instance.sms_notifications)
        instance.push_notifications=validated_data.get('push_notifications',instance.push_notifications)
        instance.two_factor_authentication=validated_data.get('two_factor_authentication',instance.two_factor_authentication)
        instance.email_two_factor=validated_data.get('email_two_factor',instance.email_two_factor)
        instance.sms_two_factor=validated_data.get('sms_two_factor',instance.sms_two_factor)
        instance.phone = validated_data.get('phone', instance.phone)
        subscriptiontype = validated_data.get('subscriptiontype', None)
        if subscriptiontype:
            instance.subscriptiontype = subscriptiontype
            instance.subscriptionplan = subscriptiontype.subscription
        if 'manual_address' in validated_data:
            manual_data = validated_data.pop('manual_address')
            if instance.manual_address:
                for key, value in manual_data.items():
                    setattr(instance.manual_address, key, value)
                instance.manual_address.save()
            else:
                instance.manual_address = Address.objects.create(**manual_data)
        if 'automatic_address' in validated_data:
            automatic_data = validated_data.pop('automatic_address')
            if instance.automatic_address:
                for key, value in automatic_data.items():
                    setattr(instance.automatic_address, key, value)
                instance.automatic_address.save()
            else:
                instance.automatic_address = Address.objects.create(**automatic_data)
        company_instance = instance.company

        if not company_instance:
            company_instance = CompanyDetails.objects.create()
            instance.company = company_instance
        company_data = validated_data.pop('company', {})
        for key, value in company_data.items():
            setattr(company_instance, key, value)
        request = self.context.get("request")
        if request and hasattr(request, 'FILES'):
            files = request.FILES

            def update_file(field_name, file_field, status_field):
                new_file = files.get(field_name)
                if new_file:
                    setattr(company_instance, file_field, new_file)
                    current_status = getattr(instance, status_field, None)
                    if current_status == "rejected" or not current_status:
                        setattr(instance, status_field, "pending")

            update_file("kbiss", "kbiss", "kbiss_status")
            update_file("iban", "iban", "iban_status")
            update_file("proofOfAddress", "proofOfAddress", "proofOfAddress_status")
            update_file("identityCardFront", "identityCardFront", "identityCardFront_status")
            update_file("identityCardBack", "identityCardBack", "identityCardBack_status")

        company_instance.save()

        if request:
            category_ids = request.data.get("categories", "[]")
            subcategory_ids = request.data.get("subcategories", "[]")
            if isinstance(category_ids, str):
                category_ids = [int(i) for i in category_ids.split(",") if i.isdigit()]

            if isinstance(subcategory_ids, str):
                subcategory_ids = [int(i) for i in subcategory_ids.split(",") if i.isdigit()]
            if category_ids:
                categories = Category.objects.filter(id__in=category_ids)
                instance.categories.set(categories)

            if subcategory_ids:
                subcategories = Subcategory.objects.filter(id__in=subcategory_ids)
                instance.subcategories.set(subcategories)

        instance.save()
        return instance
    

class CruiseFacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = CruiseFacility
        fields = '__all__'

 
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone = serializers.CharField(required=False)

    def validate(self, data):
        email = data.get("email")
        phone = data.get("phone")

        if not email and not phone:
            raise serializers.ValidationError({"error": "Email or phone number is required."})

        user = None
        if email:
            user = ProfessionalUser.objects.filter(email=email).first()
        elif phone:
            user = ProfessionalUser.objects.filter(phone=phone).first()

        if not user:
            raise serializers.ValidationError({"error": "User not found."})

        data["user"] = user
        return data

    def save(self):
        user = self.validated_data["user"]
        otp = generate_otp()
        expiry_time = timezone.now() + timedelta(minutes=10)  # OTP valid for 10 minutes
        user.otp = otp
        user.otp_attempts = 0
        user.otp_block_until = expiry_time
        user.save()
        if user.email:
            self.send_otp_email(user.email, otp)
        if user.phone:
            self.send_otp_sms(user.phone, otp)

        return otp

    def send_otp_email(self, email, otp):
        subject = "Reset Your Password - OTP Verification"
        message = f"Your OTP for password reset is {otp}. It is valid for 10 minutes."
        send_mail(subject, message, "no-reply@example.com", [email])

    def send_otp_sms(self, phone, otp):
        message = f"Your OTP for password reset is {otp}. It is valid for 10 minutes."
        send_sms(phone, message)


class ResetPasswordSerializer(serializers.Serializer):
    otp = serializers.CharField(required=True)
    newPassword = serializers.CharField(write_only=True)

    def validate(self, data):
        otp = data.get("otp")
        new_password = data.get("newPassword")
        user = ProfessionalUser.objects.filter(otp=otp, otp_block_until__gte=timezone.now()).first()

        if not user:
            raise serializers.ValidationError({"error": "Invalid or expired OTP."})

        data["user"] = user
        return data

    def save(self):
        user = self.validated_data["user"]
        new_password = self.validated_data["newPassword"]
        user.password = make_password(new_password)
        user.otp = None  # Clear OTP after reset
        user.save()
        refresh = RefreshToken()
        refresh.payload['email'] = user.email
        refresh.payload['user_type'] = "professional_user"
        access_token = str(refresh.access_token)

        return {
            "access_token": access_token,
            "refresh_token": str(refresh),
        }






class UpdatePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        user = self.context["request"].user
        old_password = data.get("old_password")
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")

        if not check_password(old_password, user.password):
            raise serializers.ValidationError({"error": "Old password is incorrect."})

        if old_password == new_password:
            raise serializers.ValidationError({"error": "New password cannot be the same as the old password."})

        if new_password != confirm_password:
            raise serializers.ValidationError({"error": "New password and confirm password do not match."})

        return data

    def save(self):
        user = self.context["request"].user
        user.password = make_password(self.validated_data["new_password"])
        user.save()
        return user



class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "user", "product", "rating", "comment", "created_at"]
        read_only_fields = ["user", "created_at"]

import datetime


class CampaignSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = "__all__"

    def validate_name(self, value):
        user = self.context["request"].user  
        if Campaign.objects.filter(name=value, company=user.company).exists():
            raise serializers.ValidationError("A campaign with this name already exists for your company.")

        return value
class CaseInsensitiveChoiceField(serializers.ChoiceField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            for key, label in self.choices.items():
                if data.lower() == str(key).lower():
                    return key
            self.fail("invalid_choice", input=data)
        return super().to_internal_value(data)
class PromotionsSerializer(serializers.ModelSerializer):
    startDateTime = serializers.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M:%S"],
        format="%d/%m/%Y %H:%M:%S"
    )
    endDateTime = serializers.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M:%S"],
        format="%d/%m/%Y %H:%M:%S"
    )

    product_service_type = CaseInsensitiveChoiceField(choices=Promotions.PRODUCT_SERVICE_CHOICES)
    
    productId = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        many=True 
    )

    class Meta:
        model = Promotions
        fields = '__all__'

    



class PromocodeSerializer(serializers.ModelSerializer):
    startDateTime = serializers.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M:%S"],
        format="%d/%m/%Y %H:%M:%S"
    )
    endDateTime = serializers.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M:%S"],
        format="%d/%m/%Y %H:%M:%S"
    )

    class Meta:
        model = Promocode
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields['company'].required = False
            self.fields['promocode'].required = False

    def validate(self, data):
        user = self.context["request"].user
        company = user.company

        if 'promocode' in data:
            promocode = data.get('promocode')
            qs = Promocode.objects.filter(company=company, promocode=promocode)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            if qs.exists():
                raise serializers.ValidationError("A promocode with this code already exists for your company.")

        return data




class CommaSeparatedUserField(serializers.Field):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("Users must be provided as a comma-separated string.")
        try:
            return [int(i.strip()) for i in data.split(",") if i.strip()]
        except ValueError:
            raise serializers.ValidationError("All user IDs must be integers.")

    def to_representation(self, value):
        return ",".join(str(i) for i in value.values_list("id", flat=True)) if value else ""

class OfferSerializer(serializers.ModelSerializer):
    users = CommaSeparatedUserField(write_only=True, required=False)
    user_ids = serializers.SerializerMethodField()

    def get_user_ids(self, obj):
        return list(obj.users.values_list("id", flat=True))

        

    startDateTime = serializers.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M:%S"],
        format="%d/%m/%Y %H:%M:%S"
    )
    endDateTime = serializers.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M:%S"],
        format="%d/%m/%Y %H:%M:%S"
    )

    offers_type = CaseInsensitiveChoiceField(choices=Offer.OFFERS_TYPE_CHOICES, required=False)
    specific_discount_type = CaseInsensitiveChoiceField(choices=Offer.DISCOUNT_TYPE_CHOICES, required=False)
    
    offers_type = serializers.ChoiceField(choices=Offer.OFFERS_TYPE_CHOICES, required=False)
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False)

    class Meta:
        model = Offer
        fields = "__all__"

    def create(self, validated_data):
        users_ids = validated_data.pop("users", [])
        offer = Offer.objects.create(**validated_data)
        if users_ids:
            offer.users.set(users_ids)
        return offer

    def update(self, instance, validated_data):
        users_ids = validated_data.pop("users", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if users_ids is not None:
            instance.users.set(users_ids)
        return instance

    def validate(self, data):
        if data.get("specific_discount_type") == "amount" and not data.get("specificAmount"):
            raise serializers.ValidationError({
                "specificAmount": "This field is required when specific_discount_type is 'amount'."
            })
        return data
class ProfessionalUserSerializer(serializers.ModelSerializer):
    company = CompanyDetailsSerializer()  
    manual_address = AddressSerializer()
    automatic_address = serializers.StringRelatedField()
    subscriptionplan = serializers.StringRelatedField()
    subscriptiontype = serializers.StringRelatedField()
    categories = serializers.StringRelatedField(many=True)
    subcategories = serializers.StringRelatedField(many=True)
    role = serializers.StringRelatedField()

    class Meta:
        model = ProfessionalUser
        fields = [
            "id","userName", "email", "phoneCode", "phone",
            "company", "manual_address", "automatic_address",
            "subscriptionplan","subscriptiontype", "categories", "subcategories",
            'finalDocument_status',
            'kbiss_status', 'iban_status', 'proofOfAddress_status',
            'identityCardFront_status', 'identityCardBack_status',
            "role", "term_condition", "is_verified","email_notifications","sms_notifications","push_notifications",
            "two_factor_authentication", "email_two_factor", "sms_two_factor",
            "created_at", "updated_at"
        ]
    def validate(self, data):
        is_2fa = data.get('two_factor_authentication', getattr(self.instance, 'two_factor_authentication', False))

        if not is_2fa:
            data['email_two_factor'] = False
            data['sms_two_factor'] = False

        return data    
class EventSerializer(serializers.ModelSerializer):
    eventAddress = serializers.JSONField(write_only=True, required=False)
    address_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = StoreEvent
        fields = ['id', 'company', 'eventTitle', 'eventImage', 'startDate', 'endDate',
                  'startTime', 'endTime', 'description', 'eventAddress', 'address_details', 'createdAt']
    def create(self, validated_data):
        event_address_data = validated_data.pop('eventAddress', None)

        if event_address_data:
            address = Address.objects.create(
                address1=event_address_data.get('address1', ''),
                address2=event_address_data.get('address2', ''),
                postalCode=event_address_data.get('postalCode', ''),
                lat=event_address_data.get('lat', None),
                lang=event_address_data.get('lang', None),
                city=event_address_data.get('city', ''),
                country=event_address_data.get('country', ''),
            )
            validated_data['eventAddress'] = address  #  Assign new address
        
        return super().create(validated_data)

    def get_address_details(self, obj):
        if obj.eventAddress:
            return {
                "address1": obj.eventAddress.address1,
                "address2": obj.eventAddress.address2,
                "postalCode": obj.eventAddress.postalCode,
                "lat": obj.eventAddress.lat,
                "lang": obj.eventAddress.lang,
                "city": obj.eventAddress.city,
                "country": obj.eventAddress.country,
            }
        return None
class InvoiceSerializer(serializers.ModelSerializer):
    
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Invoice
        fields = ['id','companyStore','customer_name', 'product_service', 'quantity', 'unit_price', 'tax_rate', 'total_amount']
        
    def create(self, validated_data):
        
        invoice = Invoice(**validated_data)
        invoice.save()  # Calls the model's save() function to calculate totalAmount
        return invoice

    

class InventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.product.name", read_only=True)
    company_id = serializers.IntegerField(source="company.id", read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    low_stock_alert = serializers.SerializerMethodField()
    medium_stock_alert = serializers.SerializerMethodField()

    class Meta:
        model = Inventory
        fields = [
            "id", "company_id", "company_name", "product", "product_name",
            "stock_quantity", "medium_stock_threshold", "low_stock_threshold",
            "last_updated", "low_stock_alert", "medium_stock_alert"
        ]
        read_only_fields = ['stock_quantity'] 

    def get_low_stock_alert(self, obj):
        """Returns a low stock warning message if stock is low"""
        if obj.stock_quantity <= obj.low_stock_threshold:
            return f"Low stock alert! Only {obj.stock_quantity} left."
        return None

    def get_medium_stock_alert(self, obj):
        """Returns a medium stock alert"""
        if obj.low_stock_threshold < obj.stock_quantity <= obj.medium_stock_threshold:
            return f"Medium stock alert! {obj.stock_quantity} in stock."
        return None
    
    def validate(self, data):
        """Ensure stock_quantity is fetched from the product."""
        product = data.get("product")
        if product:
            data["stock_quantity"] = product.quantity  
        return data
class CompanyDetailsUpdateSerializer(serializers.ModelSerializer):
    facilities = serializers.SerializerMethodField()
    subcategories = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    manual_address = AddressSerializer(required=False, allow_null=True)
    automatic_address = AddressSerializer(required=False, allow_null=True)
    coverPhotos = serializers.SerializerMethodField()
    on_site_ordering = serializers.SerializerMethodField()
    selectedCoverPhoto = serializers.SerializerMethodField()
    minimum_order_amount = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False, required=False)


    class Meta:
        model = CompanyDetails
        fields = "__all__"

    def get_categories(self, obj):
        if obj.categories is None:
            return []
        return [{"id": category.id, "name": category.name} for category in obj.categories.all()]

    def get_subcategories(self, obj):
        if obj.subcategories is None:
            return []
        return [{"id": subcategory.id, "name": subcategory.name} for subcategory in obj.subcategories.all()]

    def get_facilities(self, obj):
        if obj.facilities is None:
            return []
        return [
            {"id": facility.id, "name": facility.name, "icon": facility.icon.url if facility.icon else None}
            for facility in obj.facilities.all()
        ]

    def get_coverPhotos(self, obj):
        """Returns full URLs of cover photos."""
        if obj.coverPhotos:
            return [f"https://{settings.MEDIA_URL}{photo}" for photo in obj.coverPhotos]
        return []
    
    
    def get_on_site_ordering(self, obj):
        """ Returns full URLs of on-site ordering images."""
        if obj.on_site_ordering:
            return [f"https://{settings.MEDIA_URL}{photo}" for photo in obj.on_site_ordering]
        return []
    
    def get_selectedCoverPhoto(self, obj):
        """ Returns full URL of the selected cover photo"""
        if obj.selectedCoverPhoto:
            return f"https:/{settings.MEDIA_URL}{obj.selectedCoverPhoto}"
        return None
    
    def create_or_update_address(self, address_instance, address_data):
        """  Create a new address if it doesn't exist, otherwise update existing one. """
        if not address_data:
            return address_instance  

        if address_instance:
            for key, value in address_data.items():
                setattr(address_instance, key, value)
            address_instance.save()
            return address_instance
        else:
            return Address.objects.create(**address_data)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        
        free_cancellation_policy = request.data.get("free_cancellation_policy", instance.free_cancellation_policy)
        on_site_ordering_images = request.FILES.getlist("on_site_ordering")
        manual_address_data = request.data.get("manual_address")
        automatic_address_data = request.data.get("automatic_address")
        profile_photo = request.FILES.get("profilePhoto")
        categories_data = request.data.get("categories")
        subcategories_data = request.data.get("subcategories")
        facilities_data = request.data.get("facilities")
        minimum_order_amount = validated_data.get("minimum_order_amount", instance.minimum_order_amount)
    
        
        if minimum_order_amount:
            try:
                minimum_order_amount = float(minimum_order_amount)
            except ValueError:
                raise serializers.ValidationError({"error": "Invalid minimum_order_amount format."})

            instance.minimum_order_amount = minimum_order_amount
            
            
        if free_cancellation_policy:
            instance.free_cancellation_policy = free_cancellation_policy
        
        if facilities_data is not None:
            if isinstance(facilities_data, str):
                facilities_data = facilities_data.split(",")

            if isinstance(facilities_data, list):
                try:
                    facilities_data = [int(facility_id) for facility_id in facilities_data if facility_id]
                except ValueError:
                    raise serializers.ValidationError({"error": "Invalid facility ID format. Expected integers."})
        
        try:
            manual_address_data = json.loads(manual_address_data) if manual_address_data else None
            automatic_address_data = json.loads(automatic_address_data) if automatic_address_data else None
            categories_data = list(map(int, categories_data.split(','))) if categories_data else None
            subcategories_data = list(map(int, subcategories_data.split(','))) if subcategories_data else None
        except json.JSONDecodeError:
            raise serializers.ValidationError({"error": "Invalid JSON format in address or category fields."})
         
        if manual_address_data:
            instance.manual_address = self.create_or_update_address(instance.manual_address, manual_address_data)
        if automatic_address_data:
            instance.automatic_address = self.create_or_update_address(instance.automatic_address, automatic_address_data)
        if categories_data is not None:
            instance.categories.set(Category.objects.filter(id__in=categories_data))
        if subcategories_data is not None:
            instance.subcategories.set(Subcategory.objects.filter(id__in=subcategories_data))
        
        if facilities_data:  #  Ensure facilities_data is not an empty list
            facilities_qs = Facility.objects.filter(id__in=facilities_data)
            valid_facility_ids = list(facilities_qs.values_list("id", flat=True))
            missing_facilities = set(facilities_data) - set(valid_facility_ids)
            if missing_facilities:
                raise serializers.ValidationError({"error": f"These Facility IDs do not exist: {list(missing_facilities)}"})

            instance.facilities.set(facilities_qs)


        
        try:
            professional_user = ProfessionalUser.objects.get(company=instance)
            if professional_user:
                if categories_data is not None:
                    professional_user.categories.set(Category.objects.filter(id__in=categories_data))
                if subcategories_data is not None:
                    professional_user.subcategories.set(Subcategory.objects.filter(id__in=subcategories_data))
                professional_user.save()
                
                
        except ProfessionalUser.DoesNotExist:
           raise serializers.ValidationError({"error": "No ProfessionalUser found for this company."})
            
            
        if on_site_ordering_images:
            existing_images = instance.on_site_ordering or []
            if len(on_site_ordering_images) > 5:
                raise serializers.ValidationError({"error": "You can upload a maximum of 5 on-site ordering images."})
            
            instance.on_site_ordering = []  # Remove old images
            
            new_image_paths = []
            for photo in on_site_ordering_images:
                path = f"onsite_ordering/{photo.name}"
                saved_path = default_storage.save(path, photo)
                new_image_paths.append(saved_path)

            instance.on_site_ordering = existing_images + new_image_paths  # Replace with new images
        else:
            instance.on_site_ordering = instance.on_site_ordering or []  # Ensure it's not NULL
                    
        if profile_photo:
            profile_path = f"profile_photos/{profile_photo.name}"
            instance.profilePhoto = default_storage.save(profile_path, profile_photo)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        return instance
class CompanyReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True) 
    class Meta:
        model = CompanyReview
        fields = ['id', 'company', 'user', 'rating', 'review_text', 'created_at']
        read_only_fields = ['user', 'created_at']  

    def validate_rating(self, value):
        """Ensure rating is between 1 and 5"""
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        company = validated_data.pop('company')
        return CompanyReview.objects.create(user=user, company=company, **validated_data)



class ReelFolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReelFolder
        fields = ['id', 'name']
class DeliveryServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryService
        fields = "__all__"  

    def validate(self, data):

        delivery_fee = data.get("delivery_fee")
        minimum_order_amount = data.get("minimum_order_amount")
        travel_fee_per_km = data.get("travel_fee_per_km")

        if delivery_fee is not None and delivery_fee < 0:
            raise serializers.ValidationError({"delivery_fee": "Delivery fee cannot be negative."})

        if minimum_order_amount is not None and minimum_order_amount < 0:
            raise serializers.ValidationError({"minimum_order_amount": "Minimum order amount cannot be negative."})

        if travel_fee_per_km is not None and travel_fee_per_km < 0:
            raise serializers.ValidationError({"travel_fee_per_km": "Travel fee per km cannot be negative."})

        return data


class PerformanceMetricsSerializer(serializers.ModelSerializer):
    conversion_rate = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceMetrics
        fields = ['total_visits', 'total_completed_orders', 'conversion_rate', 'total_sales']

    def get_conversion_rate(self, obj):
        return obj.conversion_rate  # Uses @property method from model
class CategoryFolderSerializer(serializers.ModelSerializer):
   

    class Meta:
        model = CategoryFolder
        fields = ["id", "name", "productType","categories", "created_at"]
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address  # Make sure you import your Address model
        fields = ['address1', 'address2', 'postalCode', 'lat', 'lang', 'city', 'country']

class TicketsAmusementParkSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketsAmusementPark
        fields = ['id', 'name', 'description', 'adultPrice', 'childPrice']

class ProductSerializer(serializers.ModelSerializer):
    cruiseFacility = serializers.PrimaryKeyRelatedField(
        queryset=CruiseFacility.objects.all(),
        many=True,
        required=False
    )
    roomFacility = serializers.PrimaryKeyRelatedField(
        queryset=RoomFacility.objects.all(),
        many=True,
        required=False
    )
    artistName = serializers.JSONField(required=False)
    bandName = serializers.JSONField(required=False)
    petType = serializers.JSONField(required=False)
    
    availabilityDateTime = serializers.DateTimeField(required=False, allow_null=True)
    preparationDateTime = serializers.DateTimeField(required=False, allow_null=True)
    category_name = serializers.CharField(source="categoryId.name", read_only=True)

    startAddress = serializers.SerializerMethodField()
    endAddress = serializers.SerializerMethodField()

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
    
    def validate_availabilityDateTime(self, value):
        """Convert string input to DateTime object if necessary"""
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise serializers.ValidationError("Invalid date format. Use YYYY-MM-DD HH:MM:SS")
        return value
    
    def validate_preparationDateTime(self, value):
        """Convert string input to DateTime object if necessary"""
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise serializers.ValidationError("Invalid date format. Use YYYY-MM-DD HH:MM:SS")
        return value  
    
    def validate(self, attrs):
        price = attrs.get('priceOnsite')
        discount = attrs.get('discount')
        if self.instance:
            if price is None:
                price = self.instance.priceOnsite
            if discount is None:
                discount = self.instance.discount

        if price is not None and discount is not None:
            attrs['promotionalPrice'] = price - (price * discount / 100)

        return attrs

  
  

class SavedReelSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedReel
        fields = "__all__"

class ReelFolderDetailSerializer(serializers.ModelSerializer):
    reels = serializers.SerializerMethodField()

    class Meta:
        model = ReelFolder
        fields = ['id', 'name', 'reels']

    def get_reels(self, obj):
        saved_reels = SavedReel.objects.filter(folder=obj)
        reels = [saved.reel for saved in saved_reels]
        serializer = StoreReelSerializer(reels, many=True, context=self.context)
        return serializer.data
    

    
from datetime import time, timedelta

class FlexibleTimeField(serializers.TimeField):
    def to_internal_value(self, value):
        if isinstance(value, int):
            hours, minutes = divmod(value, 60)
            return time(hour=hours, minute=minutes)
        elif isinstance(value, str) and value.isdigit():
            value = int(value)
            hours, minutes = divmod(value, 60)
            return time(hour=hours, minute=minutes)
        return super().to_internal_value(value)
    
class OrderUpdateSerializer(serializers.ModelSerializer):
    onSitePreparationTime = FlexibleTimeField(required=False)
    clickCollectPreparationTime = FlexibleTimeField(required=False)
    deliveryPreparationTime = FlexibleTimeField(required=False)
    clickCollectTime = FlexibleTimeField(required=False)
    deliveryTime = FlexibleTimeField(required=False)
    serviceDuration = FlexibleTimeField(required=False)

    class Meta:
        model = Order
        fields = [
            'onSitePreparationTime', 'clickCollectPreparationTime', 'deliveryPreparationTime',
            'clickCollectTime', 'deliveryTime', 'serviceDuration',
            'orderStatus'
        ]
class MessageWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['sender', 'recipient', 'content']
        



class CaseInsensitiveChoiceField(serializers.ChoiceField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            for key, label in self.choices.items():
                if data.lower() == str(key).lower():
                    return key
            self.fail("invalid_choice", input=data)
        return super().to_internal_value(data)

    
class AdvertiseCampaignSerializer(serializers.ModelSerializer):
    startDateTime = serializers.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M:%S"],
        format="%d/%m/%Y %H:%M:%S"
    )
    endDateTime = serializers.DateTimeField(
        input_formats=["%d/%m/%Y %H:%M:%S"],
        format="%d/%m/%Y %H:%M:%S"
    )

    objective = CaseInsensitiveChoiceField(choices=AdvertiseCampaign.OBJECTIVE_CHOICES)
    ad_type = CaseInsensitiveChoiceField(choices=AdvertiseCampaign.AD_TYPE_CHOICES)
    bid_type = CaseInsensitiveChoiceField(choices=AdvertiseCampaign.BID_TYPE_CHOICES)
    age_range = serializers.CharField(allow_blank=True, required=False)

    gender = CaseInsensitiveChoiceField(choices=AdvertiseCampaign.GENDER_CHOICES)
    placement = CaseInsensitiveChoiceField(choices=AdvertiseCampaign.PLACEMENT_CHOICES)
    audience = CaseInsensitiveChoiceField(choices=AdvertiseCampaign.AUDIENCE_CHOICES)
    target_type = CaseInsensitiveChoiceField(choices=AdvertiseCampaign.TARGETING_TYPE_CHOICES)


    class Meta:
        model = AdvertiseCampaign
        fields = '__all__'


        

class AdImpressionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdImpression
        fields = ['id', 'campaign', 'user', 'timestamp']
        read_only_fields = ['id', 'user', 'timestamp']


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    company = CompanyDetailsSerializer(read_only=True)
    order_items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'company', 'order_type', 'created_at', 'order_items']

class UserPaymentTransactionSerializer(serializers.ModelSerializer):
    transaction_amount = serializers.SerializerMethodField()
    direction = serializers.SerializerMethodField()
    transaction_symbol = serializers.SerializerMethodField()
    currency_symbol = serializers.SerializerMethodField()

    class Meta:
        model = UserPayment
        fields = [
            'transaction_amount', 
            'created_at', 
            'currency', 
            'currency_symbol', 
            'status', 
            'direction', 
            'transaction_symbol',
            'stripe_payment_id'
        ]
    def get_transaction_amount(self, obj):
        return f"{abs(obj.amount)}"  # Always positive

    def get_direction(self, obj):
        return obj.payment_direction.upper() if obj.payment_direction else "UNKNOWN"

    def get_transaction_symbol(self, obj):
        if obj.payment_direction == "credited":
            return "+"
        elif obj.payment_direction == "debited":
            return "-"
        return ""

    def get_currency_symbol(self, obj):
        currency_map = {
            "USD": "$",
            "INR": "₹",
            "EUR0": "€",
            "GBP": "£",
        }
        return currency_map.get(obj.currency, "")  # Default empty if unknown
    
    def get_stripe_payment_id(self, obj):
        return obj.stripe_payment_id

class UserTransactionListSerializer(serializers.ModelSerializer):
    professional_user_name = serializers.CharField(source='professional_user.name', read_only=True)

    class Meta:
        model = UserPayment
        fields = ['id', 'amount', 'status', 'created_at', 'professional_user_name']


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = '__all__'
        extra_kwargs = {
            'company': {'required': False, 'allow_null': True},
        }
        
class CruiseRoomSerializer(serializers.ModelSerializer):
    roomId = serializers.CharField(source='room_id')
    roomType = serializers.SerializerMethodField()
    totalMembers = serializers.IntegerField(source='adults')
    isAvailable = serializers.SerializerMethodField()

    class Meta:
        model = CruiseRoom
        fields = ['roomId', 'roomType', 'roomQuantity', 'roomPrice', 'totalMembers', 'isAvailable']

    def get_roomType(self, obj):
        return obj.get_roomType_display()

    def get_isAvailable(self, obj):
        return obj.roomQuantity > 0

        

class FriendshipSerializer(serializers.ModelSerializer):
    related_user = serializers.SerializerMethodField()

    class Meta:
        model = Friendship
        fields = ['id', 'relationship_type', 'status', 'created_at', 'related_user']

    def get_related_user(self, obj):
        context = self.context.get('relation', 'sender')  # 'sender' or 'receiver'
        related_instance = getattr(obj, context)

        if isinstance(related_instance, Users):
            data = UserSerializer(related_instance).data
            data['type'] = 'user'
        elif isinstance(related_instance, CompanyDetails):
            data = CompanyDetailsSerializer(related_instance).data
            data['type'] = 'company'
        else:
            data = {}
        return data


class FeedbackProfessionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = professionalFeedback
        fields = ['id', 'user','title', 'description', 'media', 'submitted_at']
        
        
        
class InvoiceSerializer(serializers.Serializer):
    customer_name = serializers.CharField()
    product_service = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Users  
        fields = ['id', 'username', 'profileImage'] 
        


from django.utils import timezone     
class NotificationSerializer(serializers.ModelSerializer):
    sender = UserProfileSerializer()  # nested sender profile
    created_at_display = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id','title', 'message', 'notification_type', 'created_at', 'created_at_display', 'sender', 'user']

    def get_created_at_display(self, obj):
        created_at = obj.created_at
        if created_at:
            if created_at.tzinfo is None:
                created_at = timezone.make_aware(created_at)

            time_diff = timezone.now() - created_at
            days_diff = time_diff.days
            minutes_diff = time_diff.seconds // 60
            hours_diff = time_diff.seconds // 3600

            if days_diff == 0:
                if hours_diff == 0:
                    if minutes_diff <= 60:
                        return f"{minutes_diff} Min"
                    return timeago.format(created_at, timezone.now())
                return f"{hours_diff} Hr"
            
            if 1 <= days_diff <= 3:
                return f"{days_diff} days"

            return created_at.strftime('%d/%m/%Y')
        return None
    

class LoyaltyCardCreateSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = LoyaltyCard
        fields = "__all__"

    def validate(self, attrs):
        reward_type = attrs.get('reward_type')
        discount_value = attrs.get('discount_value')

        if reward_type == 'discount' and discount_value is None:
            raise serializers.ValidationError({
                'discount_value': "This field is required when reward_type is 'discount'."
            })

        if reward_type == 'free_product' and discount_value is not None:
            raise serializers.ValidationError({
                'discount_value': "This field must be null when reward_type is 'free_product'."
            })

        return attrs



class RoomFacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomFacility
        fields = ['id', 'name', 'icon', 'is_selected', 'created_at', 'updated_at']


class TicketSerializer(serializers.ModelSerializer):

    class Meta:
        model=Ticket
        fields="__all__"






class TicketsAmusementParkSerializer(serializers.ModelSerializer):

    class Meta:
        model=TicketsAmusementPark
        fields="__all__"


class CruiseRoomSerializer(serializers.ModelSerializer):
    roomId = serializers.CharField(source='room_id')
    roomType = serializers.SerializerMethodField()
    totalMembers = serializers.IntegerField(source='adults')
    isAvailable = serializers.SerializerMethodField()

    class Meta:
        model = CruiseRoom
        fields = ['roomId', 'roomType', 'roomQuantity', 'roomPrice', 'totalMembers', 'isAvailable']

    def get_roomType(self, obj):
        return obj.get_roomType_display()

    def get_isAvailable(self, obj):
        return obj.roomQuantity > 0


class RoomBookingSerializer(serializers.ModelSerializer):
    product_data = serializers.SerializerMethodField()
    room_data = serializers.SerializerMethodField()

    class Meta:
        model = RoomBooking
        fields = '__all__'  
        
    def get_product_data(self, obj):
        if obj.product:
            return ProductSerializer(obj.product).data
        return None

    def get_room_data(self, obj):
        if obj.room:
            return CruiseRoomSerializer(obj.room).data
        return None
    
    
class EventBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = eventBooking
        fields = '__all__'

class ExperienceBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = experienceBooking
        fields = '__all__'

class CancelOrderSerializer(serializers.Serializer):
    cancel_reasons = serializers.ChoiceField(choices=Order.CANCEL_REASONS)




class SupportTicketStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ['ticket_id', 'status']
        read_only_fields = ['ticket_id', 'status']


class SlotBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = slotBooking
        fields = '__all__'


class AestheticsBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = aestheticsBooking
        fields = '__all__'


class RelaxationBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = relaxationBooking
        fields = '__all__'




class ArtandCultureBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = artandcultureBooking
        fields = '__all__'
