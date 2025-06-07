from django.contrib import admin

from payment.models import *


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'subscription_plan',
        'subscription_type',
        'stripe_charge_id',
        'amount',
        'currency',
        'status',
        'created_at',
    )
    list_filter = (
        'status',
        'currency',
        'created_at',
        'updated_at',
    )
    search_fields = (
        'user__email',
        'stripe_charge_id',
        'subscription_plan__name',
        'subscription_type__name',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'



@admin.register(UserPayment)
class UserPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'professional_user',
        'stripe_payment_id',
        'amount',
        'currency',
        'status',
        'payment_direction',
        'created_at',    
    )
    search_fields = (
        'user__username',
        'user__email',
        'professional_user__email',
        'stripe_payment_id',
    )
    readonly_fields = ('created_at',)
    
@admin.register(ProfessionalUserTransactionLog)
class ProfessionalUserTransactionLogAdmin(admin.ModelAdmin):
    list_display = ('id','paid_by','paid_to')
        
@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'card_saved',
        'card_image_preview',
        'created_at',
    )
    list_filter = ('card_saved', 'created_at')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('card_number', 'cvv', 'expiry_date', 'created_at')

    def card_image_preview(self, obj):
        if obj.card_image:
            return f'<img src="{obj.card_image.url}" style="height: 50px;" />'
        return "-"
    card_image_preview.allow_tags = True
    card_image_preview.short_description = "Card Image"

    
@admin.register(AdvertisementPayment)
class AdvertisementPaymentAdmin(admin.ModelAdmin):
    list_display = ('advertisement', 'payment', 'commission_rate', 'commission_amount')
    search_fields = ('advertisement__title', 'payment__id')
    list_filter = ('commission_rate',)
    readonly_fields = ('commission_amount',)


