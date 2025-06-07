import json
import uuid
from decimal import Decimal

import stripe
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from Admin.models import *
from ProfessionalUser.models import *
from ProfessionalUser.utils import *

from .models import *
from .serializers import (AdvertisementPaymentSerializer, CardSerializer,
                          PaymentSerializer)
from .utils import *

stripe.api_key = settings.STRIPE_SECRET_KEY  
import logging

import stripe

logger = logging.getLogger(__name__)
from django.utils import timezone

timezone.now()

# views.py
class CreatePaymentIntentView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        data = request.data
        # user_professional_id =data.get("userProfessionalId")
        user= request.user #
        subscription_id = data.get("subscriptionId")
        paymentMethodId =  data.get("paymentMethodId") or None
        subscription_type_plan_id = data.get("subscriptionPlanId")
        print("subscription_type_plan_id>>>>>>",subscription_type_plan_id)

        logger.info(f"subscription _id: {subscription_id}")
        logger.info(f"subscription_type_plan_id>>>>>{subscription_type_plan_id}")
        # Validate required fields
        if not all([user, subscription_id, subscription_type_plan_id]):
            return Response({  
                    "status": False,
                    "statusCode": 400,
                    "error": "Missing required parameters (userProfessionalId, subscriptionId, subscriptionType)"}, 
                status=status.HTTP_200_OK
            )

        try:
            professional_user = ProfessionalUser.objects.get(id=user.id)
            # professional_user = ProfessionalUser.objects.get(id=user_professional_id)
        except ProfessionalUser.DoesNotExist:
            return Response(
                {"status": False,
                "statusCode": 404,
                "error": "Professional user not found"}, 
                status=status.HTTP_200_OK
            )
        
        if professional_user.subscription_active and professional_user.subscription_status in ["paid"]:
            return Response({
                "status": False,
                "statusCode": 200,
                "message": "Your plan is already active.",
                "subscription_status": professional_user.subscription_status,
                "is_subscription_active": professional_user.subscription_active,
                "trial_end_date": professional_user.trial_end_date,
            }, status=status.HTTP_200_OK)

        try:
            subscription_plan = SubscriptionPlan.objects.get(
                subscription_id=subscription_id, 
                id=subscription_type_plan_id
            )
            print("subscription_plan>================================>>>>>>>>>>>>>",subscription_plan)
            #subscription_details = Subscription.objects.get(id=subscription_id)
            subscription_type = subscription_plan.subscription_type
            print("Plan type:", subscription_type)  # Output will be 'Monthly' or 'Annual'

            
            if subscription_plan.price is None:
                return Response({
                    "error": "Price for this subscription plan is not set.",
                    "status": False,
                    "statusCode": 400
                }, status=status.HTTP_200_OK)

        except SubscriptionPlan.DoesNotExist:
            return Response(
                {   "status": False,
                    "statusCode": 404,
                    "error": "Subscription plan not found"}, 
                status=status.HTTP_200_OK
            )
        try:
            subscription_details = Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            return

        
        sub_plan_type = str(subscription_plan.subscription_type).lower()
        if (not professional_user.trial_start_date and not professional_user.trial_end_date  
              and sub_plan_type in ["monthly", "annual"] and not professional_user.subscription_active):   
           
            try:
                logger.info(f"First time choosing subscription - activate free trial.....")
                if subscription_details.name.lower()=="free":
                    trial_start_date = timezone.now()
                    trial_end_date = trial_start_date + timedelta(days=90)
                else:
                    trial_start_date = timezone.now()
                    trial_end_date = trial_start_date + timedelta(days=180)
                professional_user.trial_start_date = trial_start_date
                professional_user.trial_end_date = trial_end_date
                professional_user.is_free_trial_active = True
                professional_user.subscriptionplan = subscription_plan.subscription  
                professional_user.subscriptiontype = subscription_plan
                professional_user.subscription_active = True
                professional_user.subscription_status="trial"
                professional_user.save()

            except Exception as e:
                print("error in professional user saving>>>>>> ",e)  
                return Response(
                {   "status": False,
                    "statusCode": 500,
                    "error": f"Subscription plan details not saved  for {professional_user}"}, 
                status=status.HTTP_200_OK
            )  

            return Response({
                        "status": True,
                        "statusCode": 200,
                        "subscription_status":professional_user.subscription_status,
                        "is_subscription_active": professional_user.subscription_active,
                        "message": "Your  3 Month Subscription has been activated.",
                        "trial_end_date": professional_user.trial_end_date,
                       "subscriptionPlan": {
                                "id":subscription_plan.id,
                                "name": subscription_plan.subscription.name,
                                "type": subscription_plan.subscription_type,
                                "price": subscription_plan.price,
                            },
                        "user": {
                            "email": professional_user.email,
                            "phone": professional_user.phone,
                            "id":professional_user.id,
                            "is_verified": professional_user.is_verified,
                            "Subscription": professional_user.subscriptionplan.name if professional_user.subscriptionplan else None,
                            "company": {
                        "companyID":professional_user.company.id if professional_user.company else None,
                        "companyName": professional_user.company.companyName if professional_user.company else None,
                        "managerFullName": professional_user.company.managerFullName if professional_user.company else None,
                        "phoneNumber": professional_user.company.phoneNumber if professional_user.company else None,
                        "email": professional_user.company.email if professional_user.company else None,
                        "siret": professional_user.company.siret if professional_user.company else None,
                        "sectorofActivity": professional_user.company.sectorofActivity if professional_user.company else None,
                        "vatNumber": professional_user.company.vatNumber if professional_user.company else None,
                        }  if professional_user.company else None,
                        "categoryID": {
                                str(category_id): category_name
                                for category_id, category_name in zip(
                                    professional_user.categories.values_list('id', flat=True),
                                    professional_user.categories.values_list('name', flat=True)
                                )
                            } or None,
                        "subcategoriesID": {
                            str(subcategory_id): subcategory_name
                            for subcategory_id, subcategory_name in zip(
                                professional_user.subcategories.values_list('id', flat=True),
                                professional_user.subcategories.values_list('name', flat=True)
                            )
                        } or None,
                        "category":{
                            "subscriptionPlan":professional_user.subscriptionplan.name if professional_user.subscriptionplan else None,
                            "limit":professional_user.subscriptionplan.category_limit if professional_user.subscriptionplan else None,
                        },
                        "Subcategory":{
                            "limit":professional_user.subscriptionplan.subcategory_limit if professional_user.subscriptionplan else None,
                        },
                        "manual_address": {
                        "address1": professional_user.manual_address.address1 if professional_user.manual_address else None,
                        "address2": professional_user.manual_address.address2 if professional_user.manual_address else None,
                        "postalCode": professional_user.manual_address.postalCode if professional_user.manual_address else None,
                        "lat": professional_user.manual_address.lat if professional_user.manual_address else None,
                        "lang": professional_user.manual_address.lang if professional_user.manual_address else None,
                        "city": professional_user.manual_address.city if professional_user.manual_address else None,
                        "country": professional_user.manual_address.country if professional_user.manual_address else None
                    } if professional_user.manual_address else None,
                    "automatic_address": {
                        "address1": professional_user.automatic_address.address1 if professional_user.automatic_address else None,
                        "address2": professional_user.automatic_address.address2 if professional_user.automatic_address else None,
                        "postalCode": professional_user.automatic_address.postalCode if professional_user.automatic_address else None,
                        "lat": professional_user.automatic_address.lat if professional_user.automatic_address else None,
                        "lang": professional_user.automatic_address.lang if professional_user.automatic_address else None,
                        "city": professional_user.automatic_address.city if professional_user.automatic_address else None,
                        "country": professional_user.automatic_address.country if professional_user.automatic_address else None
                    } if professional_user.automatic_address else None
                        
                            },
                        

                    }, status=status.HTTP_200_OK)
        
        # Inside your view
        elif professional_user.trial_end_date and timezone.now() > professional_user.trial_end_date:
            print("Trial expired. Payment required.")
            try:
                amount = int(subscription_plan.price * 100)  # Convert to cents

                # Create or retrieve Stripe Customer
                if not professional_user.stripe_customer_id:
                    customer = stripe.Customer.create(
                        name=professional_user.userName,
                        email=professional_user.email,
                        metadata={
                            "user_professional_id": professional_user.id,
                            "subscription_id": subscription_id,
                            "subscription_type": subscription_plan.subscription_type
                        }
                    )
                    professional_user.stripe_customer_id = customer.id
                    professional_user.save()
                else:
                    logger.info(f"Customer already exists: {professional_user.stripe_customer_id}")
                    customer = stripe.Customer.retrieve(professional_user.stripe_customer_id)

                # Validate Payment Method ID
                if not paymentMethodId:
                    return Response({
                        "status": False,
                        "statusCode": 400,
                        "message": "Payment method ID not found"
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Create PaymentIntent
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency='usd',
                    customer=customer.id,
                    payment_method=paymentMethodId,
                    off_session=True,
                    confirm=True,
                    description=f"Subscription payment for {subscription_plan.subscription_type} {subscription_plan.subscription.name} plan",
                    payment_method_types=['card'],
                    metadata={
                        "user_professional_id": str(professional_user.id),
                        "subscription_id": subscription_id,
                        "subscription_type": subscription_plan.subscription_type,
                        "subscription_plan": subscription_plan.subscription.name
                    },
                )
                print("payment_intent>>>")

                # Check PaymentIntent status
                if payment_intent.status == "succeeded":
                    trial_start_date = now()
                    if subscription_plan.subscription_type.lower() == "monthly":
                        trial_end_date = trial_start_date + timedelta(days=30)
                    elif subscription_plan.subscription_type.lower() in ["annual", "annually"]:
                        trial_end_date = trial_start_date + timedelta(days=365)
                    else:
                        trial_end_date = trial_start_date + timedelta(days=30)  # Default fallback

                    # Update subscription info
                    professional_user.trial_start_date = trial_start_date
                    professional_user.trial_end_date = trial_end_date
                    professional_user.is_free_trial_active = False
                    professional_user.trial_availed = True
                    professional_user.subscriptionplan = subscription_plan.subscription
                    professional_user.subscriptiontype = subscription_plan
                    professional_user.subscription_active = True
                    professional_user.is_paid_subscription_active = True
                    professional_user.subscription_status = "paid"
                    professional_user.save()
                    print("subscripton")
                    # Save Payment record
                    Payment.objects.create(
                        user=professional_user,
                        subscription_plan=subscription_plan,
                        subscription_type=subscription_details,
                        stripe_charge_id=payment_intent.id,
                        amount=payment_intent.amount / 100,
                        currency=payment_intent.currency,
                        status=payment_intent.status,
                        payment_method_type=payment_intent.payment_method_types[0] if payment_intent.payment_method_types else None
                    )

                    return Response({
                        "status": True,
                        "statusCode": 200,
                        "subscription_status": professional_user.subscription_status,
                        "is_subscription_active": professional_user.subscription_active,
                        "message": f"Your paid subscription  plan of {subscription_plan.subscription_type}is now  actived",
 
                        "clientSecret": payment_intent.client_secret,
                        "paymentIntentId": payment_intent.id,
                        "message": "Payment successful",
                        "subscriptionPlan": {
                            "id": subscription_plan.id,
                            "name": subscription_plan.subscription.name,
                            "type": subscription_plan.subscription_type,
                            "price": subscription_plan.price,
                        },
                        "user": {
                            "email": professional_user.email,
                            "phone": professional_user.phone,
                            "id":professional_user.id,
                            "is_verified": professional_user.is_verified,
                            "Subscription": professional_user.subscriptionplan.name if professional_user.subscriptionplan else None,
                            "company": {
                        "companyID":professional_user.company.id if professional_user.company else None,
                        "companyName": professional_user.company.companyName if professional_user.company else None,
                        "managerFullName": professional_user.company.managerFullName if professional_user.company else None,
                        "phoneNumber": professional_user.company.phoneNumber if professional_user.company else None,
                        "email": professional_user.company.email if professional_user.company else None,
                        "siret": professional_user.company.siret if professional_user.company else None,
                        "sectorofActivity": professional_user.company.sectorofActivity if professional_user.company else None,
                        "vatNumber": professional_user.company.vatNumber if professional_user.company else None,
                        }  if professional_user.company else None,
                        "categoryID": {
                                str(category_id): category_name
                                for category_id, category_name in zip(
                                    professional_user.categories.values_list('id', flat=True),
                                    professional_user.categories.values_list('name', flat=True)
                                )
                            } or None,
                        "subcategoriesID": {
                            str(subcategory_id): subcategory_name
                            for subcategory_id, subcategory_name in zip(
                                professional_user.subcategories.values_list('id', flat=True),
                                professional_user.subcategories.values_list('name', flat=True)
                            )
                        } or None,
                        "category":{
                            "subscriptionPlan":professional_user.subscriptionplan.name if professional_user.subscriptionplan else None,
                            "limit":professional_user.subscriptionplan.category_limit if professional_user.subscriptionplan else None,
                        },
                        "Subcategory":{
                            "limit":professional_user.subscriptionplan.subcategory_limit if professional_user.subscriptionplan else None,
                        },
                        "manual_address": {
                        "address1": professional_user.manual_address.address1 if professional_user.manual_address else None,
                        "address2": professional_user.manual_address.address2 if professional_user.manual_address else None,
                        "postalCode": professional_user.manual_address.postalCode if professional_user.manual_address else None,
                        "lat": professional_user.manual_address.lat if professional_user.manual_address else None,
                        "lang": professional_user.manual_address.lang if professional_user.manual_address else None,
                        "city": professional_user.manual_address.city if professional_user.manual_address else None,
                        "country": professional_user.manual_address.country if professional_user.manual_address else None
                    } if professional_user.manual_address else None,
                    "automatic_address": {
                        "address1": professional_user.automatic_address.address1 if professional_user.automatic_address else None,
                        "address2": professional_user.automatic_address.address2 if professional_user.automatic_address else None,
                        "postalCode": professional_user.automatic_address.postalCode if professional_user.automatic_address else None,
                        "lat": professional_user.automatic_address.lat if professional_user.automatic_address else None,
                        "lang": professional_user.automatic_address.lang if professional_user.automatic_address else None,
                        "city": professional_user.automatic_address.city if professional_user.automatic_address else None,
                        "country": professional_user.automatic_address.country if professional_user.automatic_address else None
                    } if professional_user.automatic_address else None
                    },
                        
                    }, status=status.HTTP_200_OK)

                else:
                    # Payment failed
                    logger.warning(f"Payment failed with status: {payment_intent.status}")

                    Payment.objects.create(
                        user=professional_user,
                        subscription_plan=subscription_id,
                        subscription_type=subscription_details,
                        stripe_charge_id=payment_intent.id,
                        amount=payment_intent.amount / 100,
                        currency=payment_intent.currency,
                        status=payment_intent.status,
                        payment_method_type=payment_intent.payment_method_types[0] if payment_intent.payment_method_types else None
                    )

                    return Response({
                        "status": False,
                        "statusCode": 402,
                        "subscription_status": professional_user.subscription_status,
                        "is_subscription_active": professional_user.subscription_active,
                        "message": f"Your payment is failed!!!!!",
 
                        "paymentIntentId": payment_intent.id,
                        "message": f"Payment failed. Status: {payment_intent.status}"
                    }, status=status.HTTP_200_OK)

            except stripe.error.StripeError as e:
                logger.error(f"Stripe error: {str(e)}")

                Payment.objects.create(
                    user=professional_user,
                    subscription_plan=subscription_plan,
                    subscription_type=subscription_details,
                    stripe_charge_id=f"error_{uuid.uuid4()}",
                    amount=subscription_plan.price,
                    currency='usd',
                    status='failed',
                )

                return Response({
                    "status": False,
                    "statusCode": 400,
                    "message": "Stripe error occurred",
                    "error": str(e)
                }, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                return Response({
                    "status": False,
                    "statusCode": 500,
                    "message": "Internal server error",
                    "error": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        
        # **Trial is still active → No need to pay**
        elif professional_user.trial_end_date and timezone.now() <= professional_user.trial_end_date:
            
                logger.info(f"Trial is still active → No need to pay")
                return Response({
                    "status": False,
                    "statusCode": 200,
                    "subscription_status":professional_user.subscription_status,
                    "is_subscription_active": professional_user.subscription_active,
                    "message": "Your trial is still active. No need to pay now.",
                    "trial_end_date": professional_user.trial_end_date,
                    "subscriptionPlan": {
                            "id":subscription_plan.id,
                            "name": subscription_plan.subscription.name,
                            "type": subscription_plan.subscription_type,
                            "price": subscription_plan.price,
                        },
                    "user": {
                        "email": professional_user.email,
                        "phone": professional_user.phone,
                        "id":professional_user.id,
                        "is_verified": professional_user.is_verified,
                        "Subscription": professional_user.subscriptionplan.name if professional_user.subscriptionplan else None,
                        "company": {
                    "companyID":professional_user.company.id if professional_user.company else None,
                    "companyName": professional_user.company.companyName if professional_user.company else None,
                    "managerFullName": professional_user.company.managerFullName if professional_user.company else None,
                    "phoneNumber": professional_user.company.phoneNumber if professional_user.company else None,
                    "email": professional_user.company.email if professional_user.company else None,
                    "siret": professional_user.company.siret if professional_user.company else None,
                    "sectorofActivity": professional_user.company.sectorofActivity if professional_user.company else None,
                    "vatNumber": professional_user.company.vatNumber if professional_user.company else None,
                    }  if professional_user.company else None,
                    "categoryID": {
                            str(category_id): category_name
                            for category_id, category_name in zip(
                                professional_user.categories.values_list('id', flat=True),
                                professional_user.categories.values_list('name', flat=True)
                            )
                        } or None,
                    "subcategoriesID": {
                        str(subcategory_id): subcategory_name
                        for subcategory_id, subcategory_name in zip(
                            professional_user.subcategories.values_list('id', flat=True),
                            professional_user.subcategories.values_list('name', flat=True)
                        )
                    } or None,
                    "category":{
                        "subscriptionPlan":professional_user.subscriptionplan.name if professional_user.subscriptionplan else None,
                        "limit":professional_user.subscriptionplan.category_limit if professional_user.subscriptionplan else None,
                    },
                    "Subcategory":{
                        "limit":professional_user.subscriptionplan.subcategory_limit if professional_user.subscriptionplan else None,
                    },
                    "manual_address": {
                    "address1": professional_user.manual_address.address1 if professional_user.manual_address else None,
                    "address2": professional_user.manual_address.address2 if professional_user.manual_address else None,
                    "postalCode": professional_user.manual_address.postalCode if professional_user.manual_address else None,
                    "lat": professional_user.manual_address.lat if professional_user.manual_address else None,
                    "lang": professional_user.manual_address.lang if professional_user.manual_address else None,
                    "city": professional_user.manual_address.city if professional_user.manual_address else None,
                    "country": professional_user.manual_address.country if professional_user.manual_address else None
                } if professional_user.manual_address else None,
                "automatic_address": {
                    "address1": professional_user.automatic_address.address1 if professional_user.automatic_address else None,
                    "address2": professional_user.automatic_address.address2 if professional_user.automatic_address else None,
                    "postalCode": professional_user.automatic_address.postalCode if professional_user.automatic_address else None,
                    "lat": professional_user.automatic_address.lat if professional_user.automatic_address else None,
                    "lang": professional_user.automatic_address.lang if professional_user.automatic_address else None,
                    "city": professional_user.automatic_address.city if professional_user.automatic_address else None,
                    "country": professional_user.automatic_address.country if professional_user.automatic_address else None
                } if professional_user.automatic_address else None
                    
                        },
                    

                }, status=status.HTTP_200_OK)

       
        else:
            #  If not eligible for trial
            return Response({
                "status": False,
                "statusCode": 400,
                "error": "Free trial only available for first-time monthly subscribers",
                "user_status": {
                    "has_trial": professional_user.subscription_active,
                    "current_plan_type": sub_plan_type
                }
            }, status=status.HTTP_200_OK)
# views.py
class UserCardPaymentView(APIView):
    def post(self, request):
        try:
            user_id = request.data.get("userId")
            professional_user_id = request.data.get("userProfessionalId")
            order_id = request.data.get("orderId")
            amount = request.data.get("amount")
            currency = request.data.get("currency", "usd")
            payment_method_type = request.data.get("paymentMethodType", "card")

            if not all([user_id, professional_user_id, order_id, amount]):
                return Response({
                    "statusCode": 400, 
                    "status": False, 
                    "message": "Missing required fields",
                }, status=status.HTTP_400_BAD_REQUEST)

            # Verify objects exist but don't use them yet
            Users.objects.get(id=user_id)
            ProfessionalUser.objects.get(id=professional_user_id)
            Order.objects.get(id=order_id)

            # Create PaymentIntent
            payment_intent = stripe.PaymentIntent.create(
                amount=int(float(amount) * 100),  # in cents
                currency=currency,
                payment_method_types=[payment_method_type],
                metadata={
                    "user_id": str(user_id),
                    "professional_user_id": str(professional_user_id),
                    "order_id": str(order_id)
                },
                description=f"Payment for Order #{order_id}"
            )

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Payment intent created",
                "paymentIntentId": payment_intent.id,
                "clientSecret": payment_intent.client_secret,
                "requiresAction": payment_intent.status == "requires_action"
            })

        except Users.DoesNotExist:
            return Response({"statusCode": 404, "status": False, "message": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except ProfessionalUser.DoesNotExist:
            return Response({"statusCode": 404, "status": False, "message": "Professional user not found"}, status=status.HTTP_404_NOT_FOUND)
        except Order.DoesNotExist:
            return Response({"statusCode": 404, "status": False, "message": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        except stripe.error.StripeError as e:
            return Response({
                "statusCode": 500, 
                "status": False, 
                "message": "Payment processing error",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
class VerifyuserorderPaymentView(APIView):
    def post(self, request):
        try:
            payment_intent_id = request.data.get("paymentIntentId")
            if not payment_intent_id:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Payment intent ID is required"
                }, status=status.HTTP_200_OK)

            # Retrieve the payment intent from Stripe
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if payment_intent.status != "succeeded":
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Payment not completed. Current status: {payment_intent.status}",
                    "paymentStatus": payment_intent.status
                }, status=status.HTTP_200_OK)

            # Get metadata from payment intent
            metadata = payment_intent.metadata
            user_id = metadata.get("user_id")
            professional_user_id = metadata.get("professional_user_id")
            order_id = metadata.get("order_id")

            # Get objects
            user = Users.objects.get(id=user_id)
            professional_user = ProfessionalUser.objects.get(id=professional_user_id)
            order = Order.objects.get(id=order_id)

            # Update professional user payment status
            professional_user.is_paid = True
            professional_user.save()

            # Create payment record
            # payment = UserPayment.objects.create(
            #     user=user,
            #     professional_user=professional_user,
            #     Order=order,
            #     stripe_payment_id=payment_intent.id,
            #     amount=payment_intent.amount / 100,  # Convert back to dollars
            #     currency=payment_intent.currency,
            #     payment_gateway="Stripe",
            #     CardType=payment_intent.payment_method_types[0] if payment_intent.payment_method_types else "card",
            #     status=payment_intent.status
            # )

            # Update order status if needed
            # order.orderStatus =
            # order.save()

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Payment confirmed successfully",
                # "paymentId": payment.id,
                "professionalUserPaid": professional_user.is_paid,
                "orderStatus": order.status
            })

        except stripe.error.StripeError as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "Stripe error",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)            
@method_decorator(csrf_exempt, name="dispatch")
class ConfirmPaymentView(APIView):
    def post(self, request):
        try:
            data = request.POST
            stripe_payment_id = data.get("stripe_payment_id")
            payment_method_id = data.get("payment_method_id")

            if not stripe_payment_id or not payment_method_id:
                return JsonResponse({"error": "Missing required fields"}, status=200)

            # Attach payment method
            stripe.PaymentIntent.modify(
                stripe_payment_id,
                payment_method=payment_method_id
            )

            # Confirm payment
            payment_intent = stripe.PaymentIntent.confirm(stripe_payment_id)

            # Fetch payment record
            payment = Payment.objects.get(stripe_payment_id=stripe_payment_id)
            payment.status = payment_intent.status
            payment.save()

            # If payment is statusful, update the ProfessionalUser
            if payment.status == "succeeded":
                professional_user = payment.user
                professional_user.subscriptionplan = payment.subscription_plan
                professional_user.save()

            return JsonResponse({
                "statusCode": 200, "status":True,
                "payment_status": payment.status,
                "payment_id": payment.id
            },status=status.HTTP_200_OK)
        except Payment.DoesNotExist:
            return JsonResponse({"statusCode": 400, "status":False,"error": "Payment record not found"}, status=200)
        except Exception as e:
            return JsonResponse({"statusCode": 400, "status":False,"error": str(e)}, status=200)


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # ✅ Use intent directly from event payload, don't fetch again
    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        print("✅ Payment succeeded! Intent ID:", intent['id'])

    return HttpResponse(status=200)




@csrf_exempt
def stripe_webhookssss(request):
    payload = request.body
    sig_header = request.META.get(stripe.api_key)
    endpoint_secret = stripe.api_key

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return JsonResponse({"statusCode": 400, "status":False,"message": "Invalid payload"}, status=200)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({"statusCode": 400, "status":False, "message": "Invalid signature"}, status=200)

    # Handle statusful payment
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        stripe_payment_id = payment_intent["id"]

        try:
            payment = Payment.objects.get(stripe_payment_id=stripe_payment_id)
            payment.status = "succeeded"
            payment.save()

            user = payment.user
            user.subscriptionplan = payment.subscription_plan
            user.save()

            return JsonResponse({"status": "Subscription assigned statusfully"}, status=200)

        except Payment.DoesNotExist:
            return JsonResponse({"statusCode": 400, "status":False,"message": "Payment record not found"}, status=200)

    return JsonResponse({"statusCode": 400, "status":False,"message": "ignored"}, status=200)


class AddCardView(generics.CreateAPIView):
    serializer_class = CardSerializer  # Should accept 'payment_method_id'
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        user = request.user
        payment_method_id = request.data.get("payment_method_id")

        if not payment_method_id:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Payment method ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        professional_user = ProfessionalUser.objects.get(id=user.id)
        try:
            company = request.user.company
        except CompanyDetails.DoesNotExist:
            company = None
        
        # Create Stripe customer if not exists


        # Retrieve saved card details
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)

        # Optionally save masked card info to your DB via serializer
        serializer = self.get_serializer(data={
            "brand": payment_method.card.brand,
            "last4": payment_method.card.last4,
            "exp_month": payment_method.card.exp_month,
            "exp_year": payment_method.card.exp_year,
            "payment_method_id": payment_method.id
        })
        
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({
                "message": "Card added successfully",
                "statusCode": 200,
                "status": True,
                "Username": company.managerFullName if company else None,
                "card": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "statusCode": 400,
            "status": False,
            "message": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class GetCardView(generics.ListAPIView):
    serializer_class = CardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Card.objects.filter(user=self.request.user).order_by('-id')

    def list(self, request, *args, **kwargs):
        try:
            user = request.user
            try:
                username = user.company.managerFullName
            except CompanyDetails.DoesNotExist:
                username = None

            if not user.stripe_customer_id:
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "No customer account found",
                    "data": []
                }, status=status.HTTP_200_OK)

            # Initialize empty response
            combined_cards = []

            try:
                # Get cards from Stripe
                stripe_cards = stripe.PaymentMethod.list(
                    customer=user.stripe_customer_id,
                    type="card"
                )
                
                # Process Stripe cards if they exist
                for stripe_card in stripe_cards.data:
                    combined_cards.append({
                        "payment_method_id": stripe_card.id,
                        "last4": stripe_card.card.last4,
                        "brand": stripe_card.card.brand,
                        "exp_month": stripe_card.card.exp_month,
                        "exp_year": stripe_card.card.exp_year,
                        "card_saved": True,
                        "card_number": f"XXXX-XXXX-XXXX-{stripe_card.card.last4}",
                        "expiry_date": f"{stripe_card.card.exp_month:02d}/{stripe_card.card.exp_year}",
                        "Username": username
                    })

            except stripe.error.InvalidRequestError as e:
                # Handle case where customer doesn't exist in Stripe
                if e.code == "resource_missing":
                    pass  # We'll return empty array
                else:
                    raise  # Re-raise other Stripe errors

            # # Get cards saved in your DB
            # db_cards = self.get_queryset()
            # db_serializer = self.get_serializer(db_cards, many=True)
            
            # You could merge DB cards with Stripe cards here if needed

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Cards retrieved successfully",
                "data": combined_cards
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": str(e),
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class UpdateCardView(generics.UpdateAPIView):
    serializer_class = CardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        try:
            queryset = Card.objects.filter(user=self.request.user)
            if not queryset.exists():
                return Response({"statusCode": 200,
                "status": True,"message": "No cards found for the user"}, status=status.HTTP_200_OK)
            return queryset
        except Exception as e:
            return Response({"statusCode": 500,
                "status": False,"message": "Error fetching cards", "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response({"statusCode": 200,
                "status": True,"message": "Card updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"statusCode": 200,
                "status": True,"message": "Error updating card", "error": str(e)}, status=status.HTTP_200_OK)




class AdvertisementPaymentDetailView(APIView):
    def get(self, request, professional_id):
        try:
            ad_payments = AdvertisementPayment.objects.filter(payment__user_id=professional_id)
            if not ad_payments.exists():
                return Response({
                    "message": "No payments found for the given Professional User.",
                    "statusCode": 404,
                    "status": False,
                    "data": []
                }, status=status.HTTP_200_OK)

            serializer = AdvertisementPaymentSerializer(ad_payments, many=True)
            return Response({
                "message": "Advertisement payments fetched successfully.",
                "statusCode": 200,
                "status": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": f"An error occurred: {str(e)}",
                "statusCode": 500,
                "status": False,
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class PaymentListView(APIView):
    def get(self, request):
        try:
            payments = AdvertisementPayment.objects.all()
            if not payments.exists():
                return Response({
                    "message": "No payments found.",
                    "statusCode": 404,
                    "status": False,
                    "data": []
                }, status=status.HTTP_200_OK)

            serializer = AdvertisementPaymentSerializer(payments, many=True)
            return Response({
                "message": "Payments fetched successfully.",
                "statusCode": 200,
                "status": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": f"An error occurred: {str(e)}",
                "statusCode": 500,
                "status": False,
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateStripeCustomerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            professional_user = ProfessionalUser.objects.get(id=user.id)

            if professional_user.stripe_customer_id:
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Customer already exists",
                    "customer_id": professional_user.stripe_customer_id
                }, status=status.HTTP_200_OK)

            # Create Stripe customer
            customer = stripe.Customer.create(
                name=professional_user.userName,
                email=professional_user.email,
                metadata={
                    "user_professional_id": professional_user.id
                }
            )

            # Save customer ID to DB
            professional_user.stripe_customer_id = customer.id
            professional_user.save()

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Stripe customer created successfully",
                "customerId": customer.id
            }, status=status.HTTP_201_CREATED)

        except ProfessionalUser.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Professional user not found"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
def attach_payment_method(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            payment_method_id = data.get("paymentMethodId")
            customer_id = data.get("customerId")

            # 1. Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )

            # 2. Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    "default_payment_method": payment_method_id
                }
            )

            return JsonResponse({
                "statusCode": 200,
                "status": False,
                "message": "Card attached successfully"
             }, status=status.HTTP_200_OK)

        except Exception as e:
            return JsonResponse({
                "statusCode": 500,
                "status": False,
                "error": str(e)
            }, status=status.HTTP_200_OK)

    return JsonResponse({"statusCode": 500,
                "status": False,
                "error": "Invalid request method."}, status=405)


class PayOrderWithSavedCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id):
        user = request.user
        try:
            order = get_object_or_404(Order, id=order_id, user=user)

            if order.is_paid:
                return Response({"message": "Order already paid."}, status=400)

            payment_method_id = request.data.get("paymentMethodId",None)
            paymentType = request.data.get("paymentType",None)
            if paymentType.lower()=="card":
                if not payment_method_id:
                    return Response({"message": "Payment method ID is required."}, status=400)

                try:
                    # Get or create Stripe customer
                    if not user.stripeOrderCustomerId:
                        customer = stripe.Customer.create(email=user.email)
                        user.stripeOrderCustomerId = customer.id
                        user.save()

                    # Create and confirm the payment
                    intent = stripe.PaymentIntent.create(
                        amount=int(order.total_price * 100),  # Convert to cents
                        currency="usd",
                        customer=user.stripeOrderCustomerId,
                        payment_method=payment_method_id,
                        off_session=True,  # Required for saved card without user interaction
                        confirm=True,
                        metadata={"order_id": order.id},
                    )
                    if intent.status == "succeeded":
                            # Mark order as paid
                        order.is_paid = True
                        order.save()
                        return Response({
                        "status": True,
                        "statusCode": 200,
                        "message": "Payment successful",
                        "payment_intent_id": intent.id
                        
                        }, status=status.HTTP_200_OK)

                except stripe.error.CardError as e:
                    return Response({
                        "status": False,
                        "message": f"Card error: {str(e)}"
                    }, status=status.HTTP_200_OK)
                except stripe.error.StripeError as e:
                    return Response({
                        "status": False,
                        "statusCode": 400,
                        "message": f"Stripe error: {str(e)}"
                    }, status=status.HTTP_200_OK)
            elif paymentType.lower()=="cash":     
                try:
                    pass 
                except Exception as e:
                    return Response({
                        "status": False,
                        "statusCode": 500,
                        "message": f"Error: {str(e)}"
                }, status=status.HTTP_200_OK)
        except Exception as e:
                    return Response({
                        "status": False,
                        "statusCode": 500,
                        "message": f"Error: {str(e)}"
                }, status=status.HTTP_200_OK)

class CreateUserOrderStripeCustomerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            userqueryset = Users.objects.get(id=user.id)

            if userqueryset.stripeOrderCustomerId:
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Customer already exists",
                    "customer_id": userqueryset.stripeOrderCustomerId
                }, status=status.HTTP_200_OK)

            # Create Stripe customer
            customer = stripe.Customer.create(
                name=userqueryset.username,
                email=userqueryset.email,
                metadata={
                    "user_id": userqueryset.id
                }
            )

            # Save customer ID to DB
            userqueryset.stripeOrderCustomerId = customer.id
            userqueryset.save()

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Stripe customer created successfully",
                "customerId": customer.id
            }, status=status.HTTP_201_CREATED)

        except ProfessionalUser.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Professional user not found"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

import uuid


def generate_transaction_id():
    return f"TXN{uuid.uuid4().hex[:10].upper()}"

# class MakeOrderPaymentAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         user = request.user
#         print(request.data)
#         order_id = request.data.get("orderId")

#         payment_mode = request.data.get("paymentMode") 
#         stripe_payment_id = request.data.get("stripePaymentId")  
#         try:

#             if not order_id or not payment_mode:
#                 return Response({"status": False,"statusCode":400, "message": "Missing orderId or paymentMode."}, status=status.HTTP_200_OK)

#             booking = None
#             booking_type = None
#             print("order_id", order_id)

#             if relaxationBooking.objects.filter(booking_id=order_id, user=user).exists():
#                 booking = relaxationBooking.objects.get(booking_id=order_id, user=user)
#                 booking_type = 'relaxation'
#                 print("Relaxation booking found")
#             elif artandcultureBooking.objects.filter(booking_id=order_id, user=user).exists():
#                 booking = artandcultureBooking.objects.get(booking_id=order_id, user=user)
#                 booking_type = 'artandculture'
#                 print("Art and culture booking found")
#             elif aestheticsBooking.objects.filter(booking_id=order_id, user=user).exists():
#                 booking = aestheticsBooking.objects.get(booking_id=order_id, user=user)
#                 booking_type = 'asthetics'
#                 print("asthetics booking found")
#             elif eventBooking.objects.filter(booking_id=order_id, user=user).exists():
#                 booking = eventBooking.objects.get(booking_id=order_id, user=user)
#                 booking_type = 'event'
#                 print("event booking found")
#             elif experienceBooking.objects.filter(booking_id=order_id, user=user).exists():
#                 booking = experienceBooking.objects.get(booking_id=order_id, user=user)
#                 booking_type = 'experience'
#                 print("experience booking found")
#             elif slotBooking.objects.filter(booking_id=order_id, user=user).exists():
#                 booking = slotBooking.objects.get(booking_id=order_id, user=user)
#                 booking_type = 'slot'
#                 print("slot booking found")
#             elif RoomBooking.objects.filter(booking_id=order_id, user=user).exists():
#                 booking = RoomBooking.objects.get(booking_id=order_id, user=user)
#                 booking_type = 'room'
#                 print("room booking found")
#             else:
#                 print("Booking is not found in booking")
#                 return Response({
#                     "status": False,
#                     "statusCode": 400,
#                     "message": "Booking not found."
#                 }, status=status.HTTP_200_OK)


#             if booking_type == 'relaxation':
#                 if booking.is_paid:
#                     return Response({"status": False, "statusCode":400, "message": "Booking already paid."}, status=status.HTTP_200_OK)
#                 print("booking is not found in art and culture booking")
#                 # Get professional user by company
#                 try:
#                     print("--------------------------------------------------")
#                     professional_user = ProfessionalUser.objects.get(company=booking.company)
#                     print("professional_user is found",professional_user)
#                 except ProfessionalUser.DoesNotExist:
#                     return Response({"status": False, "statusCode": 400, "message": "Invalid company user for booking."}, status=status.HTTP_200_OK)

#                 base_price = booking.price or Decimal('0.00')
#                 # MINIMUM_AMOUNT_EUR = Decimal('0.50')
#                 discount = Decimal('0.00')  # You can add promo code or discount logic here if you want
#                 tax = Decimal('0.00')       # Add tax logic if needed
#                 total_price = max(base_price - discount + tax, Decimal('0.00'))
#                 product_summary = f"Booking {booking.booking_id} for {booking.full_name}"
#                 print("product_summary----------",product_summary)
#                 print("total_price",total_price)
#                 print("payment_mode",payment_mode)
#                 if payment_mode.lower() == "card":
#                     try:
                        
#                         # if total_price < MINIMUM_AMOUNT_EUR:
#                         #     return Response({
#                         #         "status": False,
#                         #         "statusCode": 400,
#                         #         "message": f"Amount must be at least {MINIMUM_AMOUNT_EUR} EUR for card payments."
#                         #     }, status=status.HTTP_200_OK)
        
#                         if not user.stripeOrderCustomerId:
#                             customer = stripe.Customer.create(email=user.email)
#                             user.stripeOrderCustomerId = customer.id
#                             user.save()

#                         intent = stripe.PaymentIntent.create(
#                             amount=int(total_price * 100),
#                             currency="eur",
#                             customer=user.stripeOrderCustomerId,
#                             payment_method=stripe_payment_id,
#                             off_session=True,
#                             confirm=True,
#                             metadata={"booking_id": booking.id},
#                         )

#                         if intent.status == "succeeded":
#                             # mark booking as paid and record payment
#                             return self._record_successful_payment(
#                                 user, professional_user, booking, total_price, base_price, discount, tax,
#                                 payment_mode, "succeeded", product_summary, stripe_payment_id, booking_type
#                             )
#                     except stripe.error.CardError as e:
#                         return Response({"status": False,"statusCode":400 , "message": f"Card error: {str(e)}"}, status=status.HTTP_200_OK)
#                     except stripe.error.StripeError as e:
#                         return Response({"status": False, "statusCode":400 ,"message": f"Stripe error: {str(e)}"}, status=status.HTTP_200_OK)

#                 elif payment_mode.lower() == "cash":
#                     return self._record_successful_payment(
#                         user, professional_user, booking, total_price, base_price, discount, tax,
#                         payment_mode, "succeeded", product_summary, booking_type=booking_type
#                     )

#                 else:
#                     return Response({"status": False,"statusCode":400, "message": "Unsupported payment mode."}, status=status.HTTP_200_OK)
                
            
#             if not order_id or not payment_mode:
#                 return Response({"status": False,"statusCode":400, "message": "Missing orderId or paymentMode."}, status=status.HTTP_200_OK)
            

#             order = get_object_or_404(Order, order_id=order_id, user=user)
#             if not order.order_id:
#                 return Response({"status": False, "statusCode":400 ,"message": "Order id not found."}, status=status.HTTP_200_OK)
                
            
#             if order.is_paid:
#                 return Response({"status": False, "statusCode":400 ,"message": "Order already paid."}, status=status.HTTP_200_OK)

#             order_items = OrderItem.objects.filter(order=order)
            
#             base_price = sum(item.price * item.quantity for item in order_items)
#             discount = Decimal(order.promo_code.specificAmount) if order.promo_code and order.promo_code.specificAmount else Decimal('0.00')
#             tax = Decimal('0.00')  # Add your tax calculation logic here
#             total_price = max(base_price - discount + tax, Decimal('0.00'))

#             product_summary = ", ".join([f"{item.product.productname} x{item.quantity}" for item in order_items])
           
#             try:
#                 professional_user = ProfessionalUser.objects.get(company=order.company)
#             except ProfessionalUser.DoesNotExist:
#                 order.delete()
#                 return Response({"status": False, "statusCode": 400, "message": "Invalid company user. Order deleted."}, status=status.HTTP_200_OK)

#             if payment_mode.lower() == "card":
#                 try:
#                     print("using card payment")
#                     if not user.stripeOrderCustomerId:
#                         customer = stripe.Customer.create(email=user.email)
#                         user.stripeOrderCustomerId = customer.id
#                         user.save()
#                     print("stripe payment is stared.....")
#                     intent = stripe.PaymentIntent.create(
#                         amount=int(total_price * 100),  
#                         currency="eur",
#                         customer=user.stripeOrderCustomerId,
#                         payment_method=stripe_payment_id,
#                         off_session=True,
#                         confirm=True,
#                         metadata={"order_id": order.id},
#                     )
#                     print("respnse;;;")

#                     if intent.status == "succeeded":
#                         return self._record_successful_payment(
#                             user, professional_user, order, total_price, base_price, discount, tax,
#                             payment_mode, "succeeded", product_summary, stripe_payment_id
#                         )

#                 except stripe.error.CardError as e:
#                     print("errorrrrr")
#                     return Response({"status": False,"statusCode":400 , "message": f"Card error: {str(e)}"}, status=status.HTTP_200_OK)
#                 except stripe.error.StripeError as e:
#                     print("erorro is >>>")
#                     return Response({"status": False, "statusCode":400 ,"message": f"Stripe error: {str(e)}"}, status=status.HTTP_200_OK)

#             elif payment_mode.lower() == "cash":
#                 return self._record_successful_payment(
#                     user, professional_user, order, total_price, base_price, discount, tax,
#                     payment_mode, "succeeded", product_summary
#                 )

#             else:
#                 order.delete()
#                 return Response({"status": False,"statusCode":400, "message": "Unsupported payment mode."}, status=status.HTTP_200_OK)
#             return
#         except Exception as e:
#             if 'order' in locals():
#                 order.delete()
#             return Response({"status": False, "statusCode":500 ,"message": f" error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def _record_successful_payment(self, user, professional_user, order, total_price, base_price, discount, tax,
#                                    payment_mode, status, product_summary, stripe_payment_id=None):

#         if hasattr(order, 'is_paid'):
#             order.is_paid = True
#             order.save()
#         elif hasattr(order, 'is_paid'):
#             order.is_paid = True
#             order.save()

#         print("payment_mode",payment_mode)
#         payment_mode=payment_mode.lower()
#         transaction_id = generate_transaction_id()
#         user_payment = UserPayment.objects.create(
#             user=user,
#             professional_user=professional_user,
#             stripe_payment_id=stripe_payment_id if payment_mode == "card" else None,
#             order=order,
#             amount=total_price,
#             base_price=base_price,
#             discount=discount,
#             tax=tax,
#             payment_mode=payment_mode.lower(),
#             currency=getattr(order, "currency", "EURO"),
#             status=status,
#             product_summary=product_summary,
#             payment_direction="debited",
#             transaction_id = transaction_id
            
#         )

#         ProfessionalUserTransactionLog.objects.create(
#             paid_by=user,
#             paid_to=professional_user,
#             payment=user_payment,
#             order=order,
#             amount=total_price,
#             base_price=base_price,
#             discount=discount,
#             tax=tax,
#             payment_mode=payment_mode,
#             product_summary=product_summary,
#             status="credited",
#             paymentStatus="succeeded",
#             transaction_id = transaction_id
#         )
        
#         Cart.objects.filter(user=user, company=order.company, order_type=order.order_type).delete()
#         return Response({
#             "status": True,
#             "statusCode":200,
#             "message": "Payment successful.",
#             "payment_id": user_payment.id,
#             "amount": str(total_price),
#             "payment_mode": payment_mode,
#             "product_summary": product_summary
#         }, status=200)

class MakeOrderPaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data
        order_id = data.get("orderId")
        payment_mode = data.get("paymentMode")
        stripe_payment_id = data.get("stripePaymentId")

        if not order_id or not payment_mode:
            return self._response(False, 400, "Missing orderId or paymentMode.")

        try:
            booking, booking_type = self._get_booking(order_id, user)
            if booking:
                if booking.is_paid:
                    return self._response(False, 400, "Booking already paid.")
                
                professional_user = self._get_professional_user(booking.company)
                if not professional_user:
                    return self._response(False, 400, "Invalid company user for booking.")

                return self._handle_payment(
                    user=user,
                    professional_user=professional_user,
                    order=booking,
                    payment_mode=payment_mode,
                    stripe_payment_id=stripe_payment_id,
                    is_booking=True,
                    summary=f"Booking {booking.booking_id}"
                )
            else:
                # Try as regular order
                order = get_object_or_404(Order, order_id=order_id, user=user)
                if order.is_paid:
                    return self._response(False, 400, "Order already paid.")
                
                professional_user = self._get_professional_user(order.company)
                if not professional_user:
                    order.delete()
                    return self._response(False, 400, "Invalid company user. Order deleted.")

                summary = ", ".join([f"{item.product.productname} x{item.quantity}" for item in order.order_items.all()])
                return self._handle_payment(
                    user=user,
                    professional_user=professional_user,
                    order=order,
                    payment_mode=payment_mode,
                    stripe_payment_id=stripe_payment_id,
                    is_booking=False,
                    summary=summary
                )

        except Exception as e:
            if 'order' in locals() and not booking:
                order.delete()
            return self._response(False, 500, f"Error: {str(e)}")

    # ---------------- HELPER METHODS ---------------- #

    def _get_booking(self, order_id, user):
        booking_models = {
            'relaxation': relaxationBooking,
            'artandculture': artandcultureBooking,
            'asthetics': aestheticsBooking,
            'event': eventBooking,
            'experience': experienceBooking,
            'slot': slotBooking,
            'room': RoomBooking,
        }

        for key, model in booking_models.items():
            booking = model.objects.filter(booking_id=order_id, user=user).first()
            if booking:
                return booking, key
        return None, None

    def _get_professional_user(self, company):
        try:
            return ProfessionalUser.objects.get(company=company)
        except ProfessionalUser.DoesNotExist:
            return None

    def _handle_payment(self, user, professional_user, order, payment_mode, stripe_payment_id, is_booking, summary):
        order_items = order.order_items.all() if not is_booking else []
        if is_booking:
            base_price = getattr(order, 'total_price', getattr(order, 'price', Decimal('0.00')))
        else:
            base_price = sum(item.price * item.quantity for item in order_items)
        discount = Decimal('0.00') if is_booking else Decimal(order.promo_code.specificAmount) if order.promo_code else Decimal('0.00')
        tax = Decimal('0.00')
        total_price = max(base_price - discount + tax, Decimal('0.00'))

        if payment_mode.lower() == "card":
            try:
                if not user.stripeOrderCustomerId:
                    customer = stripe.Customer.create(email=user.email)
                    user.stripeOrderCustomerId = customer.id
                    user.save()

                intent = stripe.PaymentIntent.create(
                    amount=int(total_price * 100),
                    currency="eur",
                    customer=user.stripeOrderCustomerId,
                    payment_method=stripe_payment_id,
                    off_session=True,
                    confirm=True,
                    metadata={"order_id": order.id if not is_booking else None, "booking_id": order.id if is_booking else None},
                )

                if intent.status == "succeeded":
                    return self._record_successful_payment(user, professional_user, order, total_price, base_price, discount, tax, payment_mode, "succeeded", summary, stripe_payment_id)
                else:
                    return self._response(False, 400, "Payment failed.")

            except stripe.error.CardError as e:
                return self._response(False, 400, f"Card error: {str(e)}")
            except stripe.error.StripeError as e:
                return self._response(False, 400, f"Stripe error: {str(e)}")

        elif payment_mode.lower() == "cash":
            return self._record_successful_payment(user, professional_user, order, total_price, base_price, discount, tax, payment_mode, "succeeded", summary)

        else:
            if not is_booking:
                order.delete()
            return self._response(False, 400, "Unsupported payment mode.")

    def _record_successful_payment(self, user, professional_user, order, total_price, base_price, discount, tax,
                                   payment_mode, status, product_summary, stripe_payment_id=None):

        transaction_id = generate_transaction_id()
        order.is_paid = True
        is_booking = hasattr(order, "booking_id")
        if is_booking:
            if hasattr(order, "booking_status"):
                order.booking_status = "confirmed"  
            elif hasattr(order, "status"):
                order.status = "confirmed"
                
        order.save()

        
        payment_kwargs = dict(
            user=user,
            professional_user=professional_user,
            stripe_payment_id=stripe_payment_id if payment_mode == "card" else None,
            # order=order,
            amount=total_price,
            base_price=base_price,
            discount=discount,
            tax=tax,
            payment_mode=payment_mode,
            currency=getattr(order, "currency", "EURO"),
            status=status,
            product_summary=product_summary,
            payment_direction="debited",
            transaction_id=transaction_id
        )
        
        if is_booking:
            payment_kwargs["booking_type"] = order.__class__.__name__
            payment_kwargs["booking_id"] = getattr(order, "booking_id", None)
        else:
            payment_kwargs["order"] = order

        payment = UserPayment.objects.create(**payment_kwargs)
        
        ProfessionalUserTransactionLog.objects.create(
            paid_by=user,
            paid_to=professional_user,
            payment=payment,
            order=order if not is_booking else None,
            amount=total_price,
            base_price=base_price,
            discount=discount,
            tax=tax,
            payment_mode=payment_mode,
            product_summary=product_summary,
            status="credited",
            paymentStatus="succeeded",
            transaction_id=transaction_id
        )

        if not is_booking:  # Only clear cart for normal orders
            Cart.objects.filter(user=user, company=order.company, order_type=order.order_type).delete()

        return Response({
            "status": True,
            "statusCode": 200,
            "message": "Payment successful.",
            "payment_id": payment.id,
            "amount": str(total_price),
            "payment_mode": payment_mode,
            "product_summary": product_summary
        }, status=200)

    def _response(self, status_bool, status_code, message):
        return Response({
            "status": status_bool,
            "statusCode": status_code,
            "message": message
        }, status=status.HTTP_200_OK if status_code < 500 else status.HTTP_500_INTERNAL_SERVER_ERROR)



class GetUserOrderCardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            user = request.user
            print("Fetching cards for user:", user)

            if not user.stripeOrderCustomerId:
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "No customer account found",
                    "data": []
                }, status=status.HTTP_200_OK)

            combined_cards = []

            try:
                # Fetch saved Stripe cards
                stripe_cards = stripe.PaymentMethod.list(
                    customer=user.stripeOrderCustomerId,
                    type="card"
                )

                for stripe_card in stripe_cards.data:
                    combined_cards.append({
                        "payment_method_id": stripe_card.id,
                        "last4": stripe_card.card.last4,
                        "brand": stripe_card.card.brand,
                        "exp_month": stripe_card.card.exp_month,
                        "exp_year": stripe_card.card.exp_year,
                        "card_saved": True,
                        "card_number": f"XXXX-XXXX-XXXX-{stripe_card.card.last4}",
                        "expiry_date": f"{stripe_card.card.exp_month:02d}/{stripe_card.card.exp_year}"
                    })

            except stripe.error.InvalidRequestError as e:
                if hasattr(e, 'code') and e.code == "resource_missing":
                    # Customer does not exist in Stripe
                    pass
                else:
                    return Response({
                        "statusCode": 400,
                        "status": False,
                        "message": f"Stripe error: {str(e)}",
                        "data": []
                    }, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Cards retrieved successfully",
                "data": combined_cards
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"Internal server error: {str(e)}",
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        