import random
import uuid
from datetime import timedelta

from django.db import models
from django.utils.timezone import now

from Admin.models import *


def generate_support_id():
    return f"SUP-{now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

class Address(models.Model):
    user = models.ForeignKey("UserApp.Users", on_delete=models.CASCADE, related_name="addresses", null=True, blank=True)
    address1 = models.CharField(max_length=255,blank=True, null=True)
    address2 = models.CharField(max_length=255, blank=True, null=True)
    postalCode = models.CharField(max_length=20,blank=True, null=True)
    city = models.CharField(max_length=100,blank=True, null=True)
    country = models.CharField(max_length=100,blank=True, null=True)
    lat = models.CharField(max_length=50, blank=True, null=True)
    lang = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.address1}, {self.city}"
    


class userAddress(models.Model):
    ADDRESS_TYPE_CHOICES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]

    user =models.ForeignKey("UserApp.Users", on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=100,blank=True, null=True)
    last_name = models.CharField(max_length=100,blank=True, null=True)
    phone_code = models.CharField(max_length=10,blank=True, null=True)  # Or use a separate model for country codes
    phone_number = models.CharField(max_length=20,blank=True, null=True)
    lat = models.CharField(max_length=50, blank=True, null=True)
    lang = models.CharField(max_length=50, blank=True, null=True)
    house_building = models.CharField(max_length=255,blank=True, null=True)
    road_area_colony = models.CharField(max_length=255,blank=True, null=True)
    pincode = models.CharField(max_length=10,blank=True, null=True)
    city = models.CharField(max_length=100,blank=True, null=True)
    state = models.CharField(max_length=100,blank=True, null=True)
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES, default='home',blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}"

class Users(models.Model):
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
       
    password = models.CharField(max_length=255)  
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    phone = models.CharField(max_length=20,blank=True, null=True)
    firstName = models.CharField(max_length=100)
    lastName = models.CharField(max_length=100)
    countryCode = models.CharField(max_length=10, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20,choices=GENDER_CHOICES, blank=True, null=True)
    manualAddress = models.OneToOneField(Address, on_delete=models.SET_NULL, null=True, blank=True,related_name="manual_users")
    automatic_address = models.OneToOneField(Address, on_delete=models.SET_NULL, null=True, blank=True,related_name="automatic_users")
    identityCardImage = models.ImageField(upload_to='identity_cards/', blank=True, null=True)
    profileImage = models.ImageField(upload_to='profile_Image/', blank=True, null=True)
    language = models.ForeignKey(Language, on_delete=models.SET_NULL, null=True, blank=True)
    categories = models.ManyToManyField(Category,  blank=True)
    subcategories = models.ManyToManyField(Subcategory,  blank=True)    
    multipleCountry = models.ManyToManyField(Country, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    termCondition = models.BooleanField(default=True)
    id_card_verified = models.BooleanField(default=False)
    marketingReference = models.BooleanField(default=True)
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    warning_message = models.CharField(max_length=255, null=True, blank=True)
    created_by_user = models.CharField(max_length=20, null=True, blank=True)
    created_by_user_id = models.IntegerField(null=True, blank=True)
    stripeOrderCustomerId= models.CharField(max_length=255, null=True, blank=True)

    def save(self, *args, **kwargs):
        """Assign default role 'user' if not provided"""

        """Ensure at least one address is present before saving."""
        if not self.role:
            self.role, _ = Role.objects.get_or_create(name="user")
        super().save(*args, **kwargs)
 
    def __str__(self):
        return self.username

    @property
    def is_authenticated(self):
        return True  

    
class OTP(models.Model):
    user = models.OneToOneField(Users, on_delete=models.SET_NULL,null=True,blank=True)  # One user, one OTP
    otpCode = models.CharField(max_length=4)
    createdAt = models.DateTimeField(auto_now_add=True)

    def generateOtp(self):
        self.otpCode = str(random.randint(1000, 9999))  # 4-digit OTP
        self.createdAt = now() 
        self.save()

    def isExpired(self):
        expiry_time = self.createdAt + timedelta(minutes=5)  # OTP valid for 5 minutes
        return now() > expiry_time

    def __str__(self):
        return f"OTP for {self.user.email} - {self.otpCode}"


class VerfyOTP(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    otpCode = models.CharField(max_length=6)
    createdAt = models.DateTimeField(auto_now_add=True)

    def generateOtp(self):
        self.otpCode = str(random.randint(100000, 999999))  # 6-digit OTP for login/registration
        self.createdAt = now()
        self.save()

    def isExpired(self):
        expiry_time = self.createdAt + timedelta(minutes=5)  # OTP expires in 5 minutes
        return now() > expiry_time

    def __str__(self):
        return f"Verify OTP for {self.user.email or self.user.phone} - {self.otpCode}"


class Feedback(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=250)
    media = models.FileField(upload_to='uploads/', null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)


class CustomerSupport(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, related_name='support_requests')
    title = models.CharField(max_length=255)
    description = models.TextField()
    support_id = models.CharField(max_length=100, unique=True)
    support_option = models.ForeignKey(SupportOption, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to='support_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.support_id:
            self.support_id = generate_support_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.support_id} - {self.title}"  
    

class PrivacySetting(models.Model):
    PRIVACY_CHOICES = [
        ('everyone', 'EveryOne'),
        ('private', 'Private'),
        ('friends_of_friends', 'Friends of Friends'),
        ('only_friends', 'Only Friends'),
        
    ]
    PUSH_NOTIFICATION_CHOICES = [
    ('activate', 'Activate'),
    ('deactivate', 'Deactivate'),
    ]


    user = models.OneToOneField(Users, on_delete=models.CASCADE)
    
    activity_visibility = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='only_friends')
    identify_visibility = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='only_friends')
    id_visibility = models.CharField(max_length=20, choices=PRIVACY_CHOICES, default='only_friends')
    push_notification_status = models.CharField(max_length=20, choices=PUSH_NOTIFICATION_CHOICES, default='activate')

    messaging = models.BooleanField(default=True)
    friend_invitation = models.BooleanField(default=True)
    id_verification = models.BooleanField(default=True)
    chat_notifications = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)

    def __str__(self):
        return f"Privacy settings for {self.user}"
   



class AdvertisementClick(models.Model):
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='clicks')
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    count = models.PositiveIntegerField(default=1)  # Start with 1 on first click
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('advertisement', 'user')  # Ensures one record per user-ad pair

    def __str__(self):
        return f"{self.user} clicked {self.advertisement.title} ({self.count} times)"



class OrderBookingFeedback(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)  
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=100)
    content_object = GenericForeignKey('content_type', 'object_id')
    rating = models.PositiveSmallIntegerField()
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'content_type', 'object_id')

    def __str__(self):
        return f"Feedback by {self.user} for {self.content_type} - {self.object_id}"