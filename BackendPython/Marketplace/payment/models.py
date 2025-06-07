from django.db import models

from Admin.models import *  # Adjust import if necessary
from Marketplace.constants import *
from ProfessionalUser.models import *  # Adjust import based on your project
from UserApp.models import Users

from .utils import decrypt_data, encrypt_data


class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("succeeded", "Succeeded"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
         ("refund", "Refund"),
    ]

    user = models.ForeignKey(
        ProfessionalUser, on_delete=models.CASCADE, related_name="payments"
    )
    subscription_type = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, blank=True
    )  # Ensure correct model name
    subscription_plan= models.ForeignKey(
        SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True
    )
    stripe_charge_id = models.CharField(max_length=255, unique=True,null=True, blank=True)  # Updated naming
    amount = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    payment_method_type = models.CharField(max_length=50, null=True, blank=True)

    currency = models.CharField(max_length=10, default="usd")
    status = models.CharField(
        max_length=255, choices=STATUS_CHOICES, default="pending"
    )
    payment_geteway=models.CharField(max_length=50, null=True, blank=True)
    stripe_customer_id=models.CharField(max_length=50, null=True, blank=True)
    CardType = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.stripe_charge_id} - {self.status} - {self.amount} {self.currency}"


class UserPayment(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE)
    professional_user = models.ForeignKey(ProfessionalUser, on_delete=models.CASCADE)
    stripe_payment_id = models.CharField(max_length=255, null=True, blank=True)
    
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Final paid amount
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    booking_type = models.CharField(max_length=50, null=True, blank=True)
    booking_id = models.CharField(max_length=100, null=True, blank=True)
    
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES,null=True, blank=True)
    product_summary = models.TextField(null=True, blank=True)  # store product names and quantity 
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default="EURO")
    status = models.CharField(max_length=50, choices=PAYMENT_STATUS, default="pending")
    payment_direction = models.CharField(max_length=10, choices=PAYMENT_DIRECTION, default="credited")
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    transaction_id=models.CharField(max_length=255, null=True, blank=True)
class ProfessionalUserTransactionLog(models.Model):
    paid_by = models.ForeignKey(Users, on_delete=models.CASCADE, related_name="transactions_made")
    paid_to = models.ForeignKey(ProfessionalUser, on_delete=models.CASCADE, related_name="transactions_received")
    
    payment = models.ForeignKey(UserPayment, on_delete=models.SET_NULL, null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    payment_mode = models.CharField(max_length=20,choices=PAYMENT_MODES,null=True, blank=True)
    status = models.CharField(max_length=50, choices=[
        ("credited", "Credited"), ("debited", "Debited"), ("refunded", "Refunded"),
    ])
    paymentStatus = models.CharField(max_length=50, choices=PAYMENT_STATUS, default="pending")
    transaction_id=models.CharField(max_length=255, null=True, blank=True)
    
    
    product_summary = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Card(models.Model):
    user = models.ForeignKey(ProfessionalUser, on_delete=models.CASCADE)
    card_number = models.TextField()
    cvv = models.TextField()
    expiry_date = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    card_saved=models.BooleanField(default=False)
    card_image=models.ImageField(upload_to='uploads/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.card_number.startswith("gAAAA"):  # Avoid re-encryption
            self.card_number = encrypt_data(self.card_number)
        if not self.cvv.startswith("gAAAA"):
            self.cvv = encrypt_data(self.cvv)
        if not self.expiry_date.startswith("gAAAA"):
            self.expiry_date = encrypt_data(self.expiry_date)
        super().save(*args, **kwargs)

    def get_decrypted_card_details(self):
        return {
            "card_number": decrypt_data(self.card_number),
            "cvv": decrypt_data(self.cvv),
            "expiry_date": decrypt_data(self.expiry_date),
        }
    
class AdvertisementPayment(models.Model):
    advertisement = models.ForeignKey(Advertisement, on_delete=models.CASCADE, related_name='ad_payments')
    payment = models.ForeignKey('Payment', on_delete=models.CASCADE, related_name='advertisement_payments')
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.5)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.payment and self.commission_rate:
            self.commission_amount = (self.payment.amount or 0) * (self.commission_rate / 100)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'AdvertisementPayment for {self.advertisement.title} - Commission: {self.commission_amount}'
