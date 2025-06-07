from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.db import models
from django.utils.text import slugify
from django.db.models import Avg

import re
from django.utils.text import slugify as django_slugify

def custom_slugify(value):
    # Lowercase, remove non-word characters (except underscores), convert spaces to underscores
    value = re.sub(r'[^\w\s]', '', value)  # Remove punctuation except underscores
    value = re.sub(r'\s+', '_', value.strip())  # Convert spaces to underscores
    return value.lower()


# Role Table
class Role(models.Model):
    ROLE_CHOICES = [
        ("administrator", "Administrator"),
        ('user', 'User'),
        ('professionaluser', 'ProfessionalUser'),
    ]

    name = models.CharField(max_length=60, unique=True, blank=True, null=True)
    machine_name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True,blank=True, null=True)
    def save(self, *args, **kwargs):
        """Ensure role names are stored in lowercase"""
        if self.name:
            self.name = self.name.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name if self.name else "Unnamed Role"



# Custom Admin User Manager
class AdminUserManager(BaseUserManager):
    def create_user(self, email,name=None, password=None, mobile=None, role=None):
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(
            email=self.normalize_email(email),
            mobile=mobile,
            name=name,
            role=role
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password):

        admin_role, created = Role.objects.get_or_create(
            name="administrator",
            defaults={
                "machine_name": "Administrator",  
                "description": "Administrator role with full access"
            }
        )

        if created:
            admin_role.machine_name = "Administrator"
            admin_role.save()

        user = self.create_user(email=email, name=name, password=password, role=admin_role)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


# Custom Admin User Model
class AdminUser(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=255, unique=True,null=True, blank=True)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=15, unique=True, null=True, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    language = models.CharField(max_length=10, default="en")
    auto_translate_messages = models.BooleanField(default=True) 

    # Fix conflicts by setting related names
    groups = models.ManyToManyField(Group, related_name="adminuser_groups", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="adminuser_permissions", blank=True)

    objects = AdminUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return self.email if self.email else "Unnamed AdminUser"



class Menu(models.Model):
    menuname = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.menuname
    


class Submenu(models.Model):
    submenuname = models.CharField(max_length=255, unique=True)
    menu = models.ForeignKey(Menu, on_delete=models.SET_NULL, related_name="submenus",blank=True, null=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.submenuname
    

class Module(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
    ]
    
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    
class Sale(models.Model):
    sale_name = models.CharField(max_length=255)
    sale_value = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL,blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.sale_name
    
class Submodule(models.Model):
    name = models.CharField(max_length=255)
    module = models.ForeignKey(Module, on_delete=models.SET_NULL,blank=True, null=True)
    sales = models.ManyToManyField(Sale, blank=True)
    
    def __str__(self):
        return self.name
    
    

class Language(models.Model):
    countryFlag = models.CharField(max_length=255, blank=True, null=True)  
    name = models.CharField(max_length=255)
    shortName = models.CharField(max_length=50, blank=True, null=True)  
    translateName = models.CharField(max_length=255, blank=True, null=True)  
    userID = models.ForeignKey(AdminUser, on_delete=models.SET_NULL, related_name="languages", blank=True, null=True)
    code = models.CharField(max_length=50, unique=True)  
    status = models.BooleanField(default=True)  
    image = models.URLField(blank=True, null=True)    
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)  

    def __str__(self):
        return self.name    
    

class Country(models.Model):
    name = models.CharField(max_length=255)
    shortNAME = models.CharField(max_length=50, blank=True, null=True)
    userID = models.ForeignKey(AdminUser, on_delete=models.SET_NULL, related_name="countries", blank=True, null=True)
    code = models.CharField(max_length=10)
    emoji = models.CharField(max_length=10)
    image = models.ImageField(upload_to="country/", blank=True, null=True)
    dialCodes = models.JSONField(blank=True, null=True)  
    slug = models.SlugField(unique=True)  
    currency = models.CharField(max_length=50, blank=True, default="")  
    status = models.BooleanField(default=True)  
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True) 

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = custom_slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    
    
class Category(models.Model):
    name = models.CharField(max_length=255)
    machine_name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    type = models.TextField(blank=True, null=True)
    categoriesImage = models.ImageField(upload_to='uploads/', blank=True, null=True)
    icon=models.ImageField(upload_to='uploads/', blank=True, null=True)
    distance = models.FloatField(blank=True, null=True)
    slug = models.SlugField(unique=True,blank=True, null=True) 
    onSite = models.BooleanField(default=False)
    clickCollect = models.BooleanField(default=False)
    halal = models.BooleanField(default=False)
    handicapped = models.BooleanField(default=False)
    rooftop = models.BooleanField(default=False)
    freeCancellation = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    user = models.ForeignKey(AdminUser, on_delete=models.SET_NULL, related_name="categories",blank=True, null=True)
    status = models.BooleanField(default=True)
    order_by = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = custom_slugify(self.name)
        if not self.machine_name:
            self.machine_name = custom_slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    

class Subcategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    machine_name = models.CharField(max_length=255, unique=True, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    type = models.TextField(blank=True, null=True)
    subcategoriesImage = models.ImageField(upload_to='uploads/subcategories_image/', max_length=255,blank=True, null=True) 
    distance = models.FloatField(blank=True, null=True)
    slug = models.SlugField(unique=True,blank=True, null=True) 
    clickCollect = models.BooleanField(default=False)
    halal = models.BooleanField(default=False)
    handicapped = models.BooleanField(default=False)
    rooftop = models.BooleanField(default=False)
    freeCancellation = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    parentCategoryId = models.ForeignKey(Category, on_delete=models.SET_NULL, related_name="subcategories" ,null=True, blank=True)
    user = models.ForeignKey(AdminUser, on_delete=models.SET_NULL, related_name="subcategories",blank=True, null=True)
    status = models.BooleanField(default=True)
    order_by = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = custom_slugify(self.name)
        if not self.machine_name:
            self.machine_name = custom_slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name



class Subscription(models.Model):
    STATUS_CHOICES = [
        ('inactive', 'Inactive'),
        ('active', 'Active'),
    ]

    name = models.CharField(max_length=255, unique=True)  # No choices here
    description = models.TextField()
    popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    category_limit = models.IntegerField(default=0)
    subcategory_limit = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return self.name



class SubscriptionPlan(models.Model):
    SUBSCRIPTION_TYPE_CHOICES = [
        ('Monthly', 'monthly'),
        ('Annual', 'annual'),
    ]

    STATUS_CHOICES = [
        ('inactive', 'Inactive'),
        ('active', 'Active'),
    ]

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="plans")
    subscription_type = models.CharField(max_length=10, choices=SUBSCRIPTION_TYPE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # save_profit_percentage = models.CharField(max_length=55, null=True, blank=True)
    no_commitment_plan = models.CharField(max_length=55, null=True, blank=True)
    three_month_plan = models.CharField(max_length=55, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='inactive')
    monthlyPlan = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    annualPlan = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    features = models.JSONField(default=list)  
    is_active = models.BooleanField(default=True, null=True, blank=True)
    is_deleted = models.BooleanField(default=False, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def calculate_discount_percentage(self):
        """
        Calculate how much the user saves on the annual plan compared to the monthly plan.
        """
        if self.annualPlan and self.price:
            monthly_cost_for_year = self.price * 12
            discount = (monthly_cost_for_year - self.annualPlan) / monthly_cost_for_year * 100
            return round(discount, 2)  # Round to 2 decimal places
        return 0

    @classmethod
    def get_average_discount(cls):
        """
        Calculate the average discount percentage across all active subscription plans.
        """
        avg_discount = cls.objects.filter(
            annualPlan__isnull=False, price__isnull=False
        ).annotate(
            discount_percentage=((12 * models.F("price") - models.F("annualPlan")) / (12 * models.F("price")) * 100)
        ).aggregate(Avg("discount_percentage"))["discount_percentage__avg"]

        return round(avg_discount, 2) if avg_discount else 0  # Return 0 if no valid plans exist

    def __str__(self):
        return f"{self.subscription.name} - {self.subscription_type}"

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


import uuid

class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
        ('closed', 'Closed'),
    ]
    
    CATEGORY_CHOICES = [
        ('refund', 'Refund Request'),
        ('quality_issue', 'Quality Issue'),
        ('payment_issue', 'Payment Issue'),
        ('account_issue', 'Account Problem'),
        ('order_issue', 'Order Issue'),
        ('other', 'Other'),
    ]
    USER_TYPE_CHOICES = [
        ('user', 'User'),
        ('professionaluser', 'ProfessionalUser'),
    ]


    # Correct ForeignKey references
    ticket_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    created_by_user_id = models.IntegerField(null=True, blank=True)
    # user = models.ForeignKey('UserApp.Users', on_delete=models.CASCADE, related_name="tickets", blank=True, null=True)
    # seller = models.ForeignKey('ProfessionalUser.ProfessionalUser', on_delete=models.SET_NULL, null=True, blank=True, related_name="seller_tickets")
    # order = models.ForeignKey('ProfessionalUser.Order', on_delete=models.SET_NULL, null=True, blank=True)  
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)

    order = GenericForeignKey('content_type', 'object_id')
    documents = models.FileField(upload_to='ticket_attachments/', blank=True, null=True)  # For documents/images
    ticket_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    subject = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    specific_order = models.BooleanField(default=False)
    
    type_of_user = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='user')

    

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = f"TCKT-{str(uuid.uuid4()).split('-')[0].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_id} - {self.subject} ({self.status})"    

class RolePermissions(models.Model):
    rolename = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions", blank=True, null=True)
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='permissions', blank=True, null=True)

    create_permission = models.BooleanField(default=False)
    read_permission = models.BooleanField(default=False)
    update_permission = models.BooleanField(default=False)
    delete_permission = models.BooleanField(default=False)

    is_deleted = models.BooleanField(default=False)
    status = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('rolename', 'menu')  # Ensure unique role-menu permissions

    def __str__(self):
        return f"{self.rolename.id} - {self.menu.menuname if self.menu else 'No Menu'}"


class Facility(models.Model):
    name = models.CharField(max_length=255,blank=True, null=True)

    icon = models.ImageField(upload_to='icon',max_length=255, blank=True, null=True)
    is_selected = models.BooleanField(default=False)  
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    

    def __str__(self):
        return self.name




class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    ]
    status = models.CharField(
        max_length=10,
        choices=[("active", "Active"), ("inactive", "Inactive")],
        default="active"
    )
    
    couponCode = models.CharField(max_length=50, unique=True)  
    discount_type = models.CharField(max_length=50, choices=DISCOUNT_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=50, decimal_places=2)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.couponCode} - {self.discount_type} - {self.amount} - {self.status}"



class HelpCategory(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.title

class HelpFAQ(models.Model):
    category = models.ForeignKey(HelpCategory, related_name='faqs', on_delete=models.CASCADE)
    question = models.CharField(max_length=255)
    answer = models.TextField()

    def __str__(self):
        return self.question
    
class SupportOption(models.Model):
    title= models.CharField(max_length=100,null=True,blank=True)
    description = models.TextField(max_length=250,null=True,blank=True)

    def __str__(self):
        return self.title    




class ReelReport(models.Model):
    REPORT_REASONS = [
        ('spam', 'Spam or misleading'),
        ('nudity', 'Nudity or sexual content'),
        ('hate', 'Hate speech or symbols'),
        ('violence', 'Violent or dangerous content'),
        ('harassment', 'Harassment or bullying'),
        ('copyright', 'Copyright infringement'),
        ('scam', 'Scam or fraud'),
        ('misinfo', 'Misinformation'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey('UserApp.Users', on_delete=models.CASCADE, related_name='reel_reports')
    reel = models.ForeignKey('ProfessionalUser.StoreReel', on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=20, choices=REPORT_REASONS)
    other_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('reviewed', 'Reviewed')], default='pending')

    class Meta:
        verbose_name = "Reel Report"
        verbose_name_plural = "Reel Reports"
        ordering = ['-created_at']

    def __str__(self):
        return f"Report by {self.user} on Reel {self.reel.id} for {self.get_reason_display()}"



class Advertisement(models.Model):
    title = models.CharField(max_length=255,blank=True, null=True)
    image = models.ImageField(upload_to='uploads/',blank=True, null=True)
    description = models.TextField(max_length=850,null=True,blank=True)
    url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    warning_message = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.title or f"Advertisement #{self.id}"




class AdminBankAccountDetails(models.Model):
    user = models.ForeignKey(AdminUser, on_delete=models.CASCADE, related_name="bank_accounts")
    account_holder_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=20, unique=True)
    bank_name = models.CharField(max_length=255)
    branch_name = models.CharField(max_length=255, null=True, blank=True)
    branch_address = models.CharField(max_length=755, null=True, blank=True)  
    bank_address = models.CharField(max_length=755, null=True, blank=True)   
    ifsc_code = models.CharField(max_length=11, null=True, blank=True)
    iban_number = models.CharField(max_length=34, null=True, blank=True)
    swift_code = models.CharField(max_length=11, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, null=True, blank=True)
    

    def __str__(self):
        return f"{self.account_holder_name} - {self.account_number}"


# models.py

class AdminNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('registration_user', 'User Registration'),
        ('registration_pro', 'Professional Registration'),
        ('support_ticket', 'Support Ticket'),
        ('payment', 'Payment'),
        ('document_upload', 'Document Upload'),
        ('reel_report', 'Reel Report'),
        ('custom', 'Custom Message'),
    ]

    title = models.CharField(max_length=150, blank=True, null=True)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES) 
    user = models.ForeignKey('UserApp.Users',on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_notifications')
    professional_user = models.ForeignKey('ProfessionalUser.ProfessionalUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_notifications')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_notification_type_display()}] {self.title or self.message[:30]}"
    



class LegalDocument(models.Model):
    TITLE_CHOICES = [
        ("terms", "Terms and Conditions"),
        ("privacy", "Privacy Policy"),
        ("legal", "Legal Notice"),
        ("cookies", "Cookie Policy"),
        ("refund", "Refund Policy"),
        ("shipping", "Shipping Policy"),
    ]

    title = models.CharField(max_length=50, choices=TITLE_CHOICES)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    language = models.CharField(max_length=10, default='en')
    version = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return dict(self.TITLE_CHOICES).get(self.title, self.title)

