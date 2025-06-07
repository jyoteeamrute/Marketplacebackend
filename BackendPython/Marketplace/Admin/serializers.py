from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from rest_framework import serializers
from .models import Subscription
from ProfessionalUser.models import Product, ProfessionalUser,CompanyDetails ,StoreReel, StoreImage, StoreEvent,Order
from UserApp.models import Users 
from Admin.models import *
from django.core.validators import RegexValidator
from rest_framework import serializers
from django.conf import settings
import timeago
from django.utils import timezone
from rest_framework import serializers
from datetime import timedelta

from django.db.models import F, Avg
from Admin.models import *


User = get_user_model()

# #admin login
# class AdminUserLoginSerializer(serializers.Serializer):
#     email = serializers.EmailField()
#     password = serializers.CharField(write_only=True)

#     def validate(self, data):
#         email = data.get("email")
#         password = data.get("password")

#         user = authenticate(email=email, password=password)
#         if user is None:
#             raise serializers.ValidationError("Invalid email or password.")
        
#         if not user.is_active:
#             raise serializers.ValidationError("User account is disabled.")

#         refresh = RefreshToken.for_user(user)
#         return {
#             "user": {
#                 "id": user.id,
#                 # "id": user.role,
#                 "name": user.name,
#                 "email": user.email,
#                 "role": user.role.name if user.role else None
#             },
#             "refresh_token": str(refresh),
#             "access_token": str(refresh.access_token)
            
#         }

class AdminUserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        user = authenticate(email=email, password=password)
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        # refresh = RefreshToken.for_user(user)
        refresh = RefreshToken.for_user(user)
        refresh["email"] = user.email
        refresh["role"] = user.role.name if user.role else None
        refresh["user_type"] = "admin"
        refresh["admin_id"] = user.id
        
        return {
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role.name if user.role else None,
                "user_type": getattr(user, "user_type", "admin"),
            },
            "refresh_token": str(refresh),
            "access_token": str(refresh.access_token)
        }

 
class AdminForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class AdminResetPasswordSerializer(serializers.Serializer):
    reset_link = serializers.CharField()
    password = serializers.CharField(write_only=True)

       
class AdminUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()  
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(), source="role", write_only=True
    )  

    mobile = serializers.CharField(
        validators=[RegexValidator(
            regex=r'^\+?\d{1,15}$',
            message="Mobile number must contain only digits and may start with '+'."
        )]
    )

    class Meta:
        model = AdminUser
        fields = ['id', 'name', 'email', 'mobile', 'role', 'role_id', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def get_role(self, obj):
        return obj.role.name if obj.role else None  

    def validate_mobile(self, value):
        """Ensure mobile number contains only digits and may start with '+'."""
        if not value.startswith("+") and not value.isdigit():
            raise serializers.ValidationError("Mobile number must contain only digits and may start with '+'.")
        if len(value) > 15:
            raise serializers.ValidationError("Mobile number must be up to 15 digits.")
        return value  

    def create(self, validated_data):
        """Override create method to hash password before saving."""
        password = validated_data.pop("password", None) 
        user = AdminUser(**validated_data) 
        if password:
            user.set_password(password)  
        user.save()
        return user  
 
 
class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'machine_name', 'created_at', 'updated_at']
        extra_kwargs = {
            'name': {'required': True},
            'machine_name': {'required': True}
        }


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    discount_percentage = serializers.SerializerMethodField()
    total_discount = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = "__all__"  # Includes all fields + discount_percentage + total_discount

    def validate_subscription(self, value):
        if not Subscription.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Subscription does not exist.")
        return value

    def get_discount_percentage(self, obj):
        """
        Calculate how much the user saves on the annual plan compared to the monthly plan.
        """
        if obj.annualPlan and obj.price:
            monthly_cost_for_year = obj.price * 12
            discount = (monthly_cost_for_year - obj.annualPlan) / monthly_cost_for_year * 100
            return round(discount, 2)  
        return 0

    def get_total_discount(self, obj):
        """
        Calculate the average discount percentage across all active subscription plans.
        """
        avg_discount = SubscriptionPlan.objects.filter(
            annualPlan__isnull=False, price__isnull=False
        ).annotate(
            discount_percentage=((12 * F("price") - F("annualPlan")) / (12 * F("price")) * 100)
        ).aggregate(Avg("discount_percentage"))

        return round(avg_discount["discount_percentage__avg"], 2) if avg_discount["discount_percentage__avg"] else 0


class SubscriptionSerializer(serializers.ModelSerializer):
    plans = SubscriptionPlanSerializer(many=True, read_only=True)
    name = serializers.CharField()

    class Meta:
        model = Subscription
        fields = [
            'id', 'name', 'description', 'popular', 'is_active', 'is_deleted',
            'category_limit', 'subcategory_limit', 'created_at', 'updated_at', 'plans'
        ]

    def validate_name(self, value):
        """
        Ensure that the name is either a predefined plan or a valid new one.
        """
        existing_choices = ['Silver', 'Gold', 'Premium', 'FreePlan']
        if value in existing_choices:
            return value  # Allowed predefined names
        
        if Subscription.objects.filter(name=value).exists():
            raise serializers.ValidationError("A subscription with this name already exists.")
        
        return value


# class SubscriptionSerializer(serializers.ModelSerializer):
#     plans = SubscriptionPlanSerializer(many=True, read_only=True)  # Include related plans
   

#     class Meta:
#         model = Subscription
#         fields = [
#             'id', 'name', 'description', 'popular', 'is_active', 'is_deleted',
#             'category_limit', 'subcategory_limit', 'created_at', 'updated_at', 'plans'
#         ]

   
       
class MenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = ['id', 'menuname', 'created_at', 'updated_at', 'is_deleted']
        extra_kwargs = {
            'is_deleted': {'read_only': True}  
        }
    
    
class SubmenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submenu
        fields = ['id', 'submenuname', 'menu', 'is_deleted', 'created_at', 'updated_at']
        extra_kwargs = {
            'is_deleted': {'read_only': True}  
        }
    
class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = '__all__'
        
    def validate_name(self, value):
        """Check if name already exists to prevent duplicates."""
        if Module.objects.filter(name=value).exists():
            raise serializers.ValidationError("A module with this name already exists.")
        return value
        
        
class SaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = ['id', 'sale_name', 'sale_value', 'description', 'role', 'created_at', 'updated_at']
        
    def validate_sale_name(self, value):
        """Check if sale_name already exists to prevent duplicates."""
        if Sale.objects.filter(sale_name=value).exists():
            raise serializers.ValidationError("A sale with this name already exists.")
        return value
        
        
        
class SubmoduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submodule
        fields = ['id', 'name', 'module', 'sales']
        
    def validate_sales(self, value):
        """Ensure that no more than 2 sales are selected."""
        if len(value) > 2:
            raise serializers.ValidationError("Maximum 2 sales can be selected.")
        return value
    
    def validate_name(self, value):
        """Check if name already exists to prevent duplicates."""
        if Submodule.objects.filter(name=value).exists():
            raise serializers.ValidationError("A Submodule with this name already exists.")
        return value
    
    
    

class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = '__all__'
        
    def validate_name(self, value):
        """Ensure language name is unique"""
        if Language.objects.filter(name=value).exists():
            raise serializers.ValidationError("A language with this name already exists.")
        return value
        
    def validate_code(self, value):
        """Ensure code is unique"""
        if Language.objects.filter(code=value).exists():
            raise serializers.ValidationError("A language with this code already exists.")
        return value
        

class CountrySerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True)
    class Meta:
        model = Country
        fields = '__all__'
        ref_name = "AdminCountry"
    
    def validate_name(self, value):
        """Ensure country name is unique"""
        if Country.objects.filter(name=value).exists():
            raise serializers.ValidationError("A country with this name already exists.")
        return value
        
    def validate_code(self, value):
        """Ensure short_name is unique"""
        if Country.objects.filter(code=value).exists():
            raise serializers.ValidationError("A country with this code already exists.")
        return value
    
        
        
        

class CategorySerializer(serializers.ModelSerializer):
    categoriesImage = serializers.ImageField(required=False, allow_null=True)  # Allow image to be optional

    class Meta:
        model = Category
        fields = '__all__'

    def create(self, validated_data):
        """Set default values on category creation"""
        validated_data.setdefault('is_active', True)
        validated_data.setdefault('status', True)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Handle image replacement properly"""
        new_image = validated_data.get('categoriesImage', None)

        if new_image:
            # Delete old image only if a new one is uploaded
            if instance.categoriesImage:
                instance.categoriesImage.delete(save=False)
            instance.categoriesImage = new_image

        return super().update(instance, validated_data)

    def validate_name(self, value):
        """Ensure category name is unique (excluding current instance)"""
        if self.instance and Category.objects.filter(name=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value

    def validate_machine_name(self, value):
        """Ensure machine_name is unique (excluding current instance)"""
        if self.instance and Category.objects.filter(machine_name=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A category with this machine name already exists.")
        return value

class SubcategorySerializer(serializers.ModelSerializer):
    subcategoriesImage = serializers.ImageField(required=False, allow_null=True)  # Allow optional image

    class Meta:
        model = Subcategory
        fields = '__all__'

    def validate_name(self, value):
        """Ensure subcategory name is unique (excluding current instance)"""
        if self.instance and Subcategory.objects.filter(name=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("A subcategory with this name already exists.")
        return value

 


class ProfessionalUserListSerializer(serializers.ModelSerializer):
    """Serializer for listing professional users with all details"""

    company = serializers.SerializerMethodField()
    manual_address = serializers.SerializerMethodField()
    automatic_address = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    subcategories = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()

    class Meta:
        model = ProfessionalUser
        fields = [
            "id", "userName", "email", "phone", "company",
            "manual_address", "automatic_address",
            "categories", "subcategories", "role",
            "subscription_status", "is_verified",
            "created_at", "updated_at","finalDocument_status"
        ]

    def get_company(self, obj):
        """Get company details including structured document details with status"""
        if obj.company:
            def get_document(file_field, name, status_field):
                """Helper function to format document details with status"""
                if file_field:
                    file_url = file_field.url
                    if not file_url.startswith("http"):
                        file_url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}{file_url}"
                    return {
                        "document_name": name,
                        "document_url": file_url,
                        "status": getattr(obj, status_field, "pending")
                    }
                return None

            return {
                "id": obj.company.id,
                "name": obj.company.companyName,
                "documents": [
                    get_document(obj.company.kbiss, "KBIS", "kbiss_status"),
                    get_document(obj.company.iban, "IBAN", "iban_status"),
                    get_document(obj.company.identityCardFront, "Identity Card Front", "identityCardFront_status"),
                    get_document(obj.company.identityCardBack, "Identity Card Back", "identityCardBack_status"),
                    get_document(obj.company.proofOfAddress, "Proof of Address", "proofOfAddress_status"),
                    
                ]
            }
        return None

    def get_manual_address(self, obj):
        """Return manual address details if available"""
        if obj.manual_address:
            return {
                "id": obj.manual_address.id,
                "address": obj.manual_address.address1,
                "city": obj.manual_address.city,
                "postalCode": obj.manual_address.postalCode,
                "country": obj.manual_address.country
            }
        return None

    def get_automatic_address(self, obj):
        """Return automatic address details if available"""
        if obj.automatic_address:
            return {
                "id": obj.automatic_address.id,
                "address": obj.automatic_address.address1,
                "city": obj.automatic_address.city,
                "postalCode": obj.automatic_address.postalCode,
                "country": obj.automatic_address.country
            }
        return None

    def get_categories(self, obj):
        """Return a list of category IDs & names if categories exist"""
        if obj.company and obj.company.categories.exists():
            return [{"id": cat.id, "name": cat.name} for cat in obj.company.categories.all()]
        return None

    def get_subcategories(self, obj):
        """Return a list of subcategory IDs & names if subcategories exist"""
        if obj.company and obj.company.subcategories.exists():
            return [{"id": sub.id, "name": sub.name} for sub in obj.company.subcategories.all()]
        return None

    def get_role(self, obj):
        """Return role details if available"""
        if obj.role:
            return {
                "id": obj.role.id,
                "name": obj.role.name,
            }
        return None

    def get_subscription_status(self, obj):
        """Return subscription status if exists, else None"""
        return obj.subscriptionplan.status if obj.subscriptionplan else None







class RolePermissionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = RolePermissions
        fields = '__all__'

    def validate(self, data):
        """Ensure role_id, menu_id, or at least one permission is provided"""
        role_id = data.get("role_id")
        menu_id = data.get("menu_id")
        permissions = data.get("permissions")  # Assuming permissions is a list or field in the data

        if not role_id and not menu_id and not permissions:
            raise serializers.ValidationError({
                "error": "At least one of role_id, menu_id, or permission must be provided."
            })
        return data





class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ["id", "couponCode", "discount_type", "amount", "status", "created_at", "updated_at"]

    def validate_amount(self, value):
        """Ensure the discount amount is greater than zero."""
        if value <= 0:
            raise serializers.ValidationError("Discount amount must be greater than zero.")
        return value
    



from rest_framework import serializers
from django.utils import timezone  


class SupportTicketSerializer(serializers.ModelSerializer):
    updated_at1 = serializers.SerializerMethodField()
    order_type = serializers.SerializerMethodField()
    order = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            'id', 'ticket_id', 'ticket_category', 'subject', 'description',
            'documents', 'status', 'created_at', 'updated_at', 'updated_at1',
            'type_of_user', 'created_by_user_id', 'specific_order',
            'order_type', 'order'
        ]

    def get_updated_at1(self, obj):
        updated_at = obj.updated_at
        if updated_at:
            if updated_at.tzinfo is None:
                updated_at = timezone.make_aware(updated_at)

            time_diff = timezone.now() - updated_at
            days_diff = time_diff.days
            minutes_diff = time_diff.seconds // 60
            hours_diff = time_diff.seconds // 3600

            if days_diff == 0:
                if hours_diff == 0:
                    if minutes_diff <= 60:
                        return f"{minutes_diff} Min ago"
                    return timeago.format(updated_at, timezone.now())
                return f"{hours_diff} Hr ago"
            if 1 <= days_diff <= 3:
                return f"{days_diff} days ago"
            return updated_at.strftime('%d/%m/%Y')
        return None

    def get_order_type(self, obj):
        if obj.content_type:
            return obj.content_type.model  # e.g., 'order', 'roombooking', etc.
        return None

    def get_order(self, obj):
        if not obj.order:
            return None

        # Try to get a booking_id or order_id from the linked object
        possible_fields = ['order_id', 'booking_id', 'slot_id']
        for field in possible_fields:
            if hasattr(obj.order, field):
                return getattr(obj.order, field)
        
        # If none exist, fall back to object_id
        return obj.object_id

# class SupportTicketSerializer(serializers.ModelSerializer):
#     updated_at1 = serializers.SerializerMethodField()

#     class Meta:
#         model = SupportTicket
#         fields = [
#             'id', 'ticket_id', 'ticket_category', 'subject', 'description',
#             'documents', 'status', 'created_at', 'updated_at', 'updated_at1',
#             'type_of_user', 'created_by_user_id', 'order', 'specific_order'
#         ]

#     def get_updated_at1(self, obj):
#         updated_at = obj.updated_at
#         if updated_at:
#             # Make sure updated_at is timezone-aware
#             if updated_at.tzinfo is None:
#                 updated_at = timezone.make_aware(updated_at)

#             # Calculate time difference
#             time_diff = timezone.now() - updated_at
#             days_diff = time_diff.days
#             minutes_diff = time_diff.seconds // 60
#             hours_diff = time_diff.seconds // 3600

#             # If it's within a day, use timeago formatting
#             if days_diff == 0:
#                 if hours_diff == 0:
#                     if minutes_diff <= 60:
#                         return f"{minutes_diff} Min ago"
#                     return timeago.format(updated_at, timezone.now())
#                 return f"{hours_diff} Hr ago"
            
#             # If it's more than a day but less than or equal to 7 days, show as "X days ago"
#             if 1 <= days_diff <= 3:
#                 return f"{days_diff} days ago"
            
#             # If it's more than 7 days, show the exact date in dd/mm/yyyy format
#             return updated_at.strftime('%d/%m/%Y')

#         return None


class FacilitySerializer(serializers.ModelSerializer):
    prouser_id = serializers.PrimaryKeyRelatedField(
        queryset=ProfessionalUser.objects.all(), required=False, allow_null=True, source="prouser"
    )

    class Meta:
        model = Facility
        fields = ["id", "name", "icon", "is_selected", "prouser_id"]




class HelpFAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = HelpFAQ
        fields = ['id', 'question', 'answer', 'category']
        extra_kwargs = {
            'category': {'required': False}  # make category not required here too
        }

class HelpCategorySerializer(serializers.ModelSerializer):
    faqs = HelpFAQSerializer(many=True, required=False)  # important

    class Meta:
        model = HelpCategory
        fields = ['id', 'title', 'description', 'faqs']

    def create(self, validated_data):
        faqs_data = validated_data.pop('faqs', [])
        category = HelpCategory.objects.create(**validated_data)
        for faq_data in faqs_data:
            faq_data['category'] = category
            HelpFAQ.objects.create(**faq_data)
        return category

class ReelReportAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReelReport
        fields = ['id', 'user', 'reel', 'reason', 'other_reason', 'created_at', 'status']


class ReelReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReelReport
        fields = ['id', 'user', 'reel', 'reason', 'other_reason', 'created_at', 'status']
        read_only_fields = ['id', 'created_at', 'status', 'user']

    def validate(self, data):
        if data['reason'] == 'other' and not data.get('other_reason'):
            raise serializers.ValidationError({"other_reason": "This field is required when reason is 'other'."})
        return data


      
class AdvertisementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advertisement
        fields = '__all__'


    


class StoreEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreEvent
        fields = [ 'id', 'company', 'eventTitle','eventImage','startDate','endDate', 'startTime',
            'endTime', 'eventAddress', 'description', 'createdAt',
        ]
        
class UserLoginDetailSerializer(serializers.ModelSerializer):
    last_login_formatted = serializers.ReadOnlyField()
    is_currently_logged_in = serializers.ReadOnlyField()

    class Meta:
        model = Users
        fields = [
            'id', 'username', 'email', 'phone', 'firstName', 'lastName',
            'gender', 'last_login', 'is_active', 'createdAt', 'updatedAt',
            'last_login_formatted', 'is_currently_logged_in'
        ]


class ProfessionalUserLoginDetailSerializer(serializers.ModelSerializer):
    last_login_formatted = serializers.ReadOnlyField()
    is_currently_logged_in = serializers.ReadOnlyField()

    class Meta:
        model = ProfessionalUser
        fields = [
            'id', 'userName', 'email', 'phone', 'company',
            'last_login', 'finalDocument_status', 'subscription_active',
            'created_at', 'updated_at',
            'last_login_formatted', 'is_currently_logged_in',
             
        ]


from rest_framework import serializers

class AdminBankAccountDetailsSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    user_role = serializers.SerializerMethodField()
    # username = serializers.SerializerMethodField()

    class Meta:
        model = AdminBankAccountDetails
        fields = [
            "id", "user",  
            "user_role",  "account_holder_name",   "account_number",  "bank_name",  "branch_name",
            "branch_address", "bank_address","ifsc_code","iban_number","swift_code",
            "created_at", "updated_at", "is_active",
        ]

    def get_user_role(self, obj):
        """Return the role name of the user."""
        return obj.user.role.name if obj.user and obj.user.role else None


class OrderSerializer(serializers.ModelSerializer):
    booking_id = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['order_id', 'booking_id', ...]  # include other fields

    def get_booking_id(self, obj):
        return f"ORD-{obj.order_id}"


from UserApp.serializers import UserSerializer
from ProfessionalUser.serializers import ProfessionalUserSerializer  # if available

class AdminNotificationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    professional_user = ProfessionalUserSerializer(read_only=True)
    created_at_display = serializers.SerializerMethodField()

    class Meta:
        model = AdminNotification
        fields = [
            'id', 'title', 'message', 'notification_type',
            'user', 'professional_user', 'created_at', 'created_at_display', 'is_read'
        ]

    def get_created_at_display(self, obj):
        created_at = obj.created_at
        if created_at:
            if created_at.tzinfo is None:
                created_at = timezone.make_aware(created_at)

            now = timezone.now()
            diff = now - created_at
            days = diff.days
            minutes = diff.seconds // 60
            hours = diff.seconds // 3600

            if days == 0:
                if hours == 0:
                    if minutes < 60:
                        return f"{minutes} Min ago"
                    return timeago.format(created_at, now)
                return f"{hours} Hr ago"
            elif 1 <= days <= 3:
                return f"{days} days ago"
            else:
                return created_at.strftime('%d/%m/%Y')
        return None

class LegalDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegalDocument
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']