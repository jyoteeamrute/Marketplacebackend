from rest_framework import serializers

from .models import *
from .models import AdvertisementPayment, Card
from .utils import decrypt_data, encrypt_data


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"



class UserPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPayment
        fields = '__all__'


class CardSerializer(serializers.ModelSerializer):
    card_number = serializers.CharField(write_only=True)
    cvv = serializers.CharField(write_only=True)
    expiry_date = serializers.CharField(write_only=True)
    card_image = serializers.ImageField(required=False)# Removed read_only=True

    class Meta:
        model = Card
        fields = ['id', 'card_number', 'cvv', 'expiry_date', 'card_saved', 'card_image']

    def create(self, validated_data):
        # Encrypt sensitive data
        validated_data['card_number'] = encrypt_data(validated_data['card_number'])
        validated_data['cvv'] = encrypt_data(validated_data['cvv'])
        validated_data['expiry_date'] = encrypt_data(validated_data['expiry_date'])
        validated_data['card_image'] = "uploads/Screenshot_from_2025-03-28_12-47-19_RdZuVj7.png"

        # Check and set the card_saved field dynamically
        card_saved = validated_data.get('card_saved')

        instance = super().create(validated_data)
        
        # Handle card image
        # if 'card_image' in validated_data:
        #         
        
        # Assign the card_saved value
        instance.card_saved = card_saved
        instance.save()
        return instance
    
    def to_representation(self, instance):
        """Decrypt fields and mask the card number before returning the response."""
        data = super().to_representation(instance)
        
        # Decrypt sensitive data
        decrypted_card_number = decrypt_data(instance.card_number)
        # decrypted_cvv = decrypt_data(instance.cvv)
        decrypted_expiry_date = decrypt_data(instance.expiry_date)

        masked_card_number = decrypted_card_number[:4] + "X" * (len(decrypted_card_number) - 8) + decrypted_card_number[-4:]

        data['card_number'] = masked_card_number
        data['expiry_date'] = decrypted_expiry_date
        # data['card_saved'] = True  #
        
        return data
    
class AdvertisementPaymentSerializer(serializers.ModelSerializer):
    advertisement_title = serializers.CharField(source='advertisement.title')
    payment_amount = serializers.DecimalField(source='payment.amount', max_digits=10, decimal_places=2)
    payment_status = serializers.CharField(source='payment.status')
    user_email = serializers.EmailField(source='payment.user.email')

    class Meta:
        model = AdvertisementPayment
        fields = ['advertisement_title', 'payment_amount', 'payment_status', 'commission_amount', 'user_email']
        
class PaymentListSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email')

    class Meta:
        model = Payment
        fields = ['id', 'stripe_charge_id', 'amount', 'currency', 'status', 'payment_method_type', 'user_email', 'created_at']

class ProfessionalUserTransactionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionalUserTransactionLog
        fields = [
            'id',
            'order',
            'amount',
            'base_price',
            'discount',
            'tax',
            'payment_mode',
            'product_summary',
            'status',
            'created_at'
        ]
