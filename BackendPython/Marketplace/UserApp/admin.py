from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import *


@admin.register(Users)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email', 'phone', 'role','is_active', 'created_by_user', 'created_by_user_id','createdAt')  
    search_fields = ('username', 'email', 'phone', 'createdAt')
    list_filter = ('email', 'role')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('profileImage', 'username', 'firstName', 'lastName', 'dob', 'gender', 'phone', 'language','categories', 'manualAddress','automatic_address')}),
        ('Permissions', {'fields': ('role',)}),  
        ('Other Details', {'fields': ('countryCode', 'identityCardImage', 'termCondition', 'marketingReference','multipleCountry','is_active','stripeOrderCustomerId')}), 

    )

    def save_model(self, request, obj, form, change):
        if not obj.username:
            raise ValidationError("Username is required")
        if not obj.phone:
            raise ValidationError("Phone number is required")
        if not obj.email:
            raise ValidationError("Email is required")
        if obj.dob and obj.dob.year > 2025:
            raise ValidationError("Date of Birth cannot be in the future")
        if not obj.termCondition:
            raise ValidationError("User must accept terms and conditions")  

        super().save_model(request, obj, form, change)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('address1', 'city', 'postalCode')  
    search_fields = ('address1', 'city', 'postalCode')


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'otpCode', 'createdAt')  
    search_fields = ('user__email', 'otpCode')  
    list_filter = ('createdAt',)  

@admin.register(CustomerSupport)
class userAddressAdmin(admin.ModelAdmin):
    list_display = ( 'user',) 

admin.site.site_header = "Marketplace Admin"
admin.site.site_title = "Marketplace Admin Panel"
admin.site.index_title = "Welcome to Marketplace Admin"



@admin.register(PrivacySetting)
class PrivacySettingAdmin(admin.ModelAdmin):
    list_display = (
        'user','activity_visibility', 'identify_visibility','id_visibility','push_notification_status',
        'messaging','friend_invitation','id_verification','chat_notifications','email_notifications'
    )
    search_fields = ('user__username', 'activity_visibility', 'identify_visibility')
    list_filter = ('activity_visibility', 'push_notification_status')

@admin.register(userAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'first_name', 'last_name', 'phone_number', 'city', 'state', 'address_type', 'created_at')
    search_fields = ('first_name', 'last_name', 'phone_number', 'city', 'state')
    list_filter = ('address_type', 'city', 'state')
    ordering = ('-created_at',)
