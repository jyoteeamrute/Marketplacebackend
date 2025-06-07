import random
import string
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg  # Import this
from django.db.models import F
from django.utils import timezone
from django.utils.timezone import now
from django.db.models import Q
from Admin.models import (Category, Facility, Role, Subcategory, Subscription,
                          SubscriptionPlan)
from UserApp.models import *


def validate_max_keywords(value):
        if isinstance(value, list) and len(value) > 5:
            raise ValidationError("You can only add up to 5 keywords.")

import logging

logger = logging.getLogger(__name__)

class ProfessionalUser(models.Model):
    STATUS_CHOICES = [
        ('pending', 'pending'),
        ('approved', 'approved'),
        ('rejected', 'rejected'),
    ]
    SUBSCRIPTION_STATUS_CHOICES = [
        ('inactive', 'Inactive - No plan chosen'),
        ('trial', 'Free Trial Active'),
        ('paid', 'Paid Subscription Active'),
    ]
    userName = models.CharField(max_length=255, null=True,blank=True)
    email = models.EmailField(null=True,blank=True)
    password = models.CharField(max_length=255)
    phoneCode=models.CharField(max_length=15,null=True,blank=True)
    phone = models.CharField(max_length=15)
    company = models.OneToOneField('CompanyDetails', on_delete=models.SET_NULL, null=True,blank=True)
    manual_address = models.OneToOneField('Address', on_delete=models.SET_NULL, null=True,blank=True, related_name='manual')
    automatic_address = models.OneToOneField('Address', on_delete=models.SET_NULL, null=True, blank=True,related_name='automatic')
    subscriptionplan=models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True,)
    subscriptiontype=models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True,)
    subscription_active = models.BooleanField(default=False)
    trial_start_date = models.DateTimeField(null=True, blank=True)  
    trial_end_date = models.DateTimeField(null=True, blank=True)# Free trial start date
    trial_availed = models.BooleanField(default=False) 
    categories = models.ManyToManyField(Category,   blank=True)
    subcategories = models.ManyToManyField(Subcategory, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    term_condition = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)  
    kbiss_status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')
    iban_status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')
    proofOfAddress_status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')
    identityCardFront_status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending') 
    identityCardBack_status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')
    finalDocument_status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True) 
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_attempts = models.IntegerField(default=0)
    otp_block_until = models.DateTimeField(null=True, blank=True)
    stripe_customer_id=models.CharField(max_length=50,null=True, blank=True)
    is_free_trial_active=models.BooleanField(default=False) 
    
    is_paid_subscription_active=models.BooleanField(default=False) 
    subscription_status=models.CharField(max_length=50,choices=SUBSCRIPTION_STATUS_CHOICES,default='inactive')
    last_login = models.DateTimeField(null=True, blank=True)

    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=False)

    two_factor_authentication = models.BooleanField(default=False)
    email_two_factor = models.BooleanField(default=False)
    sms_two_factor = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)  # Soft delete flag
    deleted_at = models.DateTimeField(null=True, blank=True)  

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save()


    def save(self, *args, **kwargs):
        if self.password and not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)

        if not self.role:
            self.role, _ = Role.objects.get_or_create(name="professionaluser")

        super().save(*args, **kwargs)


    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save()

    def save(self, *args, **kwargs):
        if not self.role:
            self.role, _ = Role.objects.get_or_create(name="professionaluser")
        super().save(*args, **kwargs)

    def __str__(self):
    # Check if email exists, otherwise fallback to userName or a default string
        return self.email if self.email else self.userName if self.userName else "ProfessionalUser"
    @property
    def is_authenticated(self):
        return True     
    
    def set_otp(self, otp):
        self.otp = otp
        self.otp_attempts += 1
        self.save()
    
    def verify_otp(self, otp):
        return self.otp == otp
    
    def can_generate_otp(self):
        now = timezone.now()
        if self.otp_block_until and self.otp_block_until > now:
            return False, self.otp_block_until - now
        if self.otp_attempts >= 10:
            self.otp_block_until = now + timedelta(hours=24)
            self.otp_attempts = 0
            self.save()
            return False, self.otp_block_until - now
        return True, None
    
    def reset_otp_attempts(self):
        self.otp_attempts = 0
        self.otp_block_until = None
        self.save()


#for generating the unique username
def generate_unique_company_username(company_name):
    
    base_username = company_name.lower().replace(" ", "_")  
    username = base_username

    while CompanyDetails.objects.filter(userName=username).exists():
        random_suffix = ''.join(random.choices(string.digits, k=4))  
        username = f"{base_username}_{random_suffix}"

    return username


def update_two_factor_settings(self, two_fa, email_2fa, sms_2fa):
    logger.info(f"Updating 2FA settings for user ID {self.id}")
    logger.debug(f"Input values -> two_fa: {two_fa}, email_2fa: {email_2fa}, sms_2fa: {sms_2fa}")

    # Fallbacks to current state if any are None
    two_fa = self.two_factor_authentication if two_fa is None else two_fa
    email_2fa = self.email_two_factor if email_2fa is None else email_2fa
    sms_2fa = self.sms_two_factor if sms_2fa is None else sms_2fa

    if not two_fa:
        # Enforce 2FA disabled -> turn off all methods
        logger.info("Disabling all 2FA methods")
        self.two_factor_authentication = False
        self.email_two_factor = False
        self.sms_two_factor = False
    else:
        logger.info("Enabling 2FA methods based on input")
        self.two_factor_authentication = True
        self.email_two_factor = bool(email_2fa)
        self.sms_two_factor = bool(sms_2fa)

    logger.debug(f"Final settings -> 2FA: {self.two_factor_authentication}, "
                 f"Email: {self.email_two_factor}, SMS: {self.sms_two_factor}")
    self.save()
    logger.info("2FA settings saved.")



#update the model fileds
class CompanyDetails(models.Model):
    companyName = models.CharField(max_length=255,blank=True, null=True) 
    userName = models.CharField(max_length=255, null=True, blank=True, unique=True)
    managerFullName = models.CharField(max_length=255,blank=True, null=True) 
    email= models.EmailField(unique=True,null=True,blank=True)
    manual_address = models.OneToOneField('Address', on_delete=models.SET_NULL,  null=True)
    automatic_address = models.OneToOneField('Address', on_delete=models.SET_NULL, null=True, related_name='company_automatic') 
    phoneNumber =models.CharField(max_length=15,null=True,blank=True)
    siret = models.CharField(max_length=50, unique=True,blank=True, null=True) 
    sectorofActivity = models.CharField(max_length=255,blank=True, null=True) 
    vatNumber = models.CharField(max_length=50, unique=True,blank=True, null=True) 
    kbiss = models.FileField(upload_to='uploads/company_documents',blank=True,null=True) 
    iban = models.FileField(upload_to='company_documents',blank=True,null=True) 
    identityCardFront = models.FileField(upload_to='company_documents', blank=True, null=True)
    identityCardBack = models.FileField(upload_to='company_documents', blank=True, null=True)
    proofOfAddress = models.FileField(upload_to='company_images',blank=True,null=True)
    profilePhoto=models.ImageField(upload_to='company_images',blank=True,null=True)
    coverPhotos = models.JSONField(default=list,blank=True, null=True)  
    # facilities = models.JSONField(default=list,blank=True, null=True)
    selectedCoverPhoto = models.CharField(max_length=500, blank=True, null=True) 
    facilities = models.ManyToManyField(Facility, blank=True, related_name="companies_facility")
    categories = models.ManyToManyField(Category, blank=True, related_name="companies_category")
    subcategories = models.ManyToManyField(Subcategory, blank=True, related_name="companies_subcategory")
    onsite=models.BooleanField(default=False)
    clickcollect=models.BooleanField(default=False)
    on_site_ordering = models.JSONField(default=list,blank=True, null=True) 
    minimum_order_quantity = models.IntegerField(null=True, blank=True) 
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    free_cancellation_policy = models.TextField(blank=True, null=True)
    is_free_cancellation_available = models.BooleanField(default=False)
    hours_before_cancellation = models.IntegerField(default=0)
    opening_hours = models.JSONField(default=dict, blank=True, null=True)
    isActive = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)  
    updated_at = models.DateTimeField(auto_now=True)  
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_ratings = models.PositiveIntegerField(default=0)
    total_visits = models.PositiveIntegerField(default=0) 
    warning_message = models.CharField(max_length=255, null=True, blank=True)

    def update_rating(self):
        """Update company rating based on reviews"""
        ratings = self.reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
        new_avg_rating = ratings or 0
        new_total_ratings = self.reviews.count()

        # Only update if values changed
        if self.average_rating != new_avg_rating or self.total_ratings != new_total_ratings:
            self.average_rating = new_avg_rating
            self.total_ratings = new_total_ratings
            self.save(update_fields=['average_rating', 'total_ratings'])

    
    
    def save(self, *args, **kwargs):
        
        if not self.userName or CompanyDetails.objects.filter(userName=self.userName).exclude(id=self.id).exists():
            self.userName = generate_unique_company_username(self.companyName)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.companyName

#Company visits
class CompanyVisit(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE)
    visited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'company')
#comapny Follow
class Follow(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE)
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'company')
        
#Company Review
class CompanyReview(models.Model):
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    review_text = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        unique_together = ('company', 'user')  # Prevent duplicate reviews

    def save(self, *args, **kwargs):
        """Validate rating before saving & update company rating"""
        if not (1 <= self.rating <= 5):
            raise ValueError("Rating must be between 1 and 5.")
        
        super().save(*args, **kwargs)
        self.company.update_rating()  # Update rating after saving

    def delete(self, *args, **kwargs):
        """Update company's average rating after deleting review"""
        super().delete(*args, **kwargs)
        self.company.update_rating()

    def __str__(self):
        return f"Review for {self.company.companyName} by {self.user.email}"
    
    
class CategoryFolder(models.Model):
    PRODUCT_TYPE_CHOICES  = [ 
        ('Product', 'product'),
        ('Services', 'services'),
        ('Ticket', 'ticket'),
    ]
    professionalUser = models.ForeignKey(ProfessionalUser, on_delete=models.SET_NULL, null=True, blank=True,related_name="category_folders")
    name = models.CharField(max_length=255)
    productType = models.CharField(max_length=20,choices=PRODUCT_TYPE_CHOICES ,default='product_type')
    categories = models.ManyToManyField(Category,blank=True, related_name="product_category_folder")  
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    
class CruiseFacility(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    icon = models.ImageField(upload_to='icon', max_length=255, blank=True, null=True)
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.name    
    
class RoomFacility(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    icon = models.ImageField(upload_to='icon', max_length=255, blank=True, null=True)
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
 
    def __str__(self):
        return self.name 
  
 
     
# product model
class Product(models.Model):
    productType = [ 
    ('Product', 'product'),
    ('Services', 'services'),
    ('Ticket', 'ticket'),
]
    company = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL, null=True, blank=True)   
    folder = models.ForeignKey(CategoryFolder, on_delete=models.SET_NULL, null=True, blank=True,related_name="products_folder")
    categoryId = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True,blank=True)
    subCategoryId = models.ForeignKey(Subcategory,on_delete=models.SET_NULL, null=True,blank=True)
    productname = models.CharField(max_length=255,blank=True, null=True)
    productType = models.CharField(max_length=20,choices=productType,default='product' ,blank=True, null=True)
    description = models.TextField(max_length=255,blank=True, null=True)
    priceOnsite = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    priceClickAndCollect = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    priceDelivery = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=0, blank=True, null=True)
    vatRate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True) 
    promotionalPrice = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    deliveryMethod = models.CharField(max_length=255, blank=True, null=True)  
    deliveryPricePerGram = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    preparationDateTime = models.DateTimeField(blank=True, null=True)
    availabilityDateTime = models.DateTimeField(null=True, blank=True)
    bookedQuantity = models.PositiveIntegerField(default=0, blank=True, null=True)
    
    #-------------new field added ------
    
    onDelivery = models.BooleanField(default=False, blank=True, null=True)
    onsite = models.BooleanField(default=False, blank=True, null=True)
    clickandCollect = models.BooleanField(default=False, blank=True, null=True)
    
    serviceTime= models.PositiveIntegerField(blank=True, null=True)
    basePrice = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    nonRestaurant = models.BooleanField(default=False, blank=True, null=True)
    delivery = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    #----------------------------------------
    keywords = models.JSONField(validators=[validate_max_keywords], blank=True, null=True)  
    ProductImage = models.ImageField(upload_to='product_images', blank=True,null=True, max_length=500 )
    galleryImage = models.JSONField(default=list, blank=True,null=True)
    isActive = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)  
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)  
    discount = models.PositiveIntegerField(blank=True, null=True)    
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_ratings = models.PositiveIntegerField(default=0)
    onhome=models.BooleanField(default=False, blank=True, null=True)
    totalEmployees = models.PositiveIntegerField(default=0, blank=True, null=True)
    
    # -------------------------cruise ------------------------
    duration=models.PositiveIntegerField(blank=True, null=True,default=0)  
    startAddress = models.OneToOneField(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name='cruise_start_address')
    endAddress = models.OneToOneField(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name='cruise_end_address')
    petAllowed = models.BooleanField(default=False, blank=True, null=True)
    petType = models.JSONField(blank=True, null=True)
    cruiseName = models.CharField(max_length=255, blank=True, null=True)
    cruiseFacility = models.ManyToManyField(CruiseFacility, blank=True,related_name="cruise_facility")
    
    
    #----------------------hotels--------------
    roomFacility = models.ManyToManyField(RoomFacility, blank=True, related_name="facility")
    smokingAllowed=models.BooleanField(default=False)
    noofMembers= models.PositiveIntegerField(blank=True, null=True)   
    roomview= models.JSONField(blank=True, null=True)
    
    #-------------------------------Concert ticket--------------------------------
    artistName= models.JSONField(blank=True, null=True)
    bandName= models.JSONField(blank=True, null=True)
    startTime = models.TimeField(blank=True, null=True)
    endTime = models.TimeField(blank=True, null=True)
    # concertTicket = models.ManyToManyField(TicketsConcert, blank=True, related_name="concert_ticket")
    
    #-----------------------------nightclub--------------
    
    
    
    
    def update_rating(self):
        """Update product rating based on reviews"""
        ratings = self.reviews.all()
        if ratings.exists():
            self.average_rating = ratings.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
            self.total_ratings = ratings.count()
        else:
            self.average_rating = 0
            self.total_ratings = 0
        self.save()

    def __str__(self):
        return self.productname if self.productname else "Unnamed Product"
    def get_price_by_order_type(self, order_type):
        if order_type == 'Onsite':
            return self.promotionalPrice
        elif order_type == 'Click and Collect':
            return self.priceClickAndCollect
        elif order_type == 'Delivery':
            return self.priceDelivery
        return self.promotionalPrice
    
 

class TicketsConcert(models.Model):
    
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(max_length=255, blank=True, null=True)
    members = models.PositiveIntegerField(default=0, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=0, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
 
    def __str__(self):
        return self.name 
        
class NightClubTicket(models.Model):
    
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    # tableNo = models.PositiveIntegerField(default=0, blank=True, null=True)
    tableName = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(max_length=255, blank=True, null=True)
    members = models.PositiveIntegerField(default=0, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=0, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
 
    def __str__(self):
        return self.product.productname 

class TicketsAmusementPark(models.Model):
    
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(max_length=255, blank=True, null=True)
    adultPrice = models.PositiveIntegerField(default=0, blank=True, null=True)
    childPrice = models.PositiveIntegerField(default=0, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
 
    def __str__(self):
        return self.name 
    

class LoyaltyCard(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='loyalty_cards')
    company = models.ForeignKey(CompanyDetails, null=True, on_delete=models.CASCADE, related_name='loyalty_cards')
    status = models.BooleanField(default=True)
    threshold_point = models.PositiveIntegerField()
    
    def __str__(self):
        return f"{self.product.productname}"



class DeliveryService(models.Model):
    SERVICE_CHOICES = [
        ('catering', 'Catering Delivery'),
        ('home_services', 'Home Services'),
    ]
    
    company = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL,null=True,blank=True, related_name="delivery_charges")
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES)
    is_enabled = models.BooleanField(default=False)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    travel_fee_per_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
     
    def save(self, *args, **kwargs):
        """ Ensure correct fields are filled based on service type """
        if self.service_type == 'catering':
            if self.travel_fee_per_km is not None:
                self.travel_fee_per_km = None  # Remove unnecessary field
        elif self.service_type == 'home_services':
            if self.delivery_fee is not None or self.minimum_order_amount is not None:
                self.delivery_fee = None
                self.minimum_order_amount = None
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_service_type_display()} ({'Enabled' if self.is_enabled else 'Disabled'})"


# service model    
class Service(models.Model):
    productType = [ 
    ('Product', 'product'),
    ('Services', 'services'),
    ('Ticket', 'ticket'),
]
    company = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL, null=True, blank=True)
    categoryId = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    subCategoryId = models.ForeignKey(Subcategory, on_delete=models.SET_NULL, null=True, blank=True)
    productType = models.CharField(max_length=20,choices=productType,default='service')
    productname = models.CharField(max_length=255,null=True)
    priceOnsite = models.DecimalField(max_digits=10, decimal_places=2)
    priceAtHome = models.DecimalField(max_digits=10, decimal_places=2)
    priceClickAndCollect = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    availabilityDateTime = models.DateTimeField(null=True, blank=True) 
    vatRate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=0,null=True)
    description = models.TextField(max_length=255, blank=True, null=True)
    keywords = models.JSONField(validators=[validate_max_keywords], blank=True, null=True)   
    preparationTime = models.PositiveIntegerField(blank=True, null=True)  
    ServiceImage = models.ImageField(upload_to='product_images', blank=True,null=True, max_length=500 ) 
    galleryImage = models.JSONField(default=list, blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.productname if self.productname else "Unnamed Product"


# ticket model
class Ticket(models.Model):
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, related_name="tickets",null=True, blank=True)
    subCategoryId = models.ForeignKey(Subcategory, on_delete=models.SET_NULL, related_name="tickets",null=True, blank=True)
    ticketName = models.CharField(max_length=255,null=True)
    description = models.TextField(max_length=255,blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=0, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.ticketName if self.ticketName else "Unnamed Product"

class Address(models.Model):
    address1 = models.CharField(max_length=255,blank=True, null=False)
    address2 = models.CharField(max_length=255, blank=True, null=True)
    postalCode = models.CharField(max_length=20, null=False)
    lat = models.CharField(max_length=50, blank=True, null=True)
    lang = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=100, null=False,blank=True,)
    country = models.CharField(max_length=100, null=False,blank=True,)
    state = models.CharField(max_length=100, null=True,blank=True,)
    countryCode = models.CharField(max_length=100, null=True,blank=True,)
    dialCode = models.CharField(max_length=100, null=True,blank=True,) # dial code


    def __str__(self):
        return f"{self.address1}, {self.city}, {self.country}"
    
 
 
# store reels  
class StoreReel(models.Model):
    company_id = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL, related_name='store_reels', null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    subcategory = models.ForeignKey(Subcategory, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    video = models.FileField(upload_to='reels/videos/', blank=True, null=True)
    thumbnail = models.ImageField(upload_to='reels/thumbnails/', blank=True, null=True)  
    m3u8_url = models.URLField(blank=True, null=True)
    views = models.PositiveIntegerField(default=0)  
    likes = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    isActive = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def increment_view_count(self):
        self.views += 1
        self.save(update_fields=['views'])

    def increment_share_count(self):
        self.shares += 1
        self.save(update_fields=['shares'])

    def toggle_like(self, user):
        like_obj, created = ReelLike.objects.get_or_create(user=user, reel=self)

        if not created:
            like_obj.delete()

        updated_likes_count = ReelLike.objects.filter(reel=self).count()
        
        StoreReel.objects.filter(id=self.id).update(likes=updated_likes_count)

        self.refresh_from_db()

        return created  

    def __str__(self):
        company_name = self.company_id.companyName if self.company_id else "No Company"
        return f"{self.title or 'Untitled Reel'} - {company_name}"
    
    
# reels like
class ReelLike(models.Model):
    user = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True, blank=True)
    reel = models.ForeignKey(StoreReel, on_delete=models.SET_NULL, related_name="reel_likes", null=True, blank=True)
    is_liked = models.BooleanField(default=True)  
    
    class Meta:
        unique_together = ('user', 'reel')  # Ensures a user can only like/unlike once

    def __str__(self):
        return f"{self.user.username} - Liked"    

#reel views
class ReelView(models.Model):
    user = models.ForeignKey(Users, on_delete=models.SET_NULL, blank=True, null=True)
    reel = models.ForeignKey(StoreReel, on_delete=models.SET_NULL, blank=True, null=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} viewed {self.reel}"

#reel comment
class ReelComment(models.Model):
    user = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True, blank=True)
    reel = models.ForeignKey(StoreReel, on_delete=models.SET_NULL, related_name="reel_comments", null=True, blank=True)
    comment = models.TextField()
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="replies")  
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(Users, related_name="comment_likes", blank=True) 

    def get_is_store_reply(self):
        """Check if the comment belongs to a store."""
        try:
            store = self.reel.company_store  # Get store from reel
            return self.user == store.user if store else False  # Check if comment user is store owner
        except AttributeError:
            return False

    def save(self, *args, **kwargs):
        is_new = self._state.adding  # Check if new comment
        super().save(*args, **kwargs)
        if is_new:
            StoreReel.objects.filter(id=self.reel.id).update(comments=F("comments") + 1)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        StoreReel.objects.filter(id=self.reel.id).update(comments=F("comments") - 1)

    def __str__(self):
        return f"{self.user.username if self.user else 'Deleted User'} - {self.comment[:20]}"
 
# reel share
class ReelShare(models.Model):
    SHARE_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter'),
        ('direct', 'Direct Share'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(Users, on_delete=models.SET_NULL, related_name="shared_reels", null=True, blank=True)  # Who shared  
    reel = models.ForeignKey(StoreReel, on_delete=models.SET_NULL, related_name="shares_detail", null=True, blank=True)  # Reel shared  
    recipient_user = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_reels")  # Who received it (if internal)  
    share_method = models.CharField(max_length=20, choices=SHARE_CHOICES, default='direct')  
    shared_at = models.DateTimeField(auto_now_add=True)  

    def clean(self):
        if not self.user and not self.recipient_user:
            raise ValidationError("Either 'user' or 'recipient_user' must be provided.")

        if self.user and self.recipient_user and self.user == self.recipient_user:
            raise ValidationError("A user cannot share a reel with themselves.")

    def save(self, *args, **kwargs):
        is_new = self._state.adding  # Check if it's a new share
        super().save(*args, **kwargs)
        if is_new:
            StoreReel.objects.filter(id=self.reel.id).update(shares=F("shares") + 1)  # Increment shares

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        StoreReel.objects.filter(id=self.reel.id).update(shares=F("shares") - 1)  # Decrement shares

    def __str__(self):
        sender = self.user.username if self.user else "Unknown User"
        reel_title = self.reel.title if self.reel else "Unknown Reel"
        if self.recipient_user:
            return f"{sender} shared '{reel_title}' with {self.recipient_user.username}"
        return f"{sender} shared '{reel_title}' via {self.share_method}'"

# store image 

from Admin.models import Category


class StoreImage(models.Model):
    company_id = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL, related_name='store_images', null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    subcategory = models.ForeignKey(Subcategory, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=600, blank=True, null=True)
    image = models.ImageField(upload_to='store_images/',blank=True, null=True)
    isActive = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    
    def __str__(self):
        return f"Image for Store {self.company_id.companyName}" if self.company_id else "Image for Store (No Company)"
    

#review model
class Review(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="reviews", on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Override save method to update product rating"""
        super().save(*args, **kwargs)
        self.product.update_rating()

    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"Review by {self.user} for {self.product.productname}"

 

    
# campaign model
class Campaign(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    Goal_CHOICES = [
        ('attract followers', 'ATTRACT FOLLOWERS'),
        ('generate messages', 'GENERATE MESSAGES'),
        ('drive purchase', 'DRIVE PURCHASE'),
    ]
    company = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL, null=True, blank=True) 
    name=models.CharField(max_length=255)
    description=models.CharField(max_length=255,null=True)
    image=models.ImageField(upload_to='campaign_images')
    startdate=models.DateTimeField(null=True)
    enddate=models.DateTimeField(null=True)
    starttime=models.DateTimeField(null=True)
    endtime=models.DateTimeField(null=True)
    goal=models.CharField(max_length=20,choices=Goal_CHOICES, blank=True, null=True)
    city_country=models.CharField(max_length=255)
    Age=models.IntegerField(blank=True, null=True)
    gender= models.CharField(max_length=20,choices=GENDER_CHOICES, blank=True, null=True)
    category= models.ForeignKey(Category, on_delete=models.SET_NULL, null=True ,related_name="campaign")
    dailyBudget=models.IntegerField(blank=True, null=True)
    CampaignDuration=models.IntegerField(blank=True, null=True)
    PauseCampaign=models.BooleanField(default=False)

# store the company store product
  
class StoreEvent(models.Model):
    company = models.ForeignKey(
        CompanyDetails, on_delete=models.SET_NULL, related_name='store_events', null=True, blank=True
    )
    eventTitle = models.CharField(max_length=255,blank=True, null=True)
    eventImage = models.ImageField(upload_to='event_images/', blank=True, null=True)
    startDate = models.DateField(blank=True, null=True)
    endDate = models.DateField(blank=True, null=True)
    startTime = models.TimeField(blank=True, null=True)
    endTime = models.TimeField(blank=True, null=True)
    eventAddress = models.OneToOneField(
        'Address', on_delete=models.SET_NULL, null=True, blank=True, related_name='event_address'
    )
    description = models.TextField(max_length=500,blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.eventTitle} ({self.startDate})"
   
   
# new orders model
class NewOrders(models.Model):
    STATUS_CHOICES = choices=[
        ("accepted", "Accepted"), 
        ("created", "Created"),
        ("paid", "Paid"), 
        ("pending", "Pending"),
        ("on hold", "On Hold"),
        ("completed", "Completed"), 
        ("cancelled", "Cancelled")
        ]
    # company_store = models.ForeignKey(CompanyStore, on_delete=models.SET_NULL, null=True, blank=True)
    customerName = models.CharField(max_length=255)
    customerEmail = models.EmailField(null=True,blank=True)
    orderDate = models.DateTimeField(auto_now_add=True)
    orderPrice = models.DecimalField(max_digits=10, decimal_places=2)
    orderStatus = models.CharField(max_length=50, choices=STATUS_CHOICES, default="Pending")
    cancellation_deadline = models.DateTimeField(null=True, blank=True)
    createdAt = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Set cancellation deadline based on store settings."""
        if not self.cancellation_deadline and self.company_store:
            if self.company_store.is_free_cancellation_available:
                self.cancellation_deadline = now() + timedelta(minutes=self.company_store.hours_before_cancellation)
            else:
                self.cancellation_deadline = None  # No free cancellation allowed

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.id} - {self.customerName}"

# preparation time for orders
class PreparationTime(models.Model):
    
    newOrder = models.OneToOneField(
        NewOrders, on_delete=models.SET_NULL, related_name="preparation_time" ,null=True,blank=True
    )
    onSiteTime = models.PositiveIntegerField(blank=True, null=True)
    clickCollectTime = models.PositiveIntegerField(blank=True, null=True)
    deliveryPrepTime = models.PositiveIntegerField(blank=True, null=True)
    productClickCollectTime = models.PositiveIntegerField(blank=True, null=True)
    productDeliveryTime = models.PositiveIntegerField(blank=True, null=True)
    serviceDuration = models.PositiveIntegerField(blank=True, null=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preparation Details for Order {self.newOrder.id}"
    
    
# reservation model
class TableReservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ("on hold", "On Hold"),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]
    # company_store = models.ForeignKey(CompanyStore, on_delete=models.SET_NULL, null=True, blank=True)
    customerName = models.CharField(max_length=255)
    contactInfo = models.CharField(max_length=255)
    reservationDate = models.DateField()
    timeSlot = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Reservation #{self.id} - {self.customerName} ({self.get_status_display()})"
    
class Promotions(models.Model):
    PRODUCT_SERVICE_CHOICES = [
        ('product', 'Product'),
        ('services', 'Services'),
        ('ticket', 'Ticket'),
    ]

    product_service_type = models.CharField(max_length=20, choices=PRODUCT_SERVICE_CHOICES, default='product')
    company = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL, null=True, blank=True)
    # productId = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    productId = models.ManyToManyField(Product, blank=True)


    promotionName = models.CharField(max_length=255)
    promotionDescription = models.CharField(max_length=255, null=True, blank=True)
    image = models.ImageField(upload_to='promotions/', null=True, blank=True)

    discountAmount = models.CharField(max_length=255, null=True, blank=True)

    
    startDateTime = models.DateTimeField(null=True, blank=True)
    endDateTime = models.DateTimeField(null=True, blank=True)
    created_at=models.DateTimeField(auto_now_add=True, blank=True, null=True) 

    def __str__(self):
        return self.promotionName
    
class Invoice(models.Model):
    # companyStore = models.ForeignKey(CompanyStore, on_delete=models.SET_NULL, null=True, blank=True) 
    customer_name = models.CharField(max_length=255)
    product_service = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Tax rate in percentage")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    def save(self, *args, **kwargs):
        """Auto-calculate totalAmount before saving"""
        if self.quantity and self.unit_price and self.tax_rate is not None:
            subtotal = self.quantity * self.unit_price
            tax_amount = (subtotal * self.tax_rate) / 100
            self.total_amount = subtotal + tax_amount  
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Invoice for {self.customer_name} - {self.product_service}"


class Promocode (models.Model):
    company = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL, null=True, blank=True)   
    promocode=models.CharField(max_length=255, unique=True ,null=True,blank=True)
    title = models.CharField(max_length=255, null=True,blank=True)
    description=models.CharField(max_length=255,null=True,blank=True)
    image=models.ImageField(upload_to='Promocode_images',null=True,blank=True)
    specificAmount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    startDateTime = models.DateTimeField(null=True, blank=True)
    endDateTime = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.promocode or f"Promocode {self.id}"

    
    class Meta:
        unique_together = ('promocode', 'company') 
    

from django.db.models.signals import post_save
from django.dispatch import receiver


class Inventory(models.Model):
    company = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL,blank=True, null=True)
    product = models.OneToOneField(Product, on_delete=models.SET_NULL, related_name="inventory",blank=True, null=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    medium_stock_threshold = models.PositiveIntegerField(default=10)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    last_updated = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Update Product quantity & check low stock"""
        super().save(*args, **kwargs)
        self.product.quantity = self.stock_quantity
        self.product.save(update_fields=["quantity"])

    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    def __str__(self):
        return f"{self.product.productname} - {self.stock_quantity} left" 
    
@receiver(post_save, sender=Product)
def update_inventory_stock(sender, instance, **kwargs):
    """Update inventory stock when product quantity changes."""
    inventory = Inventory.objects.filter(product=instance).first()
    if inventory and inventory.stock_quantity != instance.quantity:
        Inventory.objects.filter(id=inventory.id).update(stock_quantity=instance.quantity)


class Cart(models.Model):
    ORDER_TYPES = [
    ('Onsite', 'onsite'),
    ('Click and Collect', 'ClickandCollect'),
    ('Delivery', 'delivery')
]
    user = models.ForeignKey(Users, on_delete=models.SET_NULL,null=True,blank=True)
    company = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL,null=True,blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL,null=True,blank=True)
    quantity = models.PositiveIntegerField(default=0,null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, null=True, blank=True)
    promo_code = models.ForeignKey(Promocode, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.TextField(null=True, blank=True)
    date = models.DateField(null=True, blank=True) 
    time = models.TimeField(null=True, blank=True)
    members = models.IntegerField(null=True, blank=True)
    customer_name = models.CharField(max_length=100, null=True, blank=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.ForeignKey(userAddress, null=True, blank=True, on_delete=models.SET_NULL)
    manual_address = models.JSONField(null=True, blank=True)

    def get_item_total(self):
        if self.product:
            price = self.product.get_price_by_order_type(self.order_type)
            return float(price or 0) * (self.quantity or 0)
        return 0.0

    def __str__(self):
        return f"{self.user}"
    

class Order(models.Model):
    STATUS_CHOICES = choices=[
        ("accepted", "Accepted"), 
        ("processing", "Processing"),
        ("cancelled", "Cancelled"),
        ("fulfilled", "Fulfilled"),
        ("new order", "New Order"),
        ("paid", "Paid"),
        
        
        ]
    ORDER_TYPES = [
        ('Onsite', 'onsite'),
        ('Click and Collect', 'ClickandCollect'),
        ('Delivery', 'delivery')
    ]

    CANCEL_REASONS = [
        ('service_delay', 'Service Delay'),
        ('wrong_item_ordered', 'Wrong Item Ordered'),
        ('found_better_price', 'Found a Better Price'),
        ('changed_mind', 'Changed Mind'),
        ('delivery_too_slow', 'Delivery Took Too Long'),
        ('order_placed_by_mistake', 'Order Placed by Mistake'),
        ('duplicate_order', 'Duplicate Order'),
        ('incorrect_address', 'Incorrect Address Provided'),
        ('other', 'Other'),
    ]
    
    USER_TYPE_CHOICES = [
        ('user', 'User'),
        ('professionaluser', 'ProfessionalUser'),
    ]
    order_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE, blank=True, null=True)
    cart_items = models.ManyToManyField(Cart, blank=True, related_name='orders')  
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE,null=True, blank=True, related_name="orders")
    orderStatus = models.CharField(max_length=50, choices=STATUS_CHOICES, default="new order") 
    order_type = models.CharField(max_length=20, choices=ORDER_TYPES, null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) 
    onSitePreparationTime = models.TimeField(null=True, blank=True)
    clickCollectPreparationTime = models.TimeField(null=True, blank=True)
    deliveryPreparationTime = models.TimeField(null=True, blank=True)
    clickCollectTime = models.TimeField(null=True, blank=True)
    deliveryTime = models.TimeField(null=True, blank=True)
    serviceDuration = models.TimeField(null=True, blank=True)    
    is_paid=models.BooleanField(default=False)
    promo_code =  models.ForeignKey(Promocode, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.TextField(null=True, blank=True)
    date = models.DateField(null=True, blank=True) 
    time = models.TimeField(null=True, blank=True)
    members = models.IntegerField(null=True, blank=True)
    customer_name = models.CharField(max_length=100, null=True, blank=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    address = models.ForeignKey(Address, null=True, blank=True, on_delete=models.SET_NULL)
    user_address = models.ForeignKey(userAddress, null=True, blank=True, on_delete=models.SET_NULL)
    manual_address = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now_add=True,null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    invoice_number = models.CharField(max_length=30, unique=True, null=True, blank=True)
    cancel_reasons = models.CharField( max_length=50, choices=CANCEL_REASONS, null=True, blank=True )
    cancel_by = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default=None,null=True, blank=True)

    
    def __str__(self):
        return f"Order {self.id} "
    def save(self, *args, **kwargs):
        if not self.order_id:
            # You can customize this pattern as needed
            prefix = 'ORD'
            uid = uuid.uuid4().hex[:6].upper()
            self.order_id = f"{prefix}-{uid}"
        super().save(*args, **kwargs)

    

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  
    created_at = models.DateTimeField(auto_now_add=True)
    

    def __str__(self):
        return f"({self.quantity})"
    

class ReelFolder(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name')  

    def __str__(self):
        return f"{self.user.username} - {self.name}"

class SavedReel(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    reel = models.ForeignKey(StoreReel, on_delete=models.CASCADE)
    folder = models.ForeignKey(ReelFolder, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True,null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.reel.title} in {self.folder.name}"


class Friendship(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("follow","Followed"),
        ('unfollow',"unfollow"),
        ("message", "Message") 
    ]

    RELATIONSHIP_CHOICES = [
        ("friend", "Friend"),
        ("follow", "Follow")
    ]

    sender_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="friendship_sender")
    sender_object_id = models.PositiveIntegerField()
    sender = GenericForeignKey("sender_content_type", "sender_object_id")

    receiver_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="friendship_receiver")
    receiver_object_id = models.PositiveIntegerField()
    receiver = GenericForeignKey("receiver_content_type", "receiver_object_id")

    relationship_type = models.CharField(max_length=10, choices=RELATIONSHIP_CHOICES, default="friend")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("sender_content_type", "sender_object_id", "receiver_content_type", "receiver_object_id", "relationship_type")

    def accept(self):
        self.status = "accepted"
        self.save()

    def decline(self):
        self.status = "declined"
        self.save()


class PerformanceMetrics(models.Model):
    professional_user = models.OneToOneField(ProfessionalUser, on_delete=models.CASCADE, related_name="metrics")
    total_visits = models.PositiveIntegerField(default=0)  # Track profile/store visits
    unique_visitors = models.ManyToManyField(Users, related_name="visited_profiles", blank=True)  # Track unique visitors
    total_completed_orders = models.PositiveIntegerField(default=0)  # Successful purchases
    total_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Total sales revenue

    @property
    def conversion_rate(self):
        if self.total_visits > 0:
            return round((self.total_completed_orders / self.total_visits) * 100, 2)
        return 0.0  # Avoid division by zero

    def __str__(self):
        return f"Metrics for {self.professional_user.userName}"


# new model for dashbord




class Message(models.Model):
    sender = models.ForeignKey(Users, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(ProfessionalUser, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return f"Message to {self.recipient} from {self.sender}"
    




class AdvertiseCampaign(models.Model):
    OBJECTIVE_CHOICES = [
        ('followers', 'Followers'),
        ('messages', 'Messages'),
        ('purchases', 'Purchases'),
    ]

    AD_TYPE_CHOICES = [
        ('Listing', 'listing'),
        ('video_story', 'Video_Story'),
        ('ad', 'Ad'),
    ]

    BID_TYPE_CHOICES = [
        ('cpc', 'CPC'),
        ('cpm', 'CPM'),
    ]
    
    # AGE_RANGE_CHOICES = [
    #     ('18-24', '18-24'),
    #     ('25-34', '25-34'),
    #     ('35-44', '35-44'),
    #     ('45-54', '45-54'),
    #     ('55+', '55+'),
    # ]

    GENDER_CHOICES = [
        ('Male', 'male'),
        ('Female', 'female'),
        ('All', 'all'),
    ]
    PLACEMENT_CHOICES = [
            ('home', 'Home'),
            ('search', 'Search'),
        ]
    AUDIENCE_CHOICES = [
        ('All', 'all'),
        ('New', 'new'),
    ]
    
    TARGETING_TYPE_CHOICES = [
        ('Automatic', 'automatic'),
        ('Personalized', 'personalized'),
    ]

    product = models.ForeignKey(Product, on_delete=models.SET_NULL,null=True,blank=True)
    company = models.ForeignKey(CompanyDetails, on_delete=models.SET_NULL,null=True,blank=True)
    title = models.CharField(max_length=255, blank=True, null=True,)
    description = models.CharField(max_length=500, blank=True, null=True,)
    objective = models.CharField(max_length=20, choices=OBJECTIVE_CHOICES)
    ad_type = models.CharField(max_length=20, choices=AD_TYPE_CHOICES)
    content = models.FileField(upload_to='campaign_uploads/',null=True,blank=True)
    bid_type = models.CharField(max_length=10, choices=BID_TYPE_CHOICES)
    max_bid = models.DecimalField(max_digits=10, decimal_places=2)

    placement = models.CharField(max_length=10, choices=PLACEMENT_CHOICES, null=True, blank=True)
    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, null=True, blank=True)

    #-------------------- budget -------------
    daily_budget = models.DecimalField(max_digits=10, decimal_places=2,null=True,blank=True)
    duration_days = models.PositiveIntegerField(default=0)
    startDateTime = models.DateTimeField(null=True)
    endDateTime = models.DateTimeField(null=True)
    #---------------------------------------
    target_type = models.CharField(max_length=20, choices=TARGETING_TYPE_CHOICES, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True, help_text="Enter cities or countries")
    age_range = models.CharField(max_length=20, blank=True, null=True)

    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    preferences = models.ManyToManyField(Category, blank=True, help_text="Only show categories selected by the user")
    #-------- analysis CPC, CPM ----------------------- 
    today_clicks = models.PositiveIntegerField(default=0)
    today_impressions = models.PositiveIntegerField(default=0)
    total_conversions = models.IntegerField(default=0)
    last_updated = models.DateTimeField(default=timezone.now)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Campaign {self.pk}"



class AdImpression(models.Model):
    campaign = models.ForeignKey(AdvertiseCampaign, on_delete=models.CASCADE, related_name='impressions')
    user = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class AdClick(models.Model):
    campaign = models.ForeignKey(AdvertiseCampaign, on_delete=models.CASCADE, related_name='clicks')
    user = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)





class AdConversion(models.Model):
    campaign = models.ForeignKey(AdvertiseCampaign, on_delete=models.CASCADE, related_name='conversions')
    user = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    conversion_type = models.CharField(max_length=100, blank=True, null=True)  # e.g., "purchase", "signup"
    details = models.JSONField(blank=True, null=True)  # Optional: Store metadata about the conversion

    def __str__(self):
        return f"Conversion for Campaign {self.campaign.id} on {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class Offer(models.Model):
    OFFERS_TYPE_CHOICES = [
        ('discount', 'Discount'),
        ('free', 'Free'),
    ]

    DISCOUNT_TYPE_CHOICES = [
        ('amount', 'Amount'),
        ('free', 'Free'),
    ]

    offers_type = models.CharField(max_length=50, choices=OFFERS_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    specific_discount_type = models.CharField(max_length=50, choices=DISCOUNT_TYPE_CHOICES)
    specificAmount = models.PositiveIntegerField(null=True, blank=True)  # Only required if discount type is amount
    description = models.TextField()
    image = models.ImageField(upload_to='offers_images/', null=True, blank=True)
    
    startDateTime = models.DateTimeField(null=True, blank=True)
    endDateTime = models.DateTimeField(null=True, blank=True)

    users = models.ManyToManyField(Users, blank=True, help_text="Users who reviewed the offer")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title



class Employee(models.Model):
    ROLE_CHOICES = (
        ('manager', 'Manager'),
        ('employee', 'Employee'),
        ('admin', 'Admin'),
        ('delivery boy','Delivery Boy')
    )
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    company=models.ForeignKey(CompanyDetails,on_delete=models.CASCADE,null=True,blank=True)
    address = models.TextField()
    email = models.EmailField(unique=True)
    contact_no = models.CharField(max_length=15)
    idcard=models.FileField(upload_to='uploads/employee', blank=True, null=True)
    image = models.ImageField(upload_to='uploads/employee', blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)


    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    


class professionalFeedback(models.Model):
    user=models.ForeignKey(ProfessionalUser,on_delete=models.SET_NULL,null=True,blank=True)
    title = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(max_length=250)
    media = models.FileField(upload_to='uploads/', null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    
    
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('comment', 'Comment'),
        ('like', 'Like'),
        ('follow', 'Follow'),
        ('share', 'Share'), 
        ('order','Order'),
        ('booking','Booking')  
    ]
    #image 
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='notifications',null=True,blank=True)
    professional_user = models.ForeignKey(ProfessionalUser, on_delete=models.CASCADE, null=True, blank=True)
    sender = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='sent_notifications')
    title = models.CharField(max_length=100, null=True, blank=True)
    message = models.TextField(max_length=250, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)

    def __str__(self):
        return f"{self.sender} -> {self.user}: {self.message}"



class LoyaltyPoint(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name="loyalty_points")
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE, related_name="loyalty_points")
    total_points = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'company')  # Prevent duplicate entries

    def __str__(self):
        return f"{self.user} - {self.company}: {self.total_points} points"
    
class CruiseRoom(models.Model):
   
    ROOM_TYPE_CHOICES = [
    ("1", "Interior Room"),
    ("2", "Ocean View Room"),
    ("3", "Balcony Room"),
    ("4", "Suite"),
    ("5", "Mini Suite"),
    ("6", "Family Suite"),
    ("7", "Penthouse Suite"),
    ("8", "Twin Room With Balcony"),
    ("9", "Deluxe Suite"),
    ("10", "Accessible Room"),
]
   
    product = models.ForeignKey(Product, related_name="rooms", on_delete=models.CASCADE)
    room_id = models.CharField(max_length=50, unique=True)
    roomType = models.CharField(max_length=255,choices=ROOM_TYPE_CHOICES,blank=True,null=True)
    roomQuantity = models.PositiveIntegerField(default=1,blank=True,null=True)
    bookedQuantity= models.PositiveIntegerField(default=0,blank=True,null=True)
    roomPrice = models.DecimalField(max_digits=10, decimal_places=2,blank=True,null=True)
    adults = models.PositiveIntegerField(default=0,blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
 
    def __str__(self):
        return self.room_id    

class RoomBooking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('rejected','Rejected'),
        ('failed', 'Failed'),
        
    ]
    booking_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE,null=True, blank=True)
    company=models.ForeignKey(CompanyDetails, on_delete=models.CASCADE,null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE,null=True, blank=True)
    room = models.ForeignKey(CruiseRoom, on_delete=models.CASCADE,null=True, blank=True)
    room_quantity = models.PositiveIntegerField(blank=True, null=True)
    adults = models.PositiveIntegerField(blank=True, null=True)
    pets = models.PositiveIntegerField(blank=True, null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    booking_date = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    booking_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    checkin_date= models.DateTimeField(blank=True, null=True)
    checkout_date=models.DateTimeField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True) 
    updated_at = models.DateTimeField(auto_now_add=True,null=True, blank=True) 
    cancel_by = models.CharField(max_length=60, default=None,null=True, blank=True)
    
    

    def save(self, *args, **kwargs):
        if not self.booking_id:
            # You can customize this pattern as needed
            prefix = 'ROM'
            uid = uuid.uuid4().hex[:6].upper()
            self.booking_id = f"{prefix}-{uid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} -({self.room_quantity}) - {self.booking_status}"
    

 
    


class eventBooking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('rejected','Rejected'),
        ('completed', 'Completed'),
        
    )
    booking_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE,null=True, blank=True)
    ticket_id=models.ForeignKey(Product,on_delete=models.CASCADE,null=True, blank=True)
    full_name = models.CharField(max_length=200,null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20,null=True, blank=True)
    booking_date = models.DateField(null=True, blank=True) 
    end_date=models.DateField(null=True, blank=True)
    booking_time = models.TimeField(null=True, blank=True) 
    number_of_people = models.PositiveIntegerField(default=0,null=True, blank=True)
    ticket_type = models.JSONField(max_length=1000,null=True, blank=True) 
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True, blank=True) 
    is_paid=models.BooleanField(default=False,blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True) 
    updated_at = models.DateTimeField(auto_now_add=True,null=True, blank=True)
    cancel_by = models.CharField(max_length=60, default=None,null=True, blank=True)
    

    def save(self, *args, **kwargs):
        if not self.booking_id:
            prefix = 'EVT'
            uid = uuid.uuid4().hex[:6].upper()
            self.booking_id = f"{prefix}-{uid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} - ({self.status})"



class BookingTicketItem(models.Model):
    booking = models.ForeignKey(eventBooking, on_delete=models.CASCADE,null=True, related_name='ticket_items')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE,null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True)
    ticket = GenericForeignKey('content_type', 'object_id')
    quantity = models.PositiveIntegerField()
    


class experienceBooking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('rejected','Rejected'),
        ('completed', 'Completed'),
        
    )
    booking_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE,null=True, blank=True)
    ticket_id=models.ForeignKey(Product,on_delete=models.CASCADE,null=True, blank=True)
    full_name = models.CharField(max_length=200,null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20,null=True, blank=True)
    booking_date = models.DateField(null=True, blank=True) 
    end_date=models.DateField(null=True, blank=True)
    booking_time = models.TimeField(null=True, blank=True) 
    number_of_people = models.PositiveIntegerField(default=0,null=True, blank=True)
    quanity = models.PositiveIntegerField(default=0,null=True, blank=True)
    ticket_type = models.JSONField(max_length=1000,null=True, blank=True) 
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True, blank=True)
    is_paid=models.BooleanField(default=False,blank=True, null=True)
    adult=models.PositiveIntegerField(blank=True, null=True)
    children=models.PositiveIntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True) 
    updated_at = models.DateTimeField(auto_now_add=True,null=True, blank=True) 
    cancel_by = models.CharField(max_length=60, default=None,null=True, blank=True)
    def save(self, *args, **kwargs):
        if not self.booking_id:
            # You can customize this pattern as needed
            prefix = 'EXP'
            uid = uuid.uuid4().hex[:6].upper()
            self.booking_id = f"{prefix}-{uid}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} - ({self.status})"
    

class slotBooking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('rejected','Rejected'),
        ('completed', 'Completed'),
        
    )
    booking_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE,null=True, blank=True)
    Product=models.ForeignKey(Product,on_delete=models.CASCADE,null=True, blank=True)
    full_name = models.CharField(max_length=200,null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20,null=True, blank=True)
    booking_date = models.DateField(null=True, blank=True) 
    slot=models.TimeField(null=True, blank=True)
    booking_time = models.TimeField(null=True, blank=True) 
    number_of_people = models.PositiveIntegerField(default=0,null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True, blank=True)
    is_paid=models.BooleanField(default=False,blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now_add=True,null=True, blank=True) 
    cancel_by = models.CharField(max_length=60, default=None,null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.booking_id:
            # You can customize this pattern as needed
            prefix = 'SLT'
            uid = uuid.uuid4().hex[:6].upper()
            self.booking_id = f"{prefix}-{uid}"
        super().save(*args, **kwargs) 
    

    def __str__(self):
        return f"{self.full_name} - ({self.status})"
    

class aestheticsBooking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('rejected','Rejected'),
        ('completed', 'Completed'),
   
    )

    booking_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE,null=True, blank=True)
    Product=models.ForeignKey(Product,on_delete=models.CASCADE,null=True, blank=True)
    full_name = models.CharField(max_length=200,null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20,null=True, blank=True)
    booking_date = models.DateField(null=True, blank=True) 
    slot=models.TimeField(null=True, blank=True)
    booking_time = models.TimeField(null=True, blank=True) 
    number_of_people = models.PositiveIntegerField(default=0,null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True, blank=True)
    is_paid=models.BooleanField(default=False,blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)  
    updated_at = models.DateTimeField(auto_now_add=True,null=True, blank=True) 
    cancel_by = models.CharField(max_length=60, default=None,null=True, blank=True)
    def save(self, *args, **kwargs):
        if not self.booking_id:
            # You can customize this pattern as needed
            prefix = 'AST'
            uid = uuid.uuid4().hex[:6].upper()
            self.booking_id = f"{prefix}-{uid}"
        super().save(*args, **kwargs) 
    

    def __str__(self):
        return f"{self.full_name} - ({self.status})"
    
    


class relaxationBooking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('rejected','Rejected'),
        ('completed', 'Completed'),
      
    )
    booking_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE,null=True, blank=True)
    Product=models.ForeignKey(Product,on_delete=models.CASCADE,null=True, blank=True)
    full_name = models.CharField(max_length=200,null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20,null=True, blank=True)
    booking_date = models.DateField(null=True, blank=True) 
    slot=models.TimeField(null=True, blank=True)
    booking_time = models.TimeField(null=True, blank=True) 
    number_of_people = models.PositiveIntegerField(default=0,null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True, blank=True)
    is_paid=models.BooleanField(default=False,blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True) 
    updated_at = models.DateTimeField(auto_now_add=True,null=True, blank=True) 
    cancel_by = models.CharField(max_length=60, default=None,null=True, blank=True)
    def save(self, *args, **kwargs):
        if not self.booking_id:
            # You can customize this pattern as needed
            prefix = 'RLX'
            uid = uuid.uuid4().hex[:6].upper()
            self.booking_id = f"{prefix}-{uid}"
        super().save(*args, **kwargs)  
    

    def __str__(self):
        return f"{self.full_name} - ({self.status})"
    

class artandcultureBooking(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('rejected','Rejected'),
        ('completed', 'Completed'),
       
    )
    booking_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE,null=True, blank=True)
    Product=models.ForeignKey(Product,on_delete=models.CASCADE,null=True, blank=True)
    full_name = models.CharField(max_length=200,null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20,null=True, blank=True)
    booking_date = models.DateField(null=True, blank=True) 
    slot=models.TimeField(null=True, blank=True)
    booking_time = models.TimeField(null=True, blank=True) 
    number_of_people = models.PositiveIntegerField(default=0,null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,null=True, blank=True)
    is_paid=models.BooleanField(default=False,blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)  
    updated_at = models.DateTimeField(auto_now_add=True,null=True, blank=True) 
    cancel_by = models.CharField(max_length=60, default=None,null=True, blank=True)
    def save(self, *args, **kwargs):
        if not self.booking_id:
            # You can customize this pattern as needed
            prefix = 'ATC'
            uid = uuid.uuid4().hex[:6].upper()
            self.booking_id = f"{prefix}-{uid}"
        super().save(*args, **kwargs) 
    

    def __str__(self):
        return f"{self.full_name} - ({self.status})"



class LoyaltyRedemption(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    card = models.ForeignKey(LoyaltyCard, on_delete=models.CASCADE)
    order_type = models.CharField(max_length=50)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} redeemed {self.product}"
    
class OrderBookingIcons(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    icon = models.ImageField(upload_to='icon', max_length=255, blank=True, null=True)
   
    def __str__(self):
        return self.name 
      
