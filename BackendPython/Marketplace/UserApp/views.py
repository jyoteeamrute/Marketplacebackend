import math
from collections import Counter
from datetime import datetime
from rest_framework.decorators import api_view, permission_classes
import requests
from botocore.exceptions import ClientError, NoCredentialsError
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404, render
from django.core.files.uploadedfile import UploadedFile
from django.core.mail import send_mail
from django.core.paginator import EmptyPage, Paginator
from django.db import DatabaseError, transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404,render
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince
from django.utils.timezone import now
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
import urllib.parse
from Admin.models import *
from Admin.serializers import *
from ProfessionalUser.models import *
from ProfessionalUser.serializers import *
from ProfessionalUser.signals import *
from ProfessionalUser.utils import *
from UserApp.models import *
from UserApp.serializers import *
from UserApp.tasks import upload_profile_image_to_s3
from UserApp.utils import *


class UserRegistrationAPIView(APIView):
    """API View for User Registration using new UserSerializer"""

    def post(self, request, *args, **kwargs):
        data = request.data.copy()

        def parse_ids(field):
            raw = request.data.get(field)
            if isinstance(raw, str):
                try:
                    return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
                except ValueError:
                    raise serializers.ValidationError({field: "All values must be valid integers."})
            elif isinstance(raw, list):
                try:
                    return [int(x) for x in raw if str(x).isdigit()]
                except ValueError:
                    raise serializers.ValidationError({field: "Invalid values found. Only integers are allowed."})
            return []
        data.setlist("multipleCountry", parse_ids("multipleCountry"))
        data.setlist("categories", parse_ids("categories"))
        data.setlist("subcategories", parse_ids("subcategories"))
        profile_img: UploadedFile = request.FILES.get("profileImage")
        identity_img: UploadedFile = request.FILES.get("identityCardImage")
        data["profileImage"] = profile_img
        data["identityCardImage"] = identity_img
        try:
            manual_address_data = json.loads(request.data.get("manualAddress")) if request.data.get("manualAddress") else None
            automatic_address_data = json.loads(request.data.get("automatic_address")) if request.data.get("automatic_address") else None
        except json.JSONDecodeError:
            return Response({"error": "Invalid address format. Use a valid JSON object."}, status=status.HTTP_200_OK)

        if not manual_address_data and not automatic_address_data:
            return Response(
                {"error": "Either manualAddress or automatic_address is required."},
                status=status.HTTP_200_OK
            )

        with transaction.atomic():
            serializer = UserSerializer(
                data=data,
                context={
                    "request": request,
                    "manual_address_data": manual_address_data,
                    "automatic_address_data": automatic_address_data,
                }
            )

            if serializer.is_valid():
                user = serializer.save()
                on_new_user_registered(user)

               

                # Async S3 uploads via Celery
                def upload_if_present(file, folder, field_name):
                    if file:
                        upload_profile_image_to_s3.delay(
                            file.read(), folder, str(user.id), field_name
                        )

                upload_if_present(profile_img, "profile_images", "profileImage")
                upload_if_present(identity_img, "identity_cards", "identityCardImage")
                refresh = RefreshToken()
                refresh['user_id'] = str(user.id)
                refresh['email'] = user.email
                refresh['user_type'] = "user"


                user_data = UserSerializer(user, context={"request": request}).data

                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "User created successfully!",
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": {
                        **user_data,
                        "categories": list(user.categories.values_list("id", flat=True)),
                        "subcategories": list(user.subcategories.values_list("id", flat=True)),
                        "multipleCountry": list(user.multipleCountry.values_list("id", flat=True)),
                    },
                }, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_200_OK)
class UserCreateAPIView(generics.CreateAPIView):
    """
    API View to create a new User.
    - Only authenticated users can create new users.
    - Automatically sets `created_by_user` and `created_by_user_id` based on the authenticated user.
    """
    queryset = Users.objects.all()
    serializer_class = AdminProUserSerializer
    permission_classes = [IsAuthenticated]
    

    def create(self, request, *args, **kwargs):
        try:
            data = request.data.copy()

            for field, model in [('categories', Category), ('subcategories', Subcategory), ('multipleCountry', Country)]:
                value = data.get(field)
                if value:
                    pk_list = [int(x.strip()) for x in value.split(',') if x.strip().isdigit()]
                    data.setlist(field, pk_list)
                else:
                    data.setlist(field, [])

            try:
                manual_address_data = json.loads(data.get('manualAddress', '{}'))
                automatic_address_data = json.loads(data.get('automatic_address', '{}'))
            except json.JSONDecodeError as e:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Invalid JSON in address fields: {str(e)}"
                }, status=status.HTTP_200_OK)

            if not manual_address_data and not automatic_address_data:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "User must have at least one address."
                }, status=status.HTTP_200_OK)

            serializer = self.get_serializer(
                data=data,
                context={
                    "request": request,
                    "manual_address_data": manual_address_data,
                    "automatic_address_data": automatic_address_data
                }
            )

            serializer.is_valid(raise_exception=True)

            authenticated_user = request.user
            role_name = getattr(authenticated_user.role, 'name', None)

            if not role_name:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "Role not found for the authenticated user."
                }, status=status.HTTP_200_OK)

            user = serializer.save(
                created_by_user=role_name,
                created_by_user_id=authenticated_user.id
            )

            return Response({
                "statusCode": 201,
                "status": True,
                "message": "User created successfully",
                "user": serializer.data,
            }, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": f"Validation Error: {str(e)}"
            }, status=status.HTTP_200_OK)

        except ObjectDoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Object not found."
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"An unexpected error occurred: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class LoginView(APIView):

    def post(self, request):
        """Authenticate user and return JWT tokens"""
        try:
            identifier = request.data.get("username") 
            password = request.data.get("password")

            if not identifier or not password:
                return Response(
                    {"statusCode": 400, "status": False, "message": "Email/Username and password are required"},
                    status=status.HTTP_200_OK
                )

            user = None

            if "@" in identifier:  # Identifier is an email
                try:
                    user = Users.objects.get(email=identifier)
                except Users.DoesNotExist:
                    return Response(
                        {"statusCode": 400, "status": False, "message": "User with this email does not exist"},
                        status=status.HTTP_200_OK
                    )
            else:  # Identifier is a username
                try:
                    user = Users.objects.get(username=identifier)
                except Users.DoesNotExist:
                    return Response(
                        {"statusCode": 400, "status": False, "message": "User with this username does not exist"},
                        status=status.HTTP_200_OK
                    )
            if not user.is_active:
                return Response(
                    {
                        "statusCode": 403,
                        "status": False,
                        "message": "Your account is currently deactivated.",
                        "warning_message": user.warning_message or "Please contact support for further assistance."
                    },
                    status=status.HTTP_200_OK
                )

            if not check_password(password, user.password):
                return Response(
                    {"statusCode": 400, "status": False, "message": "Invalid password"},
                    status=status.HTTP_200_OK
                )
            
            user.last_login = timezone.now()
            user.save(update_fields=["last_login"]) 
            refresh = RefreshToken()
            refresh["user_id"] = str(user.id)  
            refresh["user_type"]="users"
            refresh["email"] = user.email
            user_serializer = UserSerializer(user)

            return Response(
                {
                    "statusCode": 200,
                    "status": True,
                    "message": "Login successful",
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": user_serializer.data,
                    "role": str(user.role),
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"statusCode": 500, "status": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



class RefreshProfessionalUserAccessTokenView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Refresh access token using a valid refresh token for professional users.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["refresh"],
            properties={
                "refresh": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="Refresh token to generate a new access token"
                )
            }
        ),
        responses={
            200: openapi.Response(
                description="Access token refreshed successfully",
                examples={
                    "application/json": {
                        "status": True,
                        "access_token": "new_access_token_here"
                    }
                }
            ),
            400: openapi.Response(
                description="Invalid or expired refresh token",
                examples={
                    "application/json": {
                        "status": False,
                        "message": "Invalid or expired refresh token"
                    }
                }
            )
        }
    )
    def post(self, request):
        ip = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "unknown")
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            logger.warning(f"[Pro Refresh] Missing refresh token | IP: {ip}, UA: {user_agent}")
            return Response(
                {"statusCode": 400, "status": False, "message": "Refresh token is required"},
                status=status.HTTP_200_OK
            )

        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)
            logger.info(f"[Pro Refresh] Success | IP: {ip}")
            return Response(
                {"statusCode": 200, "status": True, "access_token": access_token},
                status=status.HTTP_200_OK
            )
        except TokenError:
            logger.warning(f"[Pro Refresh] Invalid/expired token | IP: {ip}, UA: {user_agent}")
            return Response(
                {"statusCode": 400, "status": False, "message": "Invalid or expired refresh token"},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"[Pro Refresh] Error: {str(e)} | IP: {ip}, UA: {user_agent}")
            return Response(
                {"statusCode": 500, "status": False, "message": "Unexpected error", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class SendOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        email = request.data.get('email')
        phone = request.data.get('phone')

        if not email and not phone:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Email or Phone is required"
            }, status=status.HTTP_200_OK)
        VerfyOTP.objects.filter(user=request.user).delete()
        otp_obj = VerfyOTP(
            user=request.user,
            email=email,
            phone=phone
        )
        otp_obj.generateOtp()
        print(f"[DEV] OTP sent: {otp_obj.otpCode}")

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "OTP sent successfully",
            "otp": otp_obj.otpCode  # Remove in production
        }, status=status.HTTP_200_OK)

class VerifyUserOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        email = request.data.get("email")
        phone = request.data.get("phone")
        otp_code = request.data.get("otp")

        if not otp_code:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "OTP is required"
            }, status=status.HTTP_200_OK)
        otp_instance = VerfyOTP.objects.filter(user=request.user, otpCode=otp_code).first()

        if not otp_instance:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Invalid OTP or not for this user"
            }, status=status.HTTP_200_OK)

        if otp_instance.isExpired():
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "OTP expired"
            }, status=status.HTTP_200_OK)
        user = request.user
        if email:
            if user.email != email:
                user.email = email
            user.is_email_verified = True
            user.save()
        if phone:
            if user.phone != phone:
                user.phone = phone
            user.is_phone_verified = True
            user.save()
        otp_instance.delete()

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "OTP verified successfully",
            "user_id": user.id
        }, status=status.HTTP_200_OK)

class UserVerificationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        email_verified = user.is_email_verified
        email = user.email
        phone_verified = user.is_phone_verified
        phone = user.phone
        if user.identityCardImage:
            if user.id_card_verified:
                id_verified = True
                id_message = "verified"
            elif user.updatedAt and (timezone.now() - user.updatedAt) < timedelta(hours=24):
                id_verified = False
                id_message = "Wait for 24 hours"
            else:
                id_verified = False
                id_message = "Pending ,please wait"
        else:
            id_verified = False
            id_message = "Document not uploaded yet"

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Verification status retrieved successfully",
            "email": {
                "email": email,
                "email_verified": email_verified
            },
            "phone": {
                "phone": phone,
                "phone_verified": phone_verified
            },
            "idcard": {
                "idcard": user.identityCardImage.url if user.identityCardImage else None,
                "id_verified": id_verified,
                "verifymessage": id_message
            }
        }, status=status.HTTP_200_OK)
    


class UserListAPIView(APIView):

    def get(self, request):
        users = Users.objects.all()  # Corrected the model name
        serializer = UserSerializer(users, many=True)  # Use the correct serializer name
        return Response({
            "statusCode":200,
            "status": True,
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    



class VerifyOTPView(APIView):

    @swagger_auto_schema(
        operation_description="Verify OTP without requiring email or phone input",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["otp"],  # Only OTP is required now
            properties={
                "otp": openapi.Schema(type=openapi.TYPE_STRING, description="One-time password (OTP)"),
            },
        ),
        responses={
            200: openapi.Response("OTP verified successfully"),
            400: "Invalid OTP or expired",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        """Verify OTP without requiring email or phone number"""
        otp_code = request.data.get("otp")
        
        try:
            if not otp_code:
                return Response(
                    {"statusCode": 400, "status": False, "message": "OTP is required"},
                    status=status.HTTP_200_OK
                )
            otp_instance = OTP.objects.filter(otpCode=otp_code).first()

            if not otp_instance:
                return Response(
                    {"statusCode": 400, "status": False, "message": "Invalid OTP"},
                    status=status.HTTP_200_OK
                )

            if otp_instance.isExpired():
                return Response(
                    {"statusCode": 400, "status": False, "message": "OTP Expired"},
                    status=status.HTTP_200_OK
                )
            user = otp_instance.user

            otp_instance.delete()  # Delete OTP after successful verification

            return Response(
                {
                    "statusCode": 200,
                    "status": True,
                    "message": "OTP verified successfully.",
                    "user_id": user.id
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"statusCode": 500, "status": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class ResendOTPView(APIView):

    @swagger_auto_schema(
        operation_description="Resend OTP to the user's email",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["email"],
            properties={
                "email": openapi.Schema(type=openapi.TYPE_STRING, description="User email"),
            },
        ),
        responses={
            200: openapi.Response("New OTP sent successfully"),
            400: "Email is required",
            404: "User not found",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response(
                {"statusCode": 400, "status": False, "message": "Email is required"},
                status=status.HTTP_200_OK
            )

        try:
            user = Users.objects.get(email=email)
            OTP.objects.filter(user=user).delete()
            otpCode = str(random.randint(1000, 9999))
            otp_entry = OTP.objects.create(user=user, otpCode=otpCode, createdAt=timezone.now())
            send_mail(
                subject="Your OTP Code",
                message=f"Your new OTP is: {otp_entry.otpCode}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

            return Response(
                {
                    "statusCode": 200,
                    "status": True,
                    "message": "New OTP sent successfully",
                    "otp": otp_entry.otpCode  # Include OTP for testing (remove in production)
                },
                status=status.HTTP_200_OK
            )

        except Users.DoesNotExist:
            return Response(
                {"statusCode": 404, "status": False, "message": "User not found"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"statusCode": 500, "status": False, "message": "Internal Server Error", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class ForgetPasswordView(APIView):

    @swagger_auto_schema(
        operation_description="Request OTP for password reset using email or phone",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["identifier"],  # Only one required: email or phone
            properties={
                "identifier": openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    description="User's registered email or phone number"
                ),
            },
        ),
        responses={
            200: openapi.Response("OTP sent successfully"),
            400: "Identifier (Email or Phone) is required",
            404: "User not found",
            500: "Internal Server Error",
        },
    )
    def post(self, request):
        """Send OTP to user's email or phone for password reset"""
        
        try:
            identifier = request.data.get("email")  # Can be email or phone

            if not identifier:
                return Response(
                    {"statusCode": 400, "status": False, "message": "Email or Phone is required"},
                    status=status.HTTP_200_OK
                )
            user = None
            if "@" in identifier:  # If it contains '@', assume it's an email
                user = Users.objects.filter(email=identifier).first()
            elif identifier.isdigit() and len(identifier) >= 8:  # Basic phone number validation
                user = Users.objects.filter(phone=identifier).first()

            if not user:
                return Response(
                    {"statusCode": 404, "status": False, "message": "User not found"},
                    status=status.HTTP_200_OK
                )
            OTP.objects.filter(user=user).delete()
            otpCode = str(random.randint(1000, 9999))
            OTP.objects.create(user=user, otpCode=otpCode, createdAt=timezone.now())
            if "@" in identifier:
                send_mail(
                    subject="Reset Password OTP",
                    message=f"Your OTP for password reset is: {otpCode}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                return Response(
                    {"statusCode": 200, "status": True, "message": "OTP sent successfully", "OtpCode": otpCode},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"statusCode": 200, "status": True, "message": "OTP sent to your phone"},
                    status=status.HTTP_200_OK
                )

        except Exception as e:
            return Response(
                {"statusCode": 500, "status": False, "message": "Internal Server Error", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class ResetPasswordView(APIView):
    @swagger_auto_schema(
        operation_description="Reset a user's password without authentication.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["user_id", "new_password"],
            properties={
                "user_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="User's ID"),
                "new_password": openapi.Schema(type=openapi.TYPE_STRING, description="New password for the user"),
            },
        ),
        responses={
            200: openapi.Response("Password reset successful"),
            400: openapi.Response("User ID and new password are required"),
            404: openapi.Response("User not found"),
            500: openapi.Response("Internal Server Error"),
        },
    )
    def post(self, request):
        try:
            user_id = request.data.get("user_id")
            new_password = request.data.get("new_password")


            if not user_id or not new_password:
                return Response(
                    {"statusCode": 400, "status": False, "message": "User ID and new password are required"},
                    status=status.HTTP_200_OK
                )

            try:
                user = Users.objects.get(id=user_id)
            except Users.DoesNotExist:
                return Response(
                    {"statusCode": 404, "status": False, "message": "User not found"},
                    status=status.HTTP_200_OK
                )

            user.password = make_password(new_password)
            user.save()

            return Response(
                {"statusCode": 200, "status": True, "message": "Password reset successful. Please log in again."},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"statusCode": 500, "status": False, "message": "Internal Server Error", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class UpdatePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        try:
            user = request.user
            if not isinstance(user, Users):
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Invalid user instance."
                }, status=status.HTTP_200_OK)

            serializer = UpdatePasswordSerializer(data=request.data, context={"request": request})

            if serializer.is_valid():
                user.password = make_password(serializer.validated_data["new_password"])
                user.save()

                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Password updated successfully"
                }, status=status.HTTP_200_OK)

            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Password update failed",
                "errors": serializer.errors
            }, status=status.HTTP_200_OK)

        except Users.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "User not found."
            }, status=status.HTTP_200_OK)

        except KeyError as e:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": f"Missing required field: {str(e)}"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred!",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetUserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve the profile of the authenticated user using the auth token.",
        responses={
            200: openapi.Response("Success", UserRegistrationSerializer),
            401: openapi.Response("Unauthorized"),
            500: openapi.Response("Internal Server Error"),
        }
    )
    def get(self, request):
        try:
            user = request.user
            serializer = UserRegistrationSerializer(user)
            user_content_type = ContentType.objects.get_for_model(user)
            followers_count = Friendship.objects.filter(
                receiver_object_id=user.id,
                receiver_content_type=user_content_type,
                relationship_type="follow",
                status__in=["accepted", "message","follow"]   # ← lowercase!
            ).count()
            following_count = Friendship.objects.filter(
                sender_object_id=user.id,
                sender_content_type=user_content_type,
                relationship_type="follow",
                status__in=["accepted", "message","follow"]  # ← treat "message" as accepted/following
            ).count()


            response_data = {
                "statusCode": 200,
                "status": True,
                "message": "User profile fetched successfully.",
                "data": {
                    "user_id": user.id,
                    "full_name": f"{user.firstName} {user.lastName}",
                    "email": user.email,
                    "phone": getattr(user, "phone_number", None),
                    "followers_count": followers_count,
                    "following_count": following_count,
                    "phone": user.phone,
                    "firstName": user.firstName,
                    "lastName": user.lastName,
                    "countryCode": user.countryCode,
                    "dob": "2006-05-04",
                    "gender": user.gender,
                    "manualAddress": AddressSerializer(user.manualAddress).data if user.manualAddress else None,
                    "automatic_address": AddressSerializer(user.automatic_address).data if user.automatic_address else None,
                    "profileImage": user.profileImage.url if user.profileImage else None,
                    "profile_url": request.build_absolute_uri(
    reverse("public-user-profile", args=[user.id, user.username])
)
                        }
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {
                    "statusCode": 500,
                    "status": False,
                    "message": f"An error occurred: {str(e)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PublicUserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id,username):
        try:
            viewer = request.user
            user = Users.objects.get(id=user_id)

            if viewer.id == user.id:
                follow_status = "self"
            else:
                viewer_ct = ContentType.objects.get_for_model(viewer)
                user_ct = ContentType.objects.get_for_model(user)

                friendship = Friendship.objects.filter(
                    sender_object_id=viewer.id,
                    sender_content_type=viewer_ct,
                    receiver_object_id=user.id,
                    receiver_content_type=user_ct,
                    relationship_type="follow"
                ).first()

                if friendship:
                    follow_status = friendship.status  # "Accepted", "Requested", etc.
                else:
                    follow_status = "not_following"

            user_ct = ContentType.objects.get_for_model(user)

            followers_count = Friendship.objects.filter(
                receiver_object_id=user.id,
                receiver_content_type=user_ct,
                relationship_type="follow",
                status="Accepted"
            ).count()

            following_count = Friendship.objects.filter(
                sender_object_id=user.id,
                sender_content_type=user_ct,
                relationship_type="follow",
                status="follow"
            ).count()

            response_data = {
                "statusCode": 200,
                "status": True,
                "message": "Public profile fetched successfully.",
                "data": {
                    "user_id": user.id,
                    "full_name": f"{user.firstName} {user.lastName}",
                    "profileImage": user.profileImage.url if user.profileImage else None,
                    "followers_count": followers_count,
                    "following_count": following_count,
                    "follow_status": follow_status
                }
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Users.DoesNotExist:
            return Response(
                {
                    "statusCode": 404,
                    "status": False,
                    "message": "User not found"
                },
                status=status.HTTP_200_OK
            )
        

class UserProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Update user profile with all available fields.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["id"],  
            properties={
                "username": openapi.Schema(type=openapi.TYPE_STRING, description="Updated username"),
                "email": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_EMAIL, description="Updated email"),
                "phone": openapi.Schema(type=openapi.TYPE_STRING, description="Updated phone number"),
                "firstName": openapi.Schema(type=openapi.TYPE_STRING, description="Updated first name"),
                "lastName": openapi.Schema(type=openapi.TYPE_STRING, description="Updated last name"),
                "language": openapi.Schema(type=openapi.TYPE_INTEGER, description="Language ID"),
                "identityCardImage": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY, description="Upload identity card image"),
                "countryCode": openapi.Schema(type=openapi.TYPE_STRING, description="Updated country code"),
                "dob": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATE, description="Updated date of birth"),
                "gender": openapi.Schema(
                    type=openapi.TYPE_STRING, 
                    enum=["male", "female", "other"],
                    description="Updated gender"
                ),
                "manualAddress": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "address1": openapi.Schema(type=openapi.TYPE_STRING, description="Address Line 1"),
                        "address2": openapi.Schema(type=openapi.TYPE_STRING, description="Address Line 2"),
                        "postalCode": openapi.Schema(type=openapi.TYPE_STRING, description="Postal Code"),
                        "city": openapi.Schema(type=openapi.TYPE_STRING, description="City"),
                    },
                    description="Updated manual address details"
                ),
                "categories": openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description="List of Category IDs"),
                "subcategories": openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description="List of Subcategory IDs"),
                "multipleCountry": openapi.Schema(type=openapi.TYPE_STRING, description="Comma-separated country IDs"),
                "termCondition": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Accept terms and conditions"),
                "marketingReference": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Marketing reference preference"),
                "profileImage": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_BINARY, description="Upload profile image"),
                "role": openapi.Schema(type=openapi.TYPE_INTEGER, description="User role ID")
            }
        ),
        responses={
            200: openapi.Response("Profile updated successfully!", UserUpdateSerializer),
            400: "Bad Request (Invalid data or missing fields)",
            403: "Forbidden (Only the owner can update profile)",
            500: "Internal Server Error"
        },
    )
    
    def put(self, request):
        try:
            user_id = request.query_params.get("id")
            
            if not user_id:
                return Response(
                    {"statusCode": 400, "status": False, "message": "User ID is required"},
                    status=status.HTTP_200_OK
                )

            try:
                user = Users.objects.get(id=user_id)
                
            except Users.DoesNotExist:
                return Response(
                    {"statusCode": 404, "status": False, "message": "User not found"},
                    status=status.HTTP_200_OK
                )
           
            if int(user_id) != int(request.user.id):
                return Response(
                    {"statusCode": 403, "status": False, "message": "You can only update your own profile"},
                    status=status.HTTP_200_OK
                )
                
            manual_address_data = request.data.get("manualAddress", None)
            automatic_address_data = request.data.get("automatic_address", None)
            
            
            if isinstance(manual_address_data, str):
                try:
                    manual_address_data = json.loads(manual_address_data)
                except json.JSONDecodeError:
                    return Response(
                        {"statusCode": 400, "status": False, "message": "Invalid manualAddress format"},
                        status=status.HTTP_200_OK
                    )

            if isinstance(automatic_address_data, str):
                try:
                    automatic_address_data = json.loads(automatic_address_data)
                except json.JSONDecodeError:
                    return Response(
                        {"statusCode": 400, "status": False, "message": "Invalid automatic_address format"},
                        status=status.HTTP_200_OK
                    )

            
            def parse_csv_string(value):
                return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()] if isinstance(value, str) else []

            multiple_countries = parse_csv_string(request.data.get("multipleCountry", ""))
            categories = parse_csv_string(request.data.get("categories", ""))
            subcategories = parse_csv_string(request.data.get("subcategories", ""))

            update_fields = {}

            if categories:
                valid_categories = Category.objects.filter(id__in=categories)
                if valid_categories.count() != len(categories):
                    return Response(
                        {"statusCode": 404, "status": False, "message": "One or more categories not found"},
                        status=status.HTTP_200_OK
                    )
                update_fields["categories"] = valid_categories

            if subcategories:
                valid_subcategories = Subcategory.objects.filter(id__in=subcategories)
                if valid_subcategories.count() != len(subcategories):
                    return Response(
                        {"statusCode": 404, "status": False, "message": "One or more subcategories not found"},
                        status=status.HTTP_200_OK
                    )
                update_fields["subcategories"] = valid_subcategories
            serializer = UserUpdateSerializer(user, data=request.data, partial=True, context={"request": request})
            
            if serializer.is_valid():
                with transaction.atomic():  # Ensures atomic updates
                    serializer.save()

                    if "categories" in update_fields:
                        user.categories.set(update_fields["categories"])
                    if "subcategories" in update_fields:
                        user.subcategories.set(update_fields["subcategories"])
                    if multiple_countries:
                        user.multipleCountry.set(Country.objects.filter(id__in=multiple_countries))

                    user.save()

                    if manual_address_data:
                        if user.manualAddress:
                            for key, value in manual_address_data.items():
                                setattr(user.manualAddress, key, value)
                            user.manualAddress.save()
                        else:
                            user.manualAddress = Address.objects.create(**manual_address_data)
                            user.save()
                    if automatic_address_data:
                        if user.automatic_address:
                            for key, value in automatic_address_data.items():
                                setattr(user.automatic_address, key, value)
                            user.automatic_address.save()
                        else:
                            user.automatic_address = Address.objects.create(**automatic_address_data)
                            user.save()
            
                
                return Response(
                    {
                        "statusCode": 200,
                        "status": True,
                        "message": "Profile updated successfully",
                        "user": serializer.data
                    },
                    status=status.HTTP_200_OK
                )
                

            return Response(
                {"statusCode": 400, "status": False, "message": "Invalid data", "errors": serializer.errors},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"statusCode": 500, "status": False, "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.delete()
        return Response(
            {
                "statusCode": 200,
                "status": True,
                "message": "User deleted successfully."
            },
            status=status.HTTP_200_OK
        )
class GetAutomaticAddress(APIView):

    @swagger_auto_schema(
        operation_description="Get an automatic address from latitude and longitude using Google Maps API.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "latitude": openapi.Schema(type=openapi.TYPE_NUMBER, description="Latitude of the location"),
                "longitude": openapi.Schema(type=openapi.TYPE_NUMBER, description="Longitude of the location"),
            },
            required=["latitude", "longitude"]
        ),
        responses={
            200: openapi.Response("Address retrieved successfully", openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "statusCode": openapi.Schema(type=openapi.TYPE_INTEGER, example=200),
                    "status": openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
                    "address": openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "address1": openapi.Schema(type=openapi.TYPE_STRING, example="123 Main St, New York, NY, USA"),
                            "address2": openapi.Schema(type=openapi.TYPE_STRING, example=""),
                            "postalCode": openapi.Schema(type=openapi.TYPE_STRING, example="10001"),
                            "latitude": openapi.Schema(type=openapi.TYPE_NUMBER, example=40.7128),
                            "longitude": openapi.Schema(type=openapi.TYPE_NUMBER, example=-74.0060),
                            "country": openapi.Schema(type=openapi.TYPE_STRING, example="United States"),
                            "city": openapi.Schema(type=openapi.TYPE_STRING, example="New York"),
                            "countryCode": openapi.Schema(type=openapi.TYPE_STRING, example="US"),
                            "countryShortName": openapi.Schema(type=openapi.TYPE_STRING, example="US"),
                            "dialCode": openapi.Schema(type=openapi.TYPE_STRING, example="+1"),
                            "flag": openapi.Schema(type=openapi.TYPE_STRING, example="https://flagcdn.com/w320/us.png"),
                            "formattedAddress": openapi.Schema(type=openapi.TYPE_STRING, example="123 Main St, New York, NY, USA"),
                        }
                    )
                }
            )),
            400: openapi.Response("Bad request - missing latitude or longitude"),
            404: openapi.Response("No address found for the given coordinates"),
            500: openapi.Response("Internal server error"),
        }
    )
    def post(self, request):
        try:
            latitude = request.data.get("latitude")
            longitude = request.data.get("longitude")

            if not latitude or not longitude:
                return Response({
                    "message": "Latitude and longitude are required.",
                    "statusCode": 400,
                    "status": False
                }, status=200)
            GOOGLE_MAPS_API_KEY = settings.GOOGLE_MAPS_API_KEY
            geocoding_url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={latitude},{longitude}&key={GOOGLE_MAPS_API_KEY}"

            response = requests.get(geocoding_url)
            data = response.json()

            if data.get("status") == "OK" and data.get("results"):
                results = data["results"]
                address = {
                    "address1": results[0].get("formatted_address", ""),
                    "address2": results[1].get("formatted_address", "") if len(results) > 1 else "",
                    "postalCode": "",
                    "latitude": latitude,
                    "longitude": longitude,
                    "country": "",
                    "city": "",
                    "countryCode": "",
                    "countryShortName": "",
                    "dialCode": "",
                    "flag": "",
                    "formattedAddress": results[0].get("formatted_address", "")
                }
                for result in results:
                    for component in result.get("address_components", []):
                        types = component.get("types", [])

                        if "country" in types:
                            address["country"] = component["long_name"]
                            address["countryCode"] = component["short_name"]
                        if "locality" in types:
                            address["city"] = component["long_name"]
                        if "postal_code" in types:
                            address["postalCode"] = component["long_name"]
                        if "administrative_area_level_1" in types:
                            address["address1"] = results[0].get("formatted_address", "")
                        if "sublocality" in types:
                            address["address2"] = results[1].get("formatted_address", "") if len(results) > 1 else ""
                country_api_url = "https://restcountries.com/v3.1/all"
                country_info = requests.get(country_api_url).json()

                country_details = next((c for c in country_info if c.get("cca2") == address["countryCode"]), None)
                if country_details:
                    address["dialCode"] = country_details["idd"]["root"] + country_details["idd"]["suffixes"][0]
                    address["countryShortName"] = country_details["cca2"]
                    address["flag"] = f"https://flagcdn.com/w320/{address['countryCode'].lower()}.png"

                return Response({
                    "statusCode": 200,
                    "status": True,
                    "address": address
                }, status=200)

            else:
                return Response({
                    "error": "No address found for the given coordinates.",
                    "statusCode": 404,
                    "status": False
                }, status=404)

        except Exception as e:
           
            return Response({
                "error": "Internal server error.",
                "statusCode": 500,
                "status": False
            }, status=500)
class LogoutView(APIView):
    
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Logout the authenticated user by blacklisting the refresh token.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "refresh_token": openapi.Schema(type=openapi.TYPE_STRING, description="JWT Refresh Token"),
            },
            required=["refresh_token"]
        ),
        responses={
            200: openapi.Response("Logout successful", openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={"message": openapi.Schema(type=openapi.TYPE_STRING)}
            )),
            400: openapi.Response("Invalid token or missing refresh token"),
            401: openapi.Response("User not found or unauthorized"),
        }
    )
    def post(self, request):
        try:
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {
                        "statusCode": 401,
                        "status": False,
                        "message": "User not found or unauthorized"
                    },
                    status=status.HTTP_200_OK
                )

            refresh_token = request.data.get("refresh_token")

            if not refresh_token:
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": "Refresh token is required"
                    },
                    status=status.HTTP_200_OK
                )

            token = RefreshToken(refresh_token)
            token.blacklist()  # Blacklist the token

            return Response(
                {
                    "statusCode": 200,
                    "status": True,
                    "message": "Logout successful"
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "statusCode": 400,
                    "status": False,
                    "message": f"Invalid token: {str(e)}"
                },
                status=status.HTTP_200_OK
            )
class CheckEmailAvailabilityView(APIView):
    def post(self, request):
        try:
            email = request.data.get("email", None)
            if not email:
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": "Email parameter is required"
                    },
                    status=status.HTTP_200_OK
                )
            if Users.objects.filter(email=email).exists():
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": "Already taken"
                    },
                    status=status.HTTP_200_OK
                )

            return Response(
                {
                    "statusCode": 200,
                    "status": True,
                    "message": "Email available"
                },
                status=status.HTTP_200_OK
            )

        except ValidationError as e:
            return Response(
                {
                    "statusCode": 400,
                    "status": False,
                    "message": str(e)
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "statusCode": 500,
                    "status": False,
                    "message": "An unexpected error occurred",
                    "details": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class CheckUsernameAvailabilityView(APIView):
    def post(self, request):
        try:
            username = request.data.get("username", None)
            if not username:
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": "Username parameter is required"
                    },
                    status=status.HTTP_200_OK
                )
            if Users.objects.filter(username=username).exists():
                return Response(
                    {
                        "statusCode": 400,
                        "status": False,
                        "message": "Already taken"
                    },
                    status=status.HTTP_200_OK
                )

            return Response(
                {
                    "statusCode": 200,
                    "status": True,
                    "message": "Username available"
                },
                status=status.HTTP_200_OK
            )

        except ValidationError as e:
            return Response(
                {
                    "statusCode": 400,
                    "status": False,
                    "message": str(e)
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "statusCode": 500,
                    "status": False,
                    "message": "An unexpected error occurred",
                    "details": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
from datetime import datetime, timedelta

from django.utils import timezone


class HomeTabView(APIView):
    def get(self, request):
        facility_id = request.query_params.get('facilityName')
        user_lat = request.query_params.get('latitude')
        user_lon = request.query_params.get('longitude')
        distance_limit = request.query_params.get('distance_km')  # Optional
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        min_rating = request.query_params.get('min_rating')
        clickandcollect = request.query_params.get('clickandcollect')
        onsite = request.query_params.get('onsite')
        is_open = request.query_params.get('is_open')
        is_open_soon = request.query_params.get('is_open_or_soon')
        def parse_float(value):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        user_lat = parse_float(user_lat)
        user_lon = parse_float(user_lon)
        distance_limit = parse_float(distance_limit)
        min_price = parse_float(min_price)
        max_price = parse_float(max_price)
        min_rating = parse_float(min_rating)

        def to_bool(val):
            return val.lower() == 'true' if val else None

        clickandcollect = to_bool(clickandcollect)
        onsite = to_bool(onsite)
        is_open = to_bool(is_open)
        is_open_soon = to_bool(is_open_soon)

        store_reels = StoreReel.objects.all().order_by('-created_at')
        if not store_reels.exists():
            return Response({"statusCode": 400,
            "status": True, "message": "No store reels found"}, status=status.HTTP_200_OK)

        company_ids = store_reels.values_list('company_id', flat=True).distinct()
        companies = CompanyDetails.objects.filter(id__in=company_ids).prefetch_related('facilities')

        if min_price is not None:
            companies = companies.filter(minimum_order_amount__gte=min_price)
        if max_price is not None:
            companies = companies.filter(minimum_order_amount__lte=max_price)
        if facility_id:
            try:
                facility_ids = [int(fid.strip()) for fid in facility_id.split(',')]
                companies = companies.filter(facilities__id__in=facility_ids)
            except ValueError:
                pass
        if min_rating is not None:
            companies = companies.filter(average_rating__gte=min_rating)
        if clickandcollect is not None:
            companies = companies.filter(clickcollect=clickandcollect)
        if onsite is not None:
            companies = companies.filter(onsite=onsite)
        company_distance_map = {}
        filtered_company_ids = []

        if user_lat is not None and user_lon is not None:
            for company in companies:
                addr = company.manual_address
                if addr and addr.lat and addr.lang:
                    try:
                        dist = haversine_distance(user_lat, user_lon, float(addr.lat), float(addr.lang))
                        company_distance_map[company.id] = round(dist, 2)

                        if distance_limit is None or dist <= distance_limit:
                            filtered_company_ids.append(company.id)
                    except Exception:
                        continue
            companies = companies.filter(id__in=filtered_company_ids)
        def get_opening_status(opening_hours):
            if not opening_hours:
                return "closed"

            now = timezone.localtime(timezone.now())
            current_time = now.time()
            today = now.strftime('%A').lower()

            if today not in opening_hours:
                return "closed"

            today_hours = opening_hours[today]

            try:
                start_time = datetime.strptime(today_hours['start_time'], '%H:%M').time()
                end_time = datetime.strptime(today_hours['end_time'], '%H:%M').time()
            except (KeyError, ValueError):
                return "closed"

            start_datetime = datetime.combine(now.date(), start_time).replace(tzinfo=now.tzinfo)
            end_datetime = datetime.combine(now.date(), end_time).replace(tzinfo=now.tzinfo)

            if now < start_datetime:
                if (start_datetime - now) <= timedelta(hours=1):
                    return "opening soon"
                return "closed"
            elif start_datetime <= now <= end_datetime:
                if (end_datetime - now) <= timedelta(hours=1):
                    return "closing soon"
                return "open"
            else:
                return "closed"        
        response_data = []

        if request.user.is_authenticated:
            cart_products = Cart.objects.filter(user=request.user).select_related('product__company')
            cart_counts = Counter(cart_products.values_list('product__company_id', flat=True))
        else:
            cart_counts = {}
        def safe_url(field):
            return field.url if field and hasattr(field, 'url') else None

        response_data = []
        for company in companies:
            
            company_reels = store_reels.filter(company_id=company.id,isActive=True)
            if not company_reels.exists():
                continue

            opening_status = get_opening_status(company.opening_hours)
            if is_open is True and opening_status != "open":
                continue
            if is_open_soon is True and opening_status != "opening soon":
                continue 
            if company_reels.exists(): 
                for reel in company_reels:
                    thumbnail_url = None
                    if reel.thumbnail:
                        if str(reel.thumbnail).startswith("http"):
                            thumbnail_url = str(reel.thumbnail)
                        else:
                            try:
                                if hasattr(reel.thumbnail, 'url'):
                                    thumbnail_url = request.build_absolute_uri(reel.thumbnail.url)
                                else:
                                    thumbnail_url = request.build_absolute_uri(str(reel.thumbnail))
                            except Exception:
                                thumbnail_url = None  
                    response_data.append({
                        "company_data": {
                            "id": company.id,
                            "companyName": company.companyName,
                            "userName": company.userName,
                            "managerFullName": company.managerFullName,
                            "email": company.email,
                            "phoneNumber": company.phoneNumber,
                            "sectorofActivity": company.sectorofActivity,
                            "created_at": company.created_at,
                            "updated_at": company.updated_at,
                            "isActive": company.isActive,
                            "average_rating": company.average_rating,
                            "minimum_order_amount": company.minimum_order_amount,
                            "total_ratings": company.total_ratings,
                            "distance": haversine_distance(user_lat, user_lon, company.manual_address.lat, company.manual_address.lang)
                            if company.manual_address and company.manual_address.lat and company.manual_address.lang else None,
                            "cart_count": cart_counts.get(company.id, 0),
                            "opening_status": opening_status if opening_status else "Closed",   
                            "manual_address": {
                           "address1": (
                                        None if not company.manual_address or not company.manual_address.address1
                                        else (
                                            company.manual_address.address1
                                            if len(company.manual_address.address1) <= 50
                                            else company.manual_address.address1[:50] + "..."
                                        )
                                    ),
                            "address2": company.manual_address.address2 if company.manual_address else None,
                            "postalCode": company.manual_address.postalCode if company.manual_address else None,
                            "city": company.manual_address.city if company.manual_address else None,
                            "state": company.manual_address.state if company.manual_address else None,
                            "country": company.manual_address.country if company.manual_address else None,
                            "latitude": company.manual_address.lat if company.manual_address else None,
                            "longitude": company.manual_address.lang if company.manual_address else None,
                           
                        } if company.manual_address else None,
                            "facilities": [
                            {
                                "id": facility.id,
                                "name": facility.name,
                                "icon": safe_url(facility.icon),
                            }
                            for facility in company.facilities.all()
                            
                ],
                    "store_reels": 
                            {
                            "id": reel.id,
                            "title": reel.title,
                            "companyName": company.companyName,
                            "profilePhoto":safe_url(company.profilePhoto),
                            "category": reel.category.name if reel.category else None,
                            "categoryID": reel.category.id if reel.category else None,
                            "categorySlug": reel.category.slug if reel.category else None,
                            "subcategoryID": reel.subcategory.id if reel.subcategory else None,
                            "subcategorySlug": reel.subcategory.slug if reel.subcategory else None,
                            "video": safe_url(reel.video),
                            "thumbnail": thumbnail_url,
                            "m3u8_url": reel.m3u8_url if reel.m3u8_url else None,
                            "likes": reel.likes,
                            "shares": reel.shares,
                            "comments": reel.comments,
                            "views": reel.views,
                        }
                        
                        }
                        
                        
                    })
        page = int(request.query_params.get('page', 1))
        paginator = Paginator(response_data, 6)
        try:
            paginated_data = paginator.page(page)
        except EmptyPage:
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "No more data available.",
                "data": []
            })
       

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Data and reels fetched successfully",
            "data": paginated_data.object_list,
            "pagination": {
                "current_page": page,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "has_next": paginated_data.has_next(),
                "has_previous": paginated_data.has_previous(),
            }
            
        }, status=status.HTTP_200_OK)
class CompanyMediaView(APIView):

    def get(self, request, company_id):
        try:
            company = get_object_or_404(CompanyDetails, id=company_id)

            images = StoreImage.objects.filter(company_id=company.id)
            reels = StoreReel.objects.filter(company_id=company.id, is_deleted=False)

            image_serializer = StoreImagessSerializer(images, many=True)
            reel_serializer = StoreReelSerializer(reels, many=True)

            combined_media = [
                {**image, "media_type": "image"} for image in image_serializer.data
            ] + [
                {**reel, "media_type": "reel"} for reel in reel_serializer.data
            ]

            return Response({
                "status": True,
                "statusCode": 200,
                "company_id": company.id,
                "company_name": company.companyName,
                "media": combined_media 
            }, status=status.HTTP_200_OK)

        except CompanyDetails.DoesNotExist:
            return Response({
                "status": False,
                "statusCode": 404,
                "message": "Company not found."
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": False,
                "statusCode": 500,
                "message": "An error occurred while fetching company media.",
                "error": str(e) 
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class CompanyEventView(APIView): 

    def get(self, request, company_id):
        try:
            company = get_object_or_404(CompanyDetails, id=company_id)

            store_events = StoreEvent.objects.filter(company_id=company)

            event_serializer = StoreEventSerializer(store_events, many=True)
       
            return Response({
                "status": True,
                "statusCode": 200,
                "company_id": company.id,
                "company_name": company.companyName,
                "store_events": event_serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": False,
                "statusCode": 500,
                "message": "An error occurred while fetching store events.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        





class CompanyProductsAndServicesViewsnewsss(APIView):
    def get(self, request, company_id):
        try:
            company = get_object_or_404(CompanyDetails, id=company_id)
            selected_type = request.query_params.get("type")  # product, services, ticket
            search_query = request.query_params.get("search", "").strip().lower()
            category_slug = request.query_params.get("category_slug")
            subcategory_slug = request.query_params.get("subcategory_slug")
            category_service_map = {
                1: {"Onsite", "Click and Collect", "Delivery"},
                2: {"Results"},
                3: {"Onsite", "Home Visit"},
                4: {"Onsite", "Home Visit"},
                5: {"Results"},
                6: {"Results"},
                7: {"Results"},
                8: {"Click and Collect", "Delivery"},
            }

            company_category_ids = set(company.categories.values_list("id", flat=True))
            allowed_service_types = set()
            for cid in company_category_ids:
                allowed_service_types.update(category_service_map.get(cid, set()))
            category_filter = Q()
            if category_slug:
                category = get_object_or_404(Category, slug=category_slug)
                category_filter &= Q(categoryId=category.id)
            if subcategory_slug:
                subcategory = get_object_or_404(Subcategory, slug=subcategory_slug)
                category_filter &= Q(subCategoryId=subcategory.id)

            all_products = Product.objects.filter(
                company=company,
                categoryId__in=company_category_ids
            ).filter(category_filter)

            if selected_type in ['product', 'services', 'ticket']:
                all_products = all_products.filter(productType=selected_type)

            if search_query:
                all_products = all_products.filter(productname__icontains=search_query)

            def get_product_types(product):
                types = []
                if product.onsite:
                    types.append("Onsite")
                if product.onhome:
                    types.append("Home Visit")
                if product.clickandCollect:
                    types.append("Click and Collect")
                if product.onDelivery:
                    types.append("Delivery")
                if not types:
                    types.append("Results")
                return types
            user_cart = {}
            current_product_count = 0
            if request.user and request.user.is_authenticated:
                try:
                    user_cart = {
                        item.product.id: item.quantity for item in Cart.objects.filter(user=request.user)
                    }
                    current_product_count = sum(user_cart.values())
                except Exception as cart_error:
                    logger.error(f"Cart fetch failed: {cart_error}")

            label_map = {
                "Click and Collect": "Click & Collect",
                "Delivery": "OnDelivery",
                "Home Visit": "OnHome",
                "Onsite": "OnSite",
                "Results": "Other"
            }

            products_data = []
            for service_type in sorted(allowed_service_types):
                filtered_products = [
                    product for product in all_products
                    if service_type in get_product_types(product)
                ]

                serialized = []
                for product in filtered_products:
                    product_data = ProductdetailsSerializer(product).data
                    product_data["currentQuantity"] = user_cart.get(product.id, 0)
                    serialized.append(product_data)

                products_data.append({
                    "products_type": service_type,
                    "label": label_map.get(service_type, service_type.capitalize()),
                    "products": [{"items": serialized}] if serialized else []
                })

            return Response({
                "statusCode": 200,
                "status": True,
                "company_id": company.id,
                "company_name": company.companyName,
                "message": "Filtered content fetched successfully.",
                "currentProduct": current_product_count,
                "data": {
                    "productStatus": products_data
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Unhandled error in CompanyProductsAndServicesViews")
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred while fetching products and services.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class CompanyProductsAndServicesViews(APIView):
    def get(self, request, company_id):
        logger.info(f"User: {request.user}")
        logger.info(f"Is Authenticated: {request.user.is_authenticated}")

        try:
            company = get_object_or_404(CompanyDetails, id=company_id)
            selected_type = request.query_params.get("type")  # product, services, ticket
            search_query = request.query_params.get("search", "").strip().lower()
            category_service_map = {
                1: {"Onsite", "Click and Collect", "Delivery"},
                2: {"Results"},
                3: {"Onsite", "Home Visit"},
                4: {"Onsite", "Home Visit"},
                5: {"Results"},
                6: {"Results"},
                7: {"Results"},
                8: {"Click and Collect", "Delivery"},
            }

            company_category_ids = set(company.categories.values_list("id", flat=True))
            allowed_service_types = set()
            for cid in company_category_ids:
                allowed_service_types.update(category_service_map.get(cid, set()))

            all_products = Product.objects.filter(
                company=company,
                categoryId__in=company_category_ids
            )

            if selected_type in ['product', 'services', 'ticket']:
                all_products = all_products.filter(productType=selected_type)

            if search_query:
                all_products = all_products.filter(productname__icontains=search_query)

            def get_product_types(product):
                types = []
                if product.onsite:
                    types.append("Onsite")
                if product.onhome:
                    types.append("Home Visit")
                if product.clickandCollect:
                    types.append("Click and Collect")
                if product.onDelivery:
                    types.append("Delivery")
                if not types:
                    types.append("Results")
                return types
            user_cart = {}
            current_product_count = 0
            if request.user and request.user.is_authenticated:
                logger.info(f"Authenticated user: {request.user}")
                try:
                    user_cart = {
                        item.product.id: item.quantity for item in Cart.objects.filter(user=request.user)
                    }
                    current_product_count = sum(user_cart.values())
                except Exception as cart_error:
                    logger.error(f"Cart fetch failed: {cart_error}")
            else:
                logger.warning("User is not authenticated. Skipping cart count.")

            label_map = {
                "Click and Collect": "Click & Collect",
                "Delivery": "OnDelivery",
                "Home Visit": "OnHome",
                "Onsite": "OnSite",
                "Results": "Other"
            }

            products_data = []
            for service_type in sorted(allowed_service_types):
                filtered_products = [
                    product for product in all_products
                    if service_type in get_product_types(product)
                ]

                serialized = []
                for product in filtered_products:
                    product_data = ProductdetailsSerializer(product).data
                    product_data["currentQuantity"] = user_cart.get(product.id, 0)
                    serialized.append(product_data)

                products_data.append({
                    "products_type": service_type,
                    "label": label_map.get(service_type, service_type.capitalize()),
                    "products": [{"items": serialized}] if serialized else []
                })

            return Response({
                "statusCode": 200,
                "status": True,
                "company_id": company.id,
                "company_name": company.companyName,
                "message": "Filtered content fetched successfully.",
                "currentProduct": current_product_count,
                "data": {
                    "productStatus": products_data
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Unhandled error in CompanyProductsAndServicesViews")
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred while fetching products and services.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from django.http import Http404


class CompanyLabelsByCategoryView(APIView):
    def get_service_labels(self, category_ids):
        merged_labels = {
            "Onsite": 1,
            "Click and Collect": 2,
            "Home": 3  
        }

        category_service_map = {
            1: {"Onsite", "Click and Collect", "Delivery"},
            2: {"Results"},
            3: {"Onsite", "Home Visit"},
            4: {"Onsite", "Home Visit"},
            5: {"Results"},
            6: {"Results"},
            7: {"Results"},
            8: {"Click and Collect", "Delivery"},
        }

        merged_group = {"Home Visit", "Delivery", "Results"}
        service_types = set()

        for cid in category_ids:
            service_types.update(category_service_map.get(cid, set()))

        simplified_labels = set()
        for s in service_types:
            if s in merged_group:
                simplified_labels.add("Home")
            else:
                simplified_labels.add(s)

        return sorted(
            [{"label": label, "key": merged_labels[label]} for label in simplified_labels],
            key=lambda x: x["key"]
        )

    def post(self, request, company_id, *args, **kwargs):
        try:
            company = get_object_or_404(CompanyDetails, id=company_id)
            category_slug_param = request.data.get("category_slug", None)

            if category_slug_param:
                slug_list = [slug.strip() for slug in category_slug_param.split(",") if slug.strip()]
                categories = Category.objects.filter(slug__in=slug_list)
            else:
                categories = company.categories.all()

            if not categories.exists():
                return Response({
                    "statusCode": 204,
                    "status": True,
                    "message": "No matching categories found.",
                    "data": []
                }, status=status.HTTP_200_OK)

            category_ids = set(categories.values_list("id", flat=True))
            labels = self.get_service_labels(category_ids)

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Labels fetched successfully.",
                "data": labels
            }, status=status.HTTP_200_OK)

        except Http404:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Company not found.",
                "data": []
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"Internal Server Error: {str(e)}",
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class CompanyItemsByServiceKeyView(APIView):
    def post(self, request, company_id):
        try:
            key = str(request.data.get("key", "")).strip()
            search_name = request.data.get("search", "").strip()
            category = request.data.get("categorySlug", "").strip()
            subcategory = request.data.get("subcategorySlug", "").strip()

            company = get_object_or_404(CompanyDetails, id=company_id)

            label_filter_map = {
                "1": {"field": "onsite", "title": "Onsite", "label": "OnSite"},
                "2": {"field": "clickandCollect", "title": "Click and Collect", "label": "Click and Collect"},
                "3": {"field": None, "title": "Home", "label": "Home"},
            }

            filter_info = label_filter_map.get(key, {"field": None, "title": "All", "label": "All"})
            user_cart = {}
            current_product_count = 0
            if request.user and request.user.is_authenticated:




                try:
                    user_cart = {
                        item.product.id: item.quantity
                        for item in Cart.objects.filter(user=request.user)
                    }
                    current_product_count = sum(user_cart.values())
                except Exception as cart_error:
                    logger.error(f"Cart fetch failed: {cart_error}")
            
            

            def serialize_items(queryset):

                def format_datetime(dt):
                    return dt.strftime("%d %b %Y") if dt else None
                def format_time(dt):
                    return dt.strftime("%I:%M %p").lstrip("0") if dt else None
                
            
                
                return [
                    {
                        **ProductdetailsSerializer(item).data,
                        "currentQuantity": user_cart.get(item.id, 0),
                        "category_slug": item.categoryId.slug if item.categoryId else None,
                        "subcategory_slug": item.subCategoryId.slug if item.subCategoryId else None,
                        "startAddress": AddressSerializer(item.startAddress).data if item.startAddress else None,
                        "endAddress": AddressSerializer(item.endAddress).data if item.endAddress else None,
                        "availabilityDateTime": format_datetime(item.availabilityDateTime),
                        "preparationDateTime": format_datetime(item.preparationDateTime),
                        "availabilityTime":format_time(item.availabilityDateTime),
                        "preparationTime":format_time(item.preparationDateTime),
                    
                      
                    }
                    for item in queryset
                ]

            def filter_items(model, field):
                items = model.objects.filter(company=company)

                if key == "3":
                    items = items.filter(Q(onhome=True) | Q(onDelivery=True))
                elif field:
                    items = items.filter(**{field: True})

                if search_name:
                    items = items.filter(productname__icontains=search_name)

                if category:
                    items = items.filter(categoryId__slug=category)

                if subcategory:
                    items = items.filter(subCategoryId__slug=subcategory)

                return items

            items = filter_items(Product, filter_info["field"])
            result_data = {
                "products_type": filter_info["title"],
                "label": filter_info["label"],
                "items": serialize_items(items)
            }

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Filtered data fetched successfully.",
                "data": result_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"Internal Server Error: {str(e)}",
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class StoreEventDetailViewNew(APIView):
    def get(self, request, event_id):
        try:
            event = get_object_or_404(StoreEvent, id=event_id)
            company = event.company  # Assuming a ForeignKey: event.company

            event_serializer = StoreEventSerializer(event)

            return Response({
                "status": True,
                "statusCode": 200,
                "company_id": company.id,
                "company_name": company.companyName,
                "event_details": event_serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": False,
                "statusCode": 400,
                "message": str(e),
    
            }, status=status.HTTP_200_OK)





class CompanyProductsAndServicesView(APIView):

    def get(self, request, company_id):
        try:
            company = get_object_or_404(CompanyDetails, id=company_id)

            search_query = request.query_params.get("search", "").strip().lower()

            products = Product.objects.filter(company=company)
            services = Service.objects.filter(company=company, is_deleted=False)

            if search_query:
                products = products.filter(productname__icontains=search_query)
                services = services.filter(productname__icontains=search_query)

            product_serializer = ProductdetailsSerializer(products, many=True)
            service_serializer = ServiceSerializer(services, many=True)
            combined_media = [
                {**product, "type": "product"} for product in product_serializer.data
            ] + [
                {**service, "type": "service"} for service in service_serializer.data
            ]
            for item in combined_media:
                for key, value in item.items():
                    if isinstance(value, list) and not value:
                        item[key] = None

            return Response({
                "status": True,
                "statusCode": 200,
                "company_id": company.id,
                "company_name": company.companyName,
                "products": combined_media
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": False,
                "statusCode": 500,
                "message": "An error occurred while fetching products and services.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class CompanyFeedbackAPIView(generics.ListAPIView):
    serializer_class = CompanyReviewSerializer

    def get(self, request, company_id, *args, **kwargs):
        try:
            company = CompanyDetails.objects.get(id=company_id)
            
            reviews = CompanyReview.objects.filter(company=company)
            
            average_rating = float(reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0)
            average_rating = round(average_rating, 2)
            
            rating_counts = reviews.values('rating').annotate(count=Count('rating')).order_by('rating')
            
            star_counts = {i: 0 for i in range(1, 6)}
            for rating_count in rating_counts:
                star_counts[int(rating_count['rating'])] = int(rating_count['count'])

            total_rating_count = reviews.count()
            
            star_percentages = {
                star: round((count / total_rating_count) * 100, 2) if total_rating_count > 0 else 0.0
                for star, count in star_counts.items()
            }
            
            overall_rating_data = [
                {
                    "id": star,
                    "label": f"{star} Star",
                    "rating_percentage": star_percentages[star],
                }
                for star in range(5, 0, -1)  
            ]
            
            serialized_reviews = []
            for review in reviews:
                elapsed_time = timesince(review.created_at, now()) 
                serialized_review = self.get_serializer(review).data
                serialized_review["time_ago"] = elapsed_time
                serialized_reviews.append(serialized_review)
            
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Company feedback retrieved successfully",
                "data": {
                    "average_rating": average_rating,
                    "rating_counts": overall_rating_data,
                    "total_rating_count": total_rating_count,
                    "reviews": serialized_reviews,
                }
            }, status=status.HTTP_200_OK)
        
        except CompanyDetails.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Company not found"
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def haversine_distances_calculator( lat1, lon1, lat2, lon2):
    
        R = 6371  
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c 


class CompanyDetailsAPIView(generics.RetrieveAPIView):
    serializer_class = CompanyDetailsSerializer

  

    def haversine_distance(self, lat1, lon1, lat2, lon2):
    
        R = 6371  
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c  
    def convert_to_12hr_format(self, time_obj):
        try:
            if hasattr(time_obj, 'strftime'):
                return time_obj.strftime("%I:%M %p")  # Format time in 12-hour format with AM/PM
            else:
                raise ValueError("Expected a datetime.time object, but got a different type.")
        except Exception as e:
            raise ValueError(f"Error converting time: {str(e)}")
    def get(self, request, company_id, *args, **kwargs):
        try:
            company = get_object_or_404(CompanyDetails, id=company_id)
            company_data = CompanyDetailsSerializer(company).data
            if not company.coverPhotos:
                company_data['coverPhotos'] = default_image_url("company_profile")
            else:
                company_data['coverPhotos'] = request.build_absolute_uri(company.coverPhotos)

            company.total_visits = F('total_visits') + 1
            company.save(update_fields=['total_visits'])
            company.refresh_from_db()


            if company.end_time:
                company_data['end_time'] = self.convert_to_12hr_format(company.end_time)
            
            
            reviews = CompanyReview.objects.filter(company=company).order_by('-created_at')
            review_data = CompanyReviewSerializer(reviews, many=True).data

            company_ct = ContentType.objects.get_for_model(CompanyDetails)

            # Total followers for the company
            total_followers = Friendship.objects.filter(
                receiver_content_type=company_ct,
                receiver_object_id=company.id,
                relationship_type="follow",
                status="follow"
            ).count()
            is_following = False
            if request.user.is_authenticated:
                user_ct = ContentType.objects.get_for_model(request.user.__class__)
                is_following = Friendship.objects.filter(
                    sender_content_type=user_ct,
                    sender_object_id=request.user.id,
                    receiver_content_type=company_ct,
                    receiver_object_id=company.id,
                    relationship_type="follow",
                    status="follow"
                ).exists()

            user_lat = request.query_params.get('lat')
            user_lon = request.query_params.get('lon')
           
            if not user_lat or not user_lon:
                if request.user.is_authenticated:
                    if request.user.manualAddress:
                        user_lat = request.user.manualAddress.lat
                        user_lon = request.user.manualAddress.lang
                    elif request.user.automatic_address:
                        user_lat = request.user.automatic_address.lat
                        user_lon = request.user.automatic_address.lang


                

            company_lat = None
            company_lon = None

            if company.automatic_address:
                company_lat = company.automatic_address.lat
                company_lon = company.automatic_address.lang
            elif company.manual_address:
                company_lat = company.manual_address.lat
                company_lon = company.manual_address.lang
            try:
                company_lat = float(company_lat.strip()) if company_lat else None
                company_lon = float(company_lon.strip()) if company_lon else None
                user_lat = float(user_lat.strip()) if user_lat else None
                user_lon = float(user_lon.strip()) if user_lon else None
    
            except (ValueError, AttributeError) as e:
                company_lat, company_lon, user_lat, user_lon = None, None, None, None
            distance_km = None
            if user_lat and user_lon and company_lat and company_lon:
                distance_km = self.haversine_distance(user_lat, user_lon, company_lat, company_lon)
            company_data['total_followers'] = total_followers
            company_data['is_following'] = is_following
            company_data['feedback'] = review_data
            company_data['company_lat'] = company_lat
            company_data['company_lon'] = company_lon
            company_data['distance_km'] = round(distance_km, 2) if distance_km else None  # Round to 2 decimal places
            professional = ProfessionalUser.objects.filter(company=company).first()
            company_data['professional_id'] = professional.id if professional else None
            
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Company details retrieved successfully",
                "data": company_data 
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetCompanyAboutsByUserView(generics.RetrieveAPIView):
    serializer_class = CompanyDetailsSerializer

    def haversine_distance(self, lat1, lon1, lat2, lon2):
       
        R = 6371  
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon1 - lon2

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c  

    def convert_to_12hr_format(self, time_obj):
        try:
            if hasattr(time_obj, 'strftime'):
                return time_obj.strftime("%I:%M %p")  
            else:
                raise ValueError("Expected a datetime.time object, but got a different type.")
        except Exception as e:
            raise ValueError(f"Error converting time: {str(e)}")

    def format_opening_hours(self, opening_hours):
        day_mapping = {
            "monday": "Mon",
            "tuesday": "Tues",
            "wednesday": "Wed",
            "thursday": "Thur",
            "friday": "Fri",
            "saturday": "Sat",
            "sunday": "Sun"
        }

        formatted_hours = []

        for day, hours in opening_hours.items():
            start_time = hours.get('start_time')
            end_time = hours.get('end_time')

            if start_time and end_time:
                if hasattr(start_time, 'strftime') and hasattr(end_time, 'strftime'):
                    formatted_hours.append({
                        "day": day_mapping.get(day.lower(), day.capitalize()),
                        "hours": f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
                    })
                else:
                    formatted_hours.append({
                        "day": day_mapping.get(day.lower(), day.capitalize()),
                        "hours": f"{start_time} - {end_time}"  # fallback if strings
                    })
        day_order = ["Mon", "Tues", "Wed", "Thur", "Fri", "Sat", "Sun"]
        formatted_hours.sort(key=lambda x: day_order.index(x["day"]) if x["day"] in day_order else 7)

        return formatted_hours

    def get(self, request, company_id, *args, **kwargs):
        try:
            user_lat = request.query_params.get('lat')
            user_lon = request.query_params.get('lon')
            company = get_object_or_404(CompanyDetails, id=company_id)
            company_data = CompanyDetailsSerializer(company).data

          
            if company.end_time:
                company_data['end_time'] = self.convert_to_12hr_format(company.end_time)

     
            reviews = CompanyReview.objects.filter(company=company).order_by('-created_at')
            review_data = CompanyReviewSerializer(reviews, many=True).data

            total_followers = Follow.objects.filter(company=company).count()
            is_following = False
            company_lat = None
            company_lon = None
            if company.automatic_address:
                company_lat = company.automatic_address.lat
                company_lon = company.automatic_address.lang
            elif company.manual_address:
                company_lat = company.manual_address.lat
                company_lon = company.manual_address.lang
            try:
                company_lat = float(company_lat.strip()) if company_lat else None
                company_lon = float(company_lon.strip()) if company_lon else None
                user_lat = float(user_lat.strip()) if user_lat else None
                user_lon = float(user_lon.strip()) if user_lon else None
            except (ValueError, AttributeError) as e:
                company_lat, company_lon, user_lat, user_lon = None, None, None, None
            distance_km = None
            if user_lat and user_lon and company_lat and company_lon:
                distance_km = self.haversine_distance(user_lat, user_lon, company_lat, company_lon)
            opening_hours = company_data.get("opening_hours")
            if opening_hours:
                company_data["opening_hours"] = self.format_opening_hours(opening_hours)
            else:
                company_data["opening_hours"] = None
            company_data['total_followers'] = total_followers
            company_data['is_following'] = is_following
            company_data['feedback'] = review_data
            company_data['company_lat'] = company_lat
            company_data['company_lon'] = company_lon
            company_data['distance_km'] = round(distance_km, 2) if distance_km else None  

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Company details retrieved successfully",
                "data": company_data 
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ToggleFollowCompanyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, company_id):
        try:
            company = CompanyDetails.objects.get(id=company_id)
        except CompanyDetails.DoesNotExist:
            return Response({"message": "Company not found!"}, status=status.HTTP_200_OK)

        user = request.user

        user_ct = ContentType.objects.get_for_model(user)
        company_ct = ContentType.objects.get_for_model(company)
        try:
            friendship = Friendship.objects.get(
                sender_content_type=user_ct,
                sender_object_id=user.id,
                receiver_content_type=company_ct,
                receiver_object_id=company.id,
                relationship_type="follow"
            )
            friendship.delete()
            followed = False
            message = "Unfollowed successfully!"
        except Friendship.DoesNotExist:
            Friendship.objects.create(
                sender_content_type=user_ct,
                sender_object_id=user.id,
                receiver_content_type=company_ct,
                receiver_object_id=company.id,
                relationship_type="follow",
                status="follow"
            )
            followed = True
            message = "Followed successfully!"

        user_data = UserSerializer(user).data
        company_data = CompanyDetailsSerializer(company).data

        return Response({
            "statusCode": 200,
            "status": True,
            "message": message,
            "followed": followed,
            "user": user_data,
            "company": company_data
        }, status=status.HTTP_200_OK)
class AddNewAddressAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data

        required_fields = ['first_name', 'last_name', 'phone_code', 'phone_number',
                           'house_building', 'road_area_colony', 'pincode',
                           'city', 'state', 'address_type','lat','lang']
        
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return Response({
                'message': f'Missing required fields: {", ".join(missing_fields)}',
                'statusCode': 400,
                'status': False
            })

        try:
            address = userAddress.objects.create(
                user=user,
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                phone_code=data.get('phone_code'),
                phone_number=data.get('phone_number'),
                house_building=data.get('house_building'),
                road_area_colony=data.get('road_area_colony'),
                pincode=data.get('pincode'),
                city=data.get('city'),
                state=data.get('state'),
                lat=data.get('lat'),
                lang=data.get('lang'),
                address_type=data.get('address_type')
            )

            return Response({
                'message': 'Address added successfully',
                'statusCode': 200,
                'status': True,
                'address': UserAddressSerializer(address).data
            })

        except Exception as e:
            return Response({
                'message': f'Error: {str(e)}',
                'statusCode': 500,
                'status': False
            })


class GetUserAddressesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        addresses = userAddress.objects.filter(user=user)
        serializer = UserAddressSerializer(addresses, many=True)
        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Addresses retrieved successfully.',
            'data': serializer.data
        })


    
class EditUserAddressAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, address_id):
        user = request.user
        data = request.data

        try:
            address = userAddress.objects.get(id=address_id, user=user)
            address.first_name = data.get('first_name', address.first_name)
            address.last_name = data.get('last_name', address.last_name)
            address.phone_code = data.get('phone_code', address.phone_code)
            address.phone_number = data.get('phone_number', address.phone_number)
            address.house_building = data.get('house_building', address.house_building)
            address.road_area_colony = data.get('road_area_colony', address.road_area_colony)
            address.pincode = data.get('pincode', address.pincode)
            address.city = data.get('city', address.city)
            address.state = data.get('state', address.state)
            address.lat=data.get('lat',address.lat),
            address.lang=data.get('lang',address.lang),
            address.address_type = data.get('address_type', address.address_type)

            address.save()

            return Response({
                'message': 'Address updated successfully',
                'statusCode': 200,
                'status': True,
                'address': UserAddressSerializer(address).data
            })

        except userAddress.DoesNotExist:
            return Response({
                'message': 'Address not found or does not belong to the authenticated user.',
                'statusCode': 404,
                'status': False
            })

        except Exception as e:
            return Response({
                'message': f'Error: {str(e)}',
                'statusCode': 500,
                'status': False
            })

class DeleteUserAddressAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, address_id):
        user = request.user

        try:
            address = userAddress.objects.get(id=address_id, user=user)
            address.delete()

            return Response({
                'message': 'Address deleted successfully',
                'statusCode': 200,
                'status': True
            })

        except userAddress.DoesNotExist:
            return Response({
                'message': 'Address not found or does not belong to the authenticated user.',
                'statusCode': 404,
                'status': False
            })

        except Exception as e:
            return Response({
                'message': f'Error: {str(e)}',
                'statusCode': 500,
                'status': False
            })
class ReelFolderListAPIView(APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request, folder_id=None):
        try:
            if folder_id:
                folder = ReelFolder.objects.get(id=folder_id, user=request.user)
                folder_data = {
                    "id": folder.id,
                    "name": folder.name,
                    "path": f"http:/{settings.MEDIA_URL}uploads/{folder.name}/"
                }
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Folders retrieved successfully",
                    "folder": folder_data
                }, status=status.HTTP_200_OK)
            else:
                folders = ReelFolder.objects.filter(user=request.user)
                folder_list = [
                    {
                        "id": folder.id,
                        "name": folder.name,
                        "path": f"http:/{settings.MEDIA_URL}uploads/{folder.name}/"
                    }
                    for folder in folders
                ]
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Folders retrieved successfully",
                    "folders": folder_list
                }, status=status.HTTP_200_OK)

        except ReelFolder.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Folder not found"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class ReelFolderRetrieveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, folder_id):
        try:
            folder = ReelFolder.objects.get(id=folder_id, user=request.user)
            folder_key = f"uploads/{folder.name}/"
            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME,
            )

            try:
                result = s3.list_objects_v2(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Prefix=folder_key
                )
                if "Contents" not in result:
                    return Response({
                        "statusCode": 404,
                        "status": False,
                        "message": "Folder not found or empty"
                    }, status=status.HTTP_200_OK)
                folder_contents = [
                    f"http://{settings.AWS_S3_CUSTOM_DOMAIN}/{item['Key']}"
                    for item in result.get("Contents", [])
                ]

                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Folder retrieved successfully",
                    "folder": {
                        "id": folder.id,
                        "name": folder.name,
                        "path": f"http://{settings.AWS_S3_CUSTOM_DOMAIN}/{folder_key}",
                        "contents": folder_contents
                    }
                }, status=status.HTTP_200_OK)

            except (NoCredentialsError, ClientError) as e:
                return Response({
                    "statusCode": 500,
                    "status": False,
                    "message": f"Error accessing S3: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except ReelFolder.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Folder not found"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class ReelFolderDeleteView(generics.DestroyAPIView):
    queryset = ReelFolder.objects.all()
    serializer_class = ReelFolderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        folder = super().get_object()
        if folder.user != self.request.user:
            raise PermissionDenied("You do not have permission to delete this folder.")
        return folder

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            "statusCode":200,
            "status": True,
            "message": "Reel folder deleted successfully."
        }, status=status.HTTP_200_OK)



class ReelFolderUpdateView(generics.UpdateAPIView):
    queryset = ReelFolder.objects.all()
    serializer_class = ReelFolderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        folder = super().get_object()
        if folder.user != self.request.user:
            raise PermissionDenied("You do not have permission to update this folder.")
        return folder

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new_name = request.data.get("name")

        if not new_name:
            return Response({
                "statusCode":400, 
                "success": False,
                "message": "Folder name is required."
            }, status=status.HTTP_200_OK)
        if ReelFolder.objects.filter(user=request.user, name=new_name).exclude(pk=instance.pk).exists():
            return Response({
                "statusCode":400,
                "status": False,
                "message": "You already have a folder with this name."
            }, status=status.HTTP_200_OK)

        instance.name = new_name
        instance.save()

        return Response({
            "statusCode":200,
            "status": True,
            "message": "Folder name updated successfully.",
            "data": {
                "id": instance.id,
                "name": instance.name
            }
        }, status=status.HTTP_200_OK)



class FilterCompanyReelsAPIView(APIView):
    def post(self, request):
        try:
            lat = request.data.get("lat")
            lang = request.data.get("lang")
            distance_limit = request.data.get("distance", 60)
            facility_ids_raw = request.data.get("facility_ids", "")  
          
            min_price = request.data.get("min_price")
            max_price = request.data.get("max_price")

           
            if not lat or not lang:
                return Response({"status": False, "message": "Latitude and longitude are required."}, status=status.HTTP_200_OK)

            
            lat = float(lat) if lat else None
            long = float(lang) if lang else None
            distance_limit = float(distance_limit) if distance_limit else 60

            nearby_restaurants = []
            
            s3_base_url = settings.AWS_S3_CUSTOM_DOMAIN if hasattr(settings, 'AWS_S3_CUSTOM_DOMAIN') else ""
            if not s3_base_url.startswith("https://"):
                s3_base_url = f"https://{s3_base_url}"
                
           
            companies = CompanyDetails.objects.filter(isActive=True)
            
            
            facility_ids = []

            if isinstance(facility_ids_raw, str):
                
                facility_ids_raw = facility_ids_raw.strip().strip('"').strip("'")
                facility_ids = [int(fid.strip()) for fid in facility_ids_raw.split(",") if fid.strip().isdigit()]
            elif isinstance(facility_ids_raw, list):
                facility_ids = [int(fid) for fid in facility_ids_raw if str(fid).isdigit()]

            
            for company in companies:
                
                address = company.manual_address or company.automatic_address
                if not (address and address.lat and address.lang):
                    continue
                
                if facility_ids:
                    company_facility_ids = list(company.facilities.values_list('id', flat=True))
                    if not any(facility_id in company_facility_ids for facility_id in facility_ids):
                        continue
                
                distance = None
                if lat is not None and long is not None:
                    distance = haversine_distance(lat, long, float(address.lat), float(address.lang))
                    if distance > distance_limit:
                        continue  
                products = Product.objects.filter(company=company)
                if min_price and max_price:
                    try:
                        min_price = float(min_price)
                        max_price = float(max_price)
                        has_valid_price = any(
                            min_price <= float(p.priceOnsite or 0) <= max_price or
                            min_price <= float(p.priceDelivery or 0) <= max_price
                            for p in products
                        )
                        if not has_valid_price:
                            continue
                    except:
                        pass
                    
                serialized_company = CompanyDetailsSerializer(company).data
                if distance is not None:
                    serialized_company['distance'] = round(distance, 2)
                serialized_company['distance'] = round(distance, 2)
                reels = StoreReel.objects.filter(company_id=company.id, isActive=False)
                serialized_company['reels'] = [{
                    "id": r.id, 
                    "title": r.title, 
                    "video_url": f"{s3_base_url}/{r.video}", 
                    "thumbnail_url": f"{s3_base_url}/{r.thumbnail}",
                    "category": r.category.name if r.category else None,
                    "categoryId": r.category.id if r.category else None,
                    "likes": r.likes,
                    "shares": r.shares,
                    "comments": r.comments,
                    "views": r.views
                } 
                for r in reels]

                nearby_restaurants.append(serialized_company)

           
            if not nearby_restaurants:
                return Response({"status": False, "message": "No restaurants found within 20 km."}, status=status.HTTP_200_OK)

            final_response = []
            for company in nearby_restaurants:
                for reel in company.get("reels", []):
                    final_response.append({
                        "company_data": {
                            "id": company["id"],
                            "companyName": company["companyName"],
                            "userName": company.get("userName"),
                            "managerFullName": company.get("managerFullName"),
                            "email": company.get("email"),
                            "phoneNumber": company.get("phoneNumber"),
                            "sectorofActivity": company.get("sectorofActivity"),
                            "profilePhoto": company.get("profilePhoto"),
                            "manual_address": company.get("manual_address"),
                            "facilities": company.get("facilities"),
                            "store_reels": reel
                            
                        }
            })
            
            return Response({
                "status": True,
                "message": "Restaurants retrieved successfully.",
                "data": final_response
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class GetSavedLikedReelsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user_folders = ReelFolder.objects.filter(user=request.user).order_by("-created_at")

            if not user_folders.exists():
                return Response({
                    "statusCode": 200,
                    "status": False,
                    "message": "No folders found.",
                    "data": []
                }, status=status.HTTP_200_OK)

            folders_data = []
            static_image_url = "https://markerplacemobileapp.s3.us-east-1.amazonaws.com/identity_cards/5994710.png"

            for folder in user_folders:
                saved_reels_qs = SavedReel.objects.filter(
                    user=request.user,
                    folder=folder
                ).select_related("reel")

                reels_list = []
                for saved in saved_reels_qs:
                    reel = saved.reel
                    reel_data = StoreReelSerializer(reel, context={"request": request}).data

                    # Clean and set thumbnail URL
                    reel_data["thumbnail"] = self.get_thumbnail_url(request, reel)
                    reels_list.append(reel_data)

                # Set folder image from first reel's thumbnail
                if reels_list:
                    folder_image = reels_list[0].get("thumbnail") or static_image_url
                else:
                    folder_image = static_image_url

                folders_data.append({
                    "folder_id": folder.id,
                    "folder_name": folder.name,
                    "folder_image": folder_image,
                    "count": len(reels_list),
                    "reels": reels_list
                })

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "All folders with saved reels retrieved successfully.",
                "data": folders_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                "statusCode": 500,
                "status": False,
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_thumbnail_url(self, request, reel):
        """
        Generate a clean, fully qualified thumbnail URL for the reel.
        """
        thumbnail_url = None

        if reel.thumbnail:
            if str(reel.thumbnail).startswith("http"):
                thumbnail_url = str(reel.thumbnail)
            else:
                try:
                    if hasattr(reel.thumbnail, 'url'):
                        thumbnail_url = request.build_absolute_uri(reel.thumbnail.url)
                    else:
                        thumbnail_url = request.build_absolute_uri(str(reel.thumbnail))
                except Exception:
                    thumbnail_url = None

        if thumbnail_url:
            # Decode URL if double-encoded
            if "https%3A" in thumbnail_url:
                thumbnail_url = urllib.parse.unquote(thumbnail_url)

            # Remove any duplicate S3 prefix
            if thumbnail_url.startswith("https://markerplacemobileapp.s3.us-east-1.amazonaws.com/https"):
                thumbnail_url = thumbnail_url.replace("https://markerplacemobileapp.s3.us-east-1.amazonaws.com/", "")

        return thumbnail_url


# class GetSavedLikedReelsAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         try:
#             user_folders = ReelFolder.objects.filter(user=request.user).order_by("-created_at")

#             if not user_folders.exists():
#                 return Response({
#                     "statusCode": 200,
#                     "status": False,
#                     "message": "No folders found.",
#                     "data": []
#                 }, status=status.HTTP_200_OK)

#             folders_data = []
#             static_image_url ="https://markerplacemobileapp.s3.us-east-1.amazonaws.com/identity_cards/5994710.png"

#             for folder in user_folders:
#                 saved_reels_qs = SavedReel.objects.filter(
#                     user=request.user,
#                     folder=folder
#                 ).select_related("reel")

#                 reels_list = [
#                     StoreReelSerializer(saved.reel, context={"request": request}).data
#                     for saved in saved_reels_qs
#                 ]
#                 if reels_list:
#                     first_reel = reels_list[0]
#                     thumbnail = first_reel.get("thumbnail") or first_reel.get("thumbnail_url")
#                     folder_image = thumbnail if thumbnail else static_image_url
#                 else:
#                     folder_image = static_image_url

#                 folders_data.append({
#                     "folder_id": folder.id,
#                     "folder_name": folder.name,
#                     "folder_image": folder_image,
#                     "count": len(reels_list),
#                     "reels": reels_list
#                 })

#             return Response({
#                 "statusCode": 200,
#                 "status": True,
#                 "message": "All folders with saved reels retrieved successfully.",
#                 "data": folders_data
#             }, status=status.HTTP_200_OK)

#         except Exception as e:
#             import traceback
#             traceback.print_exc()
#             return Response({
#                 "statusCode": 500,
#                 "status": False,
#                 "message": str(e)
#             }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IsTicketOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user
from distutils.util import strtobool

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ProfessionalUser.models import (Order, RoomBooking, aestheticsBooking,
                                     eventBooking, experienceBooking,
                                     slotBooking)
from ProfessionalUser.signals import on_support_ticket_created
from UserApp.models import SupportTicket


class CreateSupportTicketView(APIView):
    def post(self, request):
        data = request.data
        ticket_category = data.get("ticket_category")
        subject = data.get("subject")
        description = data.get("description")
        documents = data.get("documents")
        

        specific_order = data.get("specific_order", False)
        if isinstance(specific_order, str):
            try:
                specific_order = bool(strtobool(specific_order))
            except ValueError:
                return Response({
                    "status": False,
                    "statusCode": 400,
                    "message": "Invalid value for 'specific_order'. Must be true or false."
                }, status=status.HTTP_200_OK)

        booking_id = data.get("order_id")  # Can be order_id or booking_id
        type_of_user = data.get("type_of_user", "user")  # Optional fallback
        if not ticket_category or not subject or not description:
            return Response({"status": False,"statusCode": 400, "message": "Missing required fields."},
                            status=status.HTTP_200_OK)
        if specific_order:
            if not booking_id:
                return Response({
                    "status": False,
                    "statusCode": 400,
                    "message": "Order ID or Booking ID is required when 'specific_order' is true."
                }, status=status.HTTP_200_OK)
        order_instance = None
        if booking_id:
            if "ORD-" in booking_id:
                order_instance = Order.objects.filter(order_id=booking_id).first()
            elif "ROM-" in booking_id:
                order_instance = RoomBooking.objects.filter(booking_id=booking_id).first()
            elif "EVT-" in booking_id:
                order_instance = eventBooking.objects.filter(booking_id=booking_id).first()
            elif "EXP-" in booking_id:
                order_instance = experienceBooking.objects.filter(booking_id=booking_id).first()
            elif "SLT-" in booking_id:
                order_instance = slotBooking.objects.filter(booking_id=booking_id).first()
            elif "AES-" in booking_id:
                order_instance = aestheticsBooking.objects.filter(booking_id=booking_id).first()
            elif "RLX-" in booking_id:
                order_instance = relaxationBooking.objects.filter(booking_id=booking_id).first()        
            elif "ATC-" in booking_id:
                order_instance = artandcultureBooking.objects.filter(booking_id=booking_id).first()

        if specific_order and not order_instance:
            return Response({
                "status": False,
                "statusCode": 404,
                "message": "Invalid order or booking ID provided."
            }, status=status.HTTP_200_OK)
        ticket = SupportTicket.objects.create(
            ticket_category=ticket_category,
            subject=subject,
            description=description,
            documents=documents,
            specific_order=specific_order,
            order=order_instance if order_instance and hasattr(order_instance, 'pk') else None,
            created_by_user_id=request.user.id if request.user.is_authenticated else None,
            type_of_user=type_of_user,
        )
        on_support_ticket_created(ticket)
        serializer = SupportTicketSerializer(ticket)
        return Response({
            "status": True,
            "statusCode": 200,
            "message": "Support ticket created successfully.",
            "ticket": serializer.data
        }, status=status.HTTP_201_CREATED)





# --- Update Support Ticket ---
class UpdateSupportTicketView(generics.UpdateAPIView):
    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated, IsTicketOwner]
    lookup_field = 'pk'

    def update(self, request, *args, **kwargs):
        try:
            ticket = self.get_object()
        except SupportTicket.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Support ticket not found.",
                "data": None
            }, status=status.HTTP_200_OK)

        if ticket.user != request.user:
            return Response({
                "statusCode": 403,
                "status": False,
                "message": "You are not allowed to update this ticket.",
                "data": None
            }, status=status.HTTP_200_OK)

        serializer = self.get_serializer(ticket, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Ticket updated successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)





import logging

logger = logging.getLogger(__name__)


class UserSupportTicketListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user_id = request.user.id
            logger.debug(f"Fetching tickets for user ID: {user_id}")
            tickets = SupportTicket.objects.filter(
                created_by_user_id=user_id,
                type_of_user='user',
                is_deleted=False
            )

            logger.debug(f"Tickets found before filters: {tickets.count()}")
            ticket_id = request.query_params.get('ticket_id')
            status_param = request.query_params.get('status')
            subject = request.query_params.get('subject')

            if ticket_id:
                tickets = tickets.filter(ticket_id__icontains=ticket_id)
            if status_param:
                tickets = tickets.filter(status__iexact=status_param)
            if subject:
                tickets = tickets.filter(subject__icontains=subject)

            logger.debug(f"Tickets found after filters: {tickets.count()}")

            if not tickets.exists():
                logger.debug("No tickets found for this user.")
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "No tickets found",
                    "data": []
                }, status=status.HTTP_200_OK)

            serializer = SupportTicketSerializer(tickets, many=True)
            ticket_data = [{**ticket, "chatNotifications": 5} for ticket in serializer.data]
                
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Tickets fetched successfully",
                "data": ticket_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching support tickets: {str(e)}")
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred while fetching tickets",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class UserSupportTicketDetailView(generics.RetrieveAPIView):
    serializer_class = SupportTicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SupportTicket.objects.all()
    lookup_field = 'pk'

    def retrieve(self, request, *args, **kwargs):
        try:
            ticket = self.get_object()
        except SupportTicket.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Support ticket not found.",
                "data": None
            }, status=status.HTTP_200_OK)
        if ticket.created_by_user_id != request.user.id:
            return Response({
                "statusCode": 403,
                "status": False,
                "message": "You are not allowed to view this ticket.",
                "data": None
            }, status=status.HTTP_200_OK)

        serializer = self.get_serializer(ticket)
        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Ticket retrieved successfully.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)



class FeedbackView(APIView):
    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "statusCode": 200,
                "status":True,
                "message": "Thanks for your feedback! We appreciate it.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "statusCode": 200,
            "status": False,
            "errors": serializer.errors
        }, status=status.HTTP_200_OK)
    

    

class TicketCategoryChoicesView(APIView):
    def get(self, request):
        categories = [
            {"type": key, "title": value}
            for key, value in SupportTicket.CATEGORY_CHOICES
        ]
        return Response({"status": True, "categories": categories}, status=status.HTTP_200_OK)

class FriendshipListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            user_ct = ContentType.objects.get_for_model(user.__class__)
            relation_type = request.query_params.get('type', None)
            page = int(request.GET.get("page", 1))
            per_page = int(request.GET.get("per_page", 10))

            followers = []
            following = []

            if relation_type in [None, 'follower']:
                followers = Friendship.objects.filter(
                    Q(status__in=["accepted", "message", "follow"]),
                    receiver_content_type=user_ct,
                    receiver_object_id=user.id,
                    relationship_type='follow',
                )

            if relation_type in [None, 'following']:
                following = Friendship.objects.filter(
                    Q(status__in=["accepted", "message", "follow"]),
                    sender_content_type=user_ct,
                    sender_object_id=user.id,
                    relationship_type='follow',
                )


            combined_data = []
            def extract_user_data(friendship, relation):
                user_instance = friendship.sender if relation == 'sender' else friendship.receiver
                result = {
                    "id": None,
                    "username": "",
                    "firstName": "",
                    "lastName": "",
                    "email": "",
                    "profileImage": None,
                    "request_id": friendship.id,
                    "status": friendship.status,
                    "type": "",
                }

                if isinstance(user_instance, Users):
                    result.update({
                        "id": user_instance.id,
                        "username": user_instance.username,
                        "firstName": user_instance.firstName,
                        "lastName": user_instance.lastName,
                        "email": user_instance.email,
                        "profileImage": user_instance.profileImage.url if user_instance.profileImage else None,
                        "type": "users",
                    })

                elif isinstance(user_instance, ProfessionalUser):
                    company = user_instance.company
                    manager_name = company.managerFullName if company and company.managerFullName else ""
                    first_name, last_name = "", ""
                    if manager_name:
                        split_name = manager_name.split()
                        first_name = split_name[0] if len(split_name) > 0 else ""
                        last_name = split_name[1] if len(split_name) > 1 else ""

                    result.update({
                        "id": user_instance.id,
                        "username": user_instance.userName,
                        "firstName": first_name,
                        "lastName": last_name,
                        "email": user_instance.email,
                        "profileImage": company.profilePhoto.url if company and company.profilePhoto else None,
                        "type": "professional",
                    })

                elif isinstance(user_instance, CompanyDetails):
                    manager_name = user_instance.managerFullName if user_instance.managerFullName else ""
                    first_name, last_name = "", ""
                    if manager_name:
                        split_name = manager_name.split()
                        first_name = split_name[0] if len(split_name) > 0 else ""
                        last_name = split_name[1] if len(split_name) > 1 else ""

                    result.update({
                        "id": user_instance.id,
                        "username": user_instance.userName,
                        "firstName": first_name,
                        "lastName": last_name,
                        "email": user_instance.email,
                        "profileImage": user_instance.profilePhoto.url if user_instance.profilePhoto else None,
                        "type": "company",
                    })

                return result
            for friendship in followers:
                data = extract_user_data(friendship, 'sender')
                if data:
                    combined_data.append(data)

            for friendship in following:
                data = extract_user_data(friendship, 'receiver')
                if data:
                    combined_data.append(data)


            paginator = Paginator(combined_data, per_page)
            paginated_data = paginator.get_page(page)

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Friendships retrieved successfully.",
                "totalUsers": paginator.count,
                "totalPages": paginator.num_pages,
                "currentPage": page,
                "data": list(paginated_data)
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"Error retrieving friendships: {str(e)}",
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class FollowersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            user_ct = ContentType.objects.get_for_model(user.__class__)

            followers = Friendship.objects.filter(
                receiver_content_type=user_ct,
                receiver_object_id=user.id,
                relationship_type='follow',
                status='follow'
            )

            serializer = FriendshipSerializer(followers, many=True, context={'relation': 'sender'})

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Followers retrieved successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"Error retrieving followers: {str(e)}",
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class FollowingListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            user_ct = ContentType.objects.get_for_model(user.__class__)

            following = Friendship.objects.filter(
                sender_content_type=user_ct,
                sender_object_id=user.id,
                relationship_type='follow',
                status='follow'
            )

            serializer = FriendshipSerializer(following, many=True, context={'relation': 'receiver'})

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Following retrieved successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"Error retrieving following: {str(e)}",
                "data": []
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class HelpAndSupport(APIView):
    def get(self, request):
        categories = HelpCategory.objects.prefetch_related('faqs').all()
        serializer = HelpCategorySerializer(categories, many=True)
        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Help Center content retrieved successfully.",
            "categories": serializer.data
        })
    
class CreateSupportRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CustomerSupportSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)  # Pass user explicitly here
            return Response({
                "status": True,
                "message": "Support request submitted successfully",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "status": False,
            "message": "Support request submission failed",
            "errors": serializer.errors
        }, status=status.HTTP_200_OK)


class GetPrivacySettingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            setting, created = PrivacySetting.objects.get_or_create(user=request.user)
            serializer = PrivacySettingSerializer(setting)
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Privacy settings fetched successfully" if not created else "Privacy settings created with default values",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred while fetching privacy settings.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdatePrivacySettingView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        try:
            setting, created = PrivacySetting.objects.get_or_create(user=request.user)
            serializer = PrivacySettingSerializer(setting, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": "Privacy settings updated successfully" if not created else "Privacy settings created successfully",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)

            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Validation failed",
                "errors": serializer.errors
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred while updating privacy settings.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class CompanyReelsView(APIView):

    def get(self, request, company_id):
        try:
            company = CompanyDetails.objects.prefetch_related('facilities').get(id=company_id)
        except CompanyDetails.DoesNotExist:
            return Response({"status": False, "message": "Company not found"}, status=status.HTTP_200_OK)

        store_reels = StoreReel.objects.filter(company_id=company.id)
        
        if not store_reels.exists():
            return Response({"status": False, "message": "No reels found for this company"}, status=status.HTTP_200_OK)

        def safe_url(field):
            return field.url if field and hasattr(field, 'url') else None

        def get_opening_status(opening_hours):
            if not opening_hours:
                return "closed"

            now = timezone.localtime(timezone.now())
            current_time = now.time()
            today = now.strftime('%A').lower()

            if today not in opening_hours:
                return "closed"

            today_hours = opening_hours[today]

            try:
                start_time = datetime.strptime(today_hours['start_time'], '%H:%M').time()
                end_time = datetime.strptime(today_hours['end_time'], '%H:%M').time()
            except (KeyError, ValueError):
                return "closed"

            start_datetime = datetime.combine(now.date(), start_time).replace(tzinfo=now.tzinfo)
            end_datetime = datetime.combine(now.date(), end_time).replace(tzinfo=now.tzinfo)

            if now < start_datetime:
                if (start_datetime - now) <= timedelta(hours=1):
                    return "opening soon"
                return "closed"
            elif start_datetime <= now <= end_datetime:
                if (end_datetime - now) <= timedelta(hours=1):
                    return "closing soon"
                return "open"
            else:
                return "closed"

        opening_status = get_opening_status(company.opening_hours)

        response_data = []
        for reel in store_reels:
            response_data.append({
                "company_data": {
                    "id": company.id,
                    "companyName": company.companyName,
                    "userName": company.userName,
                    "managerFullName": company.managerFullName,
                    "email": company.email,
                    "phoneNumber": company.phoneNumber,
                    "sectorofActivity": company.sectorofActivity,
                    "siret": company.siret,
                    "vatNumber": company.vatNumber,
                    "created_at": company.created_at,
                    "updated_at": company.updated_at,
                    "isActive": company.isActive,
                    "average_rating": company.average_rating,
                    "minimum_order_amount": company.minimum_order_amount,
                    "total_ratings": company.total_ratings,
                    "opening_status": opening_status if opening_status else "Closed",
                    "manual_address": {
                        "address1": company.manual_address.address1 if company.manual_address else None,
                        "address2": company.manual_address.address2 if company.manual_address else None,
                        "postalCode": company.manual_address.postalCode if company.manual_address else None,
                        "city": company.manual_address.city if company.manual_address else None,
                        "state": company.manual_address.state if company.manual_address else None,
                        "country": company.manual_address.country if company.manual_address else None,
                        "latitude": company.manual_address.lat if company.manual_address else None,
                        "longitude": company.manual_address.lang if company.manual_address else None,
                    } if company.manual_address else None,
                    "facilities": [
                        {
                            "id": facility.id,
                            "name": facility.name,
                            "icon": safe_url(facility.icon),
                        }
                        for facility in company.facilities.all()
                    ],
                },
                "store_reels": {
                    "id": reel.id,
                    "title": reel.title,
                    "video_url": safe_url(reel.video),
                    "thumbnail_url": safe_url(reel.thumbnail),
                    "companyName": company.companyName,
                    "profilePhoto": safe_url(company.profilePhoto),
                    "category": reel.category.name if reel.category else None,
                    "categoryId": reel.category.id if reel.category else None,
                    "video": safe_url(reel.video),
                    "thumbnail": safe_url(reel.thumbnail),
                    "likes": reel.likes,
                    "shares": reel.shares,
                    "comments": reel.comments,
                    "views": reel.views,
                }
            })

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Company reels fetched successfully",
            "data": response_data
        }, status=status.HTTP_200_OK)



from Admin.models import ReelReport
from Admin.serializers import ReelReportSerializer


class GetReportReasonsView(APIView):
    def get(self, request):
        reasons = [{"reasons": key, "label": label} for key, label in ReelReport.REPORT_REASONS]
        return Response({
            "message": "Report reasons fetched successfully",
            "statusCode": 200,
            "status": True,
            "data": reasons
        }, status=status.HTTP_200_OK)
    

class CreateReelReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReelReportSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            reel_report = serializer.save(user=request.user)
            on_reel_reported(reel_report)
            
            return Response({
                "message": "Reel reported successfully",
                "statusCode": 201,
                "status": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response({
            "message": "Validation error",
            "statusCode": 400,
            "status": False,
            "errors": serializer.errors
        }, status=status.HTTP_200_OK)


class ListUserReelReportsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reports = ReelReport.objects.filter(user=request.user)
        serializer = ReelReportSerializer(reports, many=True)
        return Response({
            "message": "Reel reports fetched successfully",
            "statusCode": 200,
            "status": True,
            "data": serializer.data
        }, status=status.HTTP_200_OK)




class LoyaltyPointListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            loyalty_qs = LoyaltyPoint.objects.filter(user=request.user).select_related('company')

            if not loyalty_qs.exists():
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "No loyalty points found."
                }, status=status.HTTP_200_OK)

            result = []

            for l in loyalty_qs:
                last_booking_time = None
                booking_models = [
                    RoomBooking, eventBooking, experienceBooking, slotBooking,
                    aestheticsBooking, relaxationBooking, artandcultureBooking, Order
                ]

                for model in booking_models:
                    filter_kwargs = {
                        "user": request.user,
                        "company": l.company
                    }

                    if model.__name__ == 'Order':
                        filter_kwargs["orderStatus"] = "fulfilled"
                    elif model.__name__ == 'RoomBooking':
                        filter_kwargs["booking_status"] = "completed"
                    else:
                        filter_kwargs["status"] = "completed"
                    booking = model.objects.filter(**filter_kwargs).order_by('-created_at').first()

                    if booking and (not last_booking_time or booking.created_at > last_booking_time):
                        last_booking_time = booking.created_at

                result.append({
                    "company_id": l.company.id,
                    "company_name": l.company.companyName,
                    "profile_photo": request.build_absolute_uri(l.company.profilePhoto.url) if l.company.profilePhoto else None,
                    "total_points": l.total_points,
                    "total_ratings": l.company.average_rating,
                    "card_id": l.id,
                    "updates_time": last_booking_time.strftime('%d %B %Y, %I:%M %p') if last_booking_time else None,
                })

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Loyalty points fetched successfully.",
                "data": result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"An error occurred: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

    




class LoyaltyCardProductListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        try:
            try:
                company = CompanyDetails.objects.get(id=company_id)
            except CompanyDetails.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "Company not found."
                }, status=status.HTTP_200_OK)
            loyalty = LoyaltyPoint.objects.filter(user=request.user, company=company).first()
            user_points = loyalty.total_points if loyalty else 0
            loyalty_cards = LoyaltyCard.objects.filter(company=company, status=True).select_related('product')
            product_data = []
            for card in loyalty_cards:
                product = card.product
                is_locked = user_points < card.threshold_point

                product_data.append({
                    "product_id": product.id,
                    "product_name": product.productname,
                    "threshold_point": card.threshold_point,
                    "is_locked": is_locked,
                    "image": request.build_absolute_uri(product.ProductImage.url) if product.ProductImage else None,
                })

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Loyalty card products fetched successfully.",
                "user_loyalty_points": user_points,
                "loyalitycard_id":loyalty.id,
                "company_name": company.companyName,
                "products": product_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"An error occurred: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class RandomAdvertisementView(APIView):
    """
    API to fetch three random active advertisements.
    """
    def get(self, request):
        ads = Advertisement.objects.filter(is_active=True)
        
        if ads.exists():
            count = min(3, ads.count())
            random_ads = random.sample(list(ads), count)
            serializer = AdvertisementSerializer(random_ads, many=True)
            
            return Response({
                "message": "Random active advertisements fetched successfully",
                "status": True,
                "statusCode": 200,
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        return Response({
            "message": "No active advertisements available",
            "status": False,
            "statusCode": 404
        }, status=status.HTTP_200_OK)



class AdvertisementClickAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, ad_id):
        user = request.user
        advertisement = get_object_or_404(Advertisement, id=ad_id)

        ad_click, created = AdvertisementClick.objects.get_or_create(
            advertisement=advertisement,
            user=user,
            defaults={'count': 1}
        )

        if not created:
            ad_click.count += 1
            ad_click.save()

        return Response({
            "message": "Click recorded successfully",
            "status": True,
            "click_count": ad_click.count
        }, status=status.HTTP_200_OK)
    



class ReviewCreateAPIView(generics.CreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        product_id = request.data.get("product")
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {"statusCode": 400, "status": False, "message": "Product not found"},
                status=status.HTTP_200_OK
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, product=product)

        return Response(
            {
                "statusCode": 200,
                "status": True,
                "message": "Review added successfully",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
    
class ReviewDetailView(generics.RetrieveAPIView):
    """Fetch a single review by ID"""
    permission_classes = [IsAuthenticated]
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

    def get(self, request, review_id):
        try:
            review = Review.objects.get(id=review_id)
            serializer = ReviewSerializer(review)
            return Response({
                "statusCode": 200,
                "status": True,
                "message":"Data fetch successfully",
                "data": serializer.data
            })
        except Review.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Review not found"
            }, status=200)
        

class ReviewListView(APIView):
    """Fetch all reviews"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        reviews = Review.objects.all()
        serializer = ReviewSerializer(reviews, many=True)

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Reviews fetched successfully",
            "data": serializer.data
        })
    



class CruiseRoomListView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            rooms = CruiseRoom.objects.all()
            response_data = []

            for room in rooms:
                response_data.append({
                    "roomId": room.room_id,
                    "roomType": room.get_roomType_display(),
                    "roomQuantity": room.roomQuantity,
                    "roomPrice": str(room.roomPrice),
                    "totalMembers": room.adults,
                    "isAvailable": room.roomQuantity > 0
                })
            
            return Response({
                "message": "Room types fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": response_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": "Failed to fetch room types",
                "statusCode": 500,
                "status": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class UserOrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        orders = Order.objects.filter(user=user).prefetch_related(
            'order_items__product__cruiseFacility',
            'order_items__product__roomFacility',
            'order_items__product__rooms',
            'company__manual_address'
        )

        reviewed_product_ids = request.session.get('reviewed_products', [])

        grouped_orders = []
        now = timezone.localtime()
        current_weekday = now.strftime('%A').lower()

        for order in orders:
            company = order.company
            items = order.order_items.all()
            products_list = []
            for item in items:
                product = item.product
                if product:
                    is_rating_pending = product.id not in reviewed_product_ids

                    product_data = {
                        "product_id": product.id,
                        "product_name": product.productname,
                        "product_image": request.build_absolute_uri(product.ProductImage.url) if product.ProductImage else default_image_url("product_images"),
                        "quantity": item.quantity,
                        "price": round(item.price, 2),
                        "average_rating": product.average_rating,
                        "total_ratings": product.total_ratings,
                        "noofMembers":product.noofMembers,
                        "view":product.roomview,
                        "is_rating_pending": is_rating_pending
                    }
                    if getattr(product, 'cruiseName', None):
                        cruise_data = {
                            "cruise_name": product.cruiseName,
                            "start_address": product.startAddress.address1 if product.startAddress else None,
                            "end_address": product.endAddress.address1 if product.endAddress else None,
                            "pet_allowed": product.petAllowed,
                            "smoking_allowed": product.smokingAllowed,
                            "no_of_members": product.noofMembers,
                            "view": product.roomview,
                            "cruise_facilities": [
                                {"id": facility.id, "name": facility.name} 
                                for facility in product.cruiseFacility.all()
                            ],
                            "room_facilities": [
                                {"id": facility.id, "name": facility.name} 
                                for facility in product.roomFacility.all()
                            ],
                            "rooms": []
                        }

                        for room in product.rooms.all():
                            cruise_data["rooms"].append({
                                "room_id": room.room_id,
                                "room_type": room.get_roomType_display(),
                                "room_quantity": room.roomQuantity,
                                "booked_quantity": room.bookedQuantity,
                                "room_price": float(room.roomPrice) if room.roomPrice else None,
                                "totalMember": room.adults
                            })

                        product_data["cruise_details"] = cruise_data

                    products_list.append(product_data)

            grouped_orders.append({
                "company": {
                    "company_id": company.id if company else None,
                    "company_name": company.companyName if company else "Unknown",
                    "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company and company.profilePhoto else default_image_url("product_images"),
                    "company_address": company.manual_address.address1 if company and company.manual_address else None,
                    "company_pincode": company.manual_address.postalCode if company and company.manual_address else None,
                    "companyratings": company.average_rating if company else 0.0,
                },
                "item_count": items.count(),
                "status": order.orderStatus,
                "order_id": order.order_id,
                "total_price": round(order.total_price, 2),
                "order_type": order.order_type,
                "order_date": order.created_at.strftime("%d-%b-%Y"),
                "products": products_list
            })

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "User orders fetched successfully",
            "orders": grouped_orders
        }, status=status.HTTP_200_OK)



class UserOrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            user = request.user
            order = Order.objects.filter(order_id=order_id, user=user).first()
            if not order:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": f"Order with ID {order_id} not found for user {user.email if user.email else user.username}"
                }, status=status.HTTP_200_OK)
            company = order.company
            company_data = {
                "company_id": company.id if company else None,
                "company_name": company.companyName if company else None,
                "manager_name": company.managerFullName if company else None,
                "company_profile_photo": (company.profilePhoto.url) if company and company.profilePhoto else None,
                "selected_cover_photo": company.selectedCoverPhoto if company else None,
                "phone_number": company.phoneNumber if company else None,
                "siret": company.siret if company else None,
                "vat_number": company.vatNumber if company else None,
                "sector_of_activity": company.sectorofActivity if company else None,
                "email": company.email if company else None,
                "is_open": company.isActive if company else False,
                "average_rating": company.average_rating if company else 0.0,
                "total_ratings": company.total_ratings if company else 0,
                "total_visits": company.total_visits if company else 0,
                "minimum_order_quantity": company.minimum_order_quantity if company else None,
                "minimum_order_amount": float(company.minimum_order_amount) if company and company.minimum_order_amount else None,
                "onsite": company.onsite if company else False,
                "clickcollect": company.clickcollect if company else False,
                "opening_hours": company.opening_hours if company else None,
                "facilities": [
                        {"id": facility.id, "name": facility.name} 
                        for facility in company.facilities.all()
                    ] if company else [],

                    "categories": [
                        {"id": category.id, "name": category.name} 
                        for category in company.categories.all()
                    ] if company else [],

                    "subcategories": [
                        {"id": subcategory.id, "name": subcategory.name} 
                        for subcategory in company.subcategories.all()
                    ] if company else [],
            }
            products_data = []
            for item in order.order_items.all():
                product = item.product
                product_data = {
                    "product_id": product.id if product else None,
                    "product_name": product.productname if product else None,
                    "product_image": product.ProductImage.url if product and product.ProductImage else None,
                    "quantity": item.quantity,
                    "price": item.price,
                    "average_rating": product.average_rating if product else 0.0,
                    "total_ratings": product.total_ratings if product else 0,
                    "noofMembers":product.noofMembers,
                    "view":product.roomview,
                    "is_rating_pending": True
                }
                if product and product.cruiseName:
                    cruise_data = {
                        "cruise_name": product.cruiseName,
                        "start_address": product.startAddress.address1 if product.startAddress else None,
                        "end_address": product.endAddress.address1 if product.endAddress else None,
                        "pet_allowed": product.petAllowed,
                        "smoking_allowed": product.smokingAllowed,
                        "no_of_members": product.noofMembers,
                        "view": product.roomview,
                        "cruise_facilities": [
                            {"id": facility.id, "name": facility.name} 
                            for facility in product.cruiseFacility.all()
                        ],
                        "room_facilities": [
                            {"id": facility.id, "name": facility.name} 
                            for facility in product.roomFacility.all()
                        ],
                        "rooms": []
                    }
                    for room in product.rooms.all():
                        cruise_data["rooms"].append({
                            "room_id": room.room_id,
                            "room_type": room.get_roomType_display(),
                            "room_quantity": room.roomQuantity,
                            "booked_quantity": room.bookedQuantity,
                            "room_price": float(room.roomPrice) if room.roomPrice else None,
                            "totalMember": room.adults
                        })

                    product_data["cruise_details"] = cruise_data

                products_data.append(product_data)
            preparation_time = None
            if order.order_type == 'Onsite':
                preparation_time = order.onSitePreparationTime
            elif order.order_type == 'Click and Collect':
                preparation_time = order.clickCollectPreparationTime
            elif order.order_type == 'Delivery':
                preparation_time = order.deliveryPreparationTime
            response_data = {
                "order_id": order.order_id,
                "item_count": order.order_items.count(),
                "status": order.orderStatus,
                "order_id": order.order_id,
                "total_price": order.total_price,
                "order_type": order.order_type,
                "order_date": order.created_at.strftime("%d-%b-%Y"),
                "company": company_data,
                "products": products_data
            }

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Order details fetched successfully",
                "data": response_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "Failed to fetch order details",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def render_invoice_view(request, order_id):
    user = get_object_or_404(Users, email=request.user.email)  # Fixes the issue
    order = get_object_or_404(Order, order_id=order_id, user=user)
    return render(request, 'order_invoice.html', {'order': order})

from geopy.distance import geodesic


class UserOrderTrackingView(APIView):
    def get(self, request):
        tracking_id = request.query_params.get('tracking_id')
        if not tracking_id:
            return Response({"status": False, "message": "Tracking ID is required"}, status=status.HTTP_200_OK)
 
        tracking_data = []
        product_based = [
            "fast_food", "bakeries_pastrie", "themed_bars", "rooftop",
            "bookstores", "clothing_stores", "grocery_stores", "decoration_shops",
            "local_product_shops", "artisan_stores", "organic_store", "supermarket"
        ]

        reservation_based = [
            "gourmet_restaurants", "themed_dining", "hotel_dining", "brunches",
            "hotels", "guest_houses", "camping", "inns_lodges", "chalets_cabins",
            "unusual_accommodation", "cruises_pleasure_boats", "spa_swimming_pool"
        ]

        service_based = [
            "facial_body_hair_treatments", "barbers", "tattoos_piercings", "manicure_pedicure_salons",
            "makeup", "hair_removal", "tanning_services","hairsalons",
            "massage_well_being", "meditation_relaxation", "alternative_therapies"
        ]

        event_based = [
            "museums_art_galleries", "theaters_operas", "cinema_videos",
            "libraries", "history_heritage", "cultural_festivals",
            "concerts", "music_festivals", "nightclubs",
            "amusement_parks", "events"
        ]

        experience_based = [
            "sport", "workshops", "activities_for_children", "guided_tours", "experiences",
            "animal_encounters", "personalized_course", "nautical_activity"
        ]
        def calculate_etm_time(created_at, checkin):
            if not isinstance(checkin, datetime):
                checkin = datetime.combine(checkin, time.min)
            if timezone.is_naive(created_at):
                created_at = timezone.make_aware(created_at)
            if timezone.is_naive(checkin):
                checkin = timezone.make_aware(checkin)

            if checkin < created_at:
                return "0 min"

            time_diff = checkin - created_at
            total_minutes = round(time_diff.total_seconds() / 60, 2)

            if total_minutes >= 1440:
                days = round(total_minutes / 1440, 2)
                return f"{days} day{'s' if days != 1 else ''}"
            elif total_minutes >= 60:
                hours = round(total_minutes / 60, 2)
                return f"{hours} hr{'s' if hours != 1 else ''}"
            else:
                return f"{total_minutes} min"
        

        def get_tracking_type(sub_name: str) -> str:
            mapping = {
                "product": product_based,
                "reservation": reservation_based,
                "service": service_based,
                "event": event_based,
                "experience": experience_based,
            }
            for key, group in mapping.items():
                if sub_name in group:
                    return key
            return "default"

       
        try:
            if Order.objects.filter(order_id=tracking_id).exists():
                order = Order.objects.get(order_id=tracking_id)
                order_items = OrderItem.objects.filter(order=order)
                # Determine button visibility
                order_cancel_statuses = ["cancelled", "fulfilled"]
                order_canceled_btn_show = order.orderStatus.lower() not in order_cancel_statuses


                for item in order_items:
                    product = item.product
                    subcategory = product.subCategoryId
                    category = subcategory.parentCategoryId if subcategory else None
                    delivery_address = None
                    etm_time = "1 hr"

                    from .serializers import \
                        UserAddressSerializer  # if not already imported

                    if order.order_type.lower() == "delivery":
                        user_address = order.user_address
                        if user_address:
                            delivery_address = UserAddressSerializer(user_address).data
                            if (
                                user_address.lat and user_address.lang and
                                order.company.manual_address.lat and order.company.manual_address.lang
                            ):
                                user_coords = (user_address.lat, user_address.lang)
                                company_coords = (order.company.manual_address.lat, order.company.manual_address.lang)

                                distance_km = geodesic(user_coords, company_coords).km
                                total_minutes = round(distance_km * 2, 2)  # 2 minutes per km

                                if total_minutes >= 1440:
                                    days = round(total_minutes / 1440, 2)
                                    etm_time = f"{days} day{'s' if days != 1 else ''}"
                                elif total_minutes >= 60:
                                    hours = round(total_minutes / 60, 2)
                                    etm_time = f"{hours} hr{'s' if hours != 1 else ''}"
                                else:
                                    etm_time = f"{total_minutes} min"

                               




                    sub_name = subcategory.slug if subcategory else None
                    cat_name = category.name if category else None

                    tracking_type = "default"
                    if sub_name in product_based:
                        tracking_type = "product"
                    elif sub_name in reservation_based:
                        tracking_type = "reservation"
                    elif sub_name in service_based:
                        tracking_type = "service"
                    elif sub_name in event_based:
                        tracking_type = "event"
                    elif sub_name in experience_based:
                        tracking_type = "experience"

                    tracking_info = {
                        "order_id": order.order_id,
                        "order_canceled_btn_show": order_canceled_btn_show,
                        "booking_id": order.order_id,
                        "order_type": order.order_type,
                        "order_status": order.orderStatus,
                        "is_paid": order.is_paid,
                        "total_price": order.total_price,
                        "company": order.company.companyName,
                        "delivery_address": delivery_address,
                        "order_name": product.productname,
                        "subcategory": sub_name,
                        "category": cat_name,
                        "ETM": etm_time,
                        "created_at_date": order.created_at.strftime("%Y-%m-%d"),
                        "created_at_time": order.created_at.strftime("%I:%M %p"),
                        "tracking_steps": self.get_tracking_steps(
                            category_type=tracking_type,
                            current_status=order.orderStatus,
                            updated_at=order.updated_at,
                            booking_date=order.date,
                            booking_time=order.time,
                            booking_durations=order.serviceDuration
                        )
                    }

                    tracking_data.append(tracking_info)
            elif RoomBooking.objects.filter(booking_id=tracking_id).exists():
                booking = RoomBooking.objects.get(booking_id=tracking_id)
                product = booking.product
                subcategory = product.subCategoryId
                category = subcategory.parentCategoryId if subcategory else None
                sub_name = subcategory.slug if subcategory else None
                cat_name = category.name if category else None
                created_at = booking.created_at
                checkin = booking.booking_date 
                # Determine button visibility
                booking_cancel_statuses = ["cancelled", "completed", "rejected"]
                order_canceled_btn_show = booking.booking_status.lower() not in booking_cancel_statuses

                etm_time = calculate_etm_time(created_at, checkin)
                tracking_type = get_tracking_type(sub_name)
 
                tracking_data.append({
                    "order_id": booking.booking_id,
                    "booking_id": booking.booking_id,
                    "order_canceled_btn_show": order_canceled_btn_show,
                    "order_name": product.productname,
                    "total_price": booking.total_price,
                    "company": booking.company.companyName,
                    "subcategory": subcategory.slug if subcategory else None,
                    "category": category.name if category else None,
                    "order_status": booking.booking_status,
                    "ETM": etm_time,
                    "booking_date_date": booking.booking_date.strftime("%Y-%m-%d") if booking else None,
                    "booking_date_time": booking.booking_date.strftime("%I:%M %p")if booking else None,
                    "created_at_date": booking.created_at.strftime("%Y-%m-%d")if booking else None,
                    "created_at_time": booking.created_at.strftime("%I:%M %p")if booking else None,
                    "tracking_steps": self.get_tracking_steps(
                    category_type=tracking_type,  
                    current_status=booking.booking_status,
                    updated_at=booking.updated_at,
                    booking_date=booking.booking_date,
                    booking_time=booking.room.product.endTime,
                    booking_durations=booking.room.product.duration 
                )
 
                })
            elif eventBooking.objects.filter(booking_id=tracking_id).exists():
                event = eventBooking.objects.get(booking_id=tracking_id)
                product = event.ticket_id
                subcategory = product.subCategoryId
                category = subcategory.parentCategoryId if subcategory else None
                sub_name = subcategory.slug if subcategory else None
                cat_name = category.name if category else None
                created_at = event.created_at
                checkin = event.booking_date
                # Determine button visibility
                event_cancel_statuses = ["cancelled", "completed", "rejected"]
                order_canceled_btn_show = event.status.lower() not in event_cancel_statuses

                etm_time = calculate_etm_time(created_at, checkin)
                tracking_type = get_tracking_type(sub_name)
                tracking_data.append({
                    "order_id": event.booking_id,
                    "booking_id": event.booking_id,
                    "order_canceled_btn_show": order_canceled_btn_show,
                    "order_name": product.productname,
                    "total_price": event.price,
                    "company": event.company.companyName,
                    "subcategory": subcategory.slug if subcategory else None,
                    "category": category.name if category else None,
                    "order_status": event.status,
                    "ETM": etm_time,
                    "created_at_date": event.created_at.strftime("%Y-%m-%d"),
                    "created_at_time": event.created_at.strftime("%I:%M %p"),
                    "booking_date": event.booking_date.strftime("%Y-%m-%d"),
                    "booking_time":event.booking_time.strftime("%I:%M %p"),
                    "booking_durations":event.ticket_id.duration,
                    "tracking_steps": self.get_tracking_steps(
                    category_type=tracking_type,  # or "event", "experience"
                    current_status=event.status,
                    updated_at=event.updated_at,
                    booking_date=event.booking_date,
                    booking_time=event.booking_time,
                    booking_durations=event.ticket_id.duration
                )
 
                })
            elif experienceBooking.objects.filter(booking_id=tracking_id).exists():
                exp = experienceBooking.objects.get(booking_id=tracking_id)
                product = exp.ticket_id
                subcategory = product.subCategoryId
                category = subcategory.parentCategoryId if subcategory else None
                sub_name = subcategory.slug if subcategory else None
                cat_name = category.name if category else None
                created_at = exp.created_at
                checkin = exp.booking_date
                # Determine button visibility
                event_cancel_statuses = ["cancelled", "completed", "rejected"]
                order_canceled_btn_show = exp.status.lower() not in event_cancel_statuses

                etm_time = calculate_etm_time(created_at, checkin)
                tracking_type = get_tracking_type(sub_name) 
                tracking_data.append({
                    "order_id": exp.booking_id,
                    "booking_id": exp.booking_id,
                    "order_canceled_btn_show": order_canceled_btn_show,
                    "order_name": product.productname,
                    "total_price": exp.price,
                    "company": exp.company.companyName,
                    "subcategory": subcategory.slug if subcategory else None,
                    "category": category.name if category else None,
                    "order_status": exp.status,
                    "ETM": etm_time,
                    "created_at_date": exp.created_at.strftime("%Y-%m-%d"),
                    "created_at_time": exp.created_at.strftime("%I:%M %p"),
                    "booking_date": exp.booking_date.strftime("%Y-%m-%d"),
                    "booking_time":exp.booking_time.strftime("%I:%M %p"),
                    "booking_durations":exp.ticket_id.duration,
                    "tracking_steps": self.get_tracking_steps(
                    category_type=tracking_type,  
                    current_status=exp.status,
                    updated_at=exp.updated_at,
                    booking_date=exp.booking_date,
                    booking_time=exp.booking_time,
                    booking_durations=exp.ticket_id.duration
                )
 
                })
            elif slotBooking.objects.filter(booking_id=tracking_id).exists():
                slot = slotBooking.objects.get(booking_id=tracking_id)
                product = slot.Product
                subcategory = product.subCategoryId
                category = subcategory.parentCategoryId if subcategory else None
                sub_name = subcategory.slug if subcategory else None
                cat_name = category.name if category else None
                created_at = slot.created_at
                checkin = slot.booking_date
                event_cancel_statuses = ["cancelled", "completed", "rejected"]
                order_canceled_btn_show = slot.status.lower() not in event_cancel_statuses
                etm_time = calculate_etm_time(created_at, checkin)
                tracking_type = get_tracking_type(sub_name)
                tracking_data.append({
                    "order_id": slot.booking_id,
                    "booking_id": slot.booking_id,
                    "order_canceled_btn_show": order_canceled_btn_show,
                    "order_name": product.productname,
                    "total_price": slot.price,
                    "company": slot.company.companyName,
                    "subcategory": subcategory.slug if subcategory else None,
                    "category": category.name if category else None,
                    "order_status": slot.status,
                    "ETM": etm_time,
                    "created_at_date": slot.created_at.strftime("%Y-%m-%d"),
                    "created_at_time": slot.created_at.strftime("%I:%M %p"),
                    "booking_date": slot.booking_date.strftime("%Y-%m-%d"),
                    "booking_time":slot.booking_time.strftime("%I:%M %p"),
                    "booking_durations":slot.Product.duration,
                    "tracking_steps": self.get_tracking_steps(
                        category_type=tracking_type,
                        current_status=slot.status,
                        updated_at=slot.updated_at,
                        booking_date=slot.booking_date,
                        booking_time=slot.booking_time,
                        booking_durations=slot.Product.duration
                    )
                })

            elif aestheticsBooking.objects.filter(booking_id=tracking_id).exists():
                slot = aestheticsBooking.objects.get(booking_id=tracking_id)
                product = slot.Product
                subcategory = product.subCategoryId
                category = subcategory.parentCategoryId if subcategory else None
                sub_name = subcategory.slug if subcategory else None
                cat_name = category.name if category else None
                created_at = slot.created_at
                checkin = slot.booking_date
                event_cancel_statuses = ["cancelled", "completed", "rejected"]
                order_canceled_btn_show = slot.status.lower() not in event_cancel_statuses
                etm_time = calculate_etm_time(created_at, checkin)
                tracking_type = get_tracking_type(sub_name)
 
                tracking_data.append({
                    "order_id": slot.booking_id,
                    "booking_id": slot.booking_id,
                    "order_canceled_btn_show": order_canceled_btn_show,
                    "order_name": product.productname,
                    "total_price": slot.price,
                    "company": slot.company.companyName,
                    "subcategory": subcategory.slug if subcategory else None,
                    "category": category.name if category else None,
                    "order_status": slot.status,
                    "ETM": etm_time,
                    "created_at_date": slot.created_at.strftime("%Y-%m-%d"),
                    "created_at_time": slot.created_at.strftime("%I:%M %p"),
                    "booking_date": slot.booking_date.strftime("%Y-%m-%d"),
                    "booking_time":slot.booking_time.strftime("%I:%M %p"),
                    "booking_durations":slot.Product.duration ,
                    "tracking_steps": self.get_tracking_steps(
                        category_type=tracking_type,
                        current_status=slot.status,
                        updated_at=slot.updated_at,
                        booking_date=slot.booking_date,
                        booking_time=slot.booking_time,
                        booking_durations=slot.Product.duration
                    )
                })
            
            elif relaxationBooking.objects.filter(booking_id=tracking_id).exists():
                slot = relaxationBooking.objects.get(booking_id=tracking_id)
                product = slot.Product
                subcategory = product.subCategoryId
                category = subcategory.parentCategoryId if subcategory else None
                sub_name = subcategory.slug if subcategory else None
                cat_name = category.name if category else None
                created_at = slot.created_at
                checkin = slot.booking_date
                event_cancel_statuses = ["cancelled", "completed", "rejected"]
                order_canceled_btn_show = slot.status.lower() not in event_cancel_statuses
                etm_time = calculate_etm_time(created_at, checkin)
                tracking_type = get_tracking_type(sub_name)
                tracking_data.append({
                    "order_id": slot.booking_id,
                    "booking_id": slot.booking_id,
                    "order_canceled_btn_show": order_canceled_btn_show,
                    "order_name": product.productname,
                    "total_price": slot.price,
                    "company": slot.company.companyName,
                    "subcategory": subcategory.slug if subcategory else None,
                    "category": category.name if category else None,
                    "order_status": slot.status,
                    "ETM": etm_time,
                    "created_at_date": slot.created_at.strftime("%Y-%m-%d"),
                    "created_at_time": slot.created_at.strftime("%I:%M %p"),
                    "booking_date": slot.booking_date.strftime("%Y-%m-%d"),
                    "booking_time":slot.booking_time.strftime("%I:%M %p"),
                    "booking_durations":slot.Product.duration,
                    "tracking_steps": self.get_tracking_steps(
                        category_type=tracking_type,
                        current_status=slot.status,
                        updated_at=slot.updated_at,
                        booking_date=slot.booking_date,
                        booking_time=slot.booking_time,
                        booking_durations=slot.Product.duration
                    )
                })

            elif artandcultureBooking.objects.filter(booking_id=tracking_id).exists():
                slot = artandcultureBooking.objects.get(booking_id=tracking_id)
                product = slot.Product
                subcategory = product.subCategoryId
                category = subcategory.parentCategoryId if subcategory else None
                sub_name = subcategory.slug if subcategory else None
                cat_name = category.name if category else None
                created_at = slot.created_at
                checkin = slot.booking_date
                event_cancel_statuses = ["cancelled", "completed", "rejected"]
                order_canceled_btn_show = slot.status.lower() not in event_cancel_statuses
                etm_time = calculate_etm_time(created_at, checkin)
                tracking_type = get_tracking_type(sub_name)
                tracking_data.append({
                    "order_id": slot.booking_id,
                    "booking_id": slot.booking_id,
                    "order_canceled_btn_show": order_canceled_btn_show,
                    "order_name": product.productname,
                    "total_price": slot.price,
                    "company": slot.company.companyName,
                    "subcategory": subcategory.slug if subcategory else None,
                    "category": category.name if category else None,
                    "order_status": slot.status,
                    "ETM": etm_time,
                    "created_at_date": slot.created_at.strftime("%Y-%m-%d"),
                    "created_at_time": slot.created_at.strftime("%I:%M %p"),
                    "booking_date": slot.booking_date.strftime("%Y-%m-%d"),
                    "booking_time":slot.booking_time.strftime("%I:%M %p"),
                    "booking_durations":slot.Product.duration,
                    "tracking_steps": self.get_tracking_steps(
                        category_type=tracking_type,
                        current_status=slot.status,
                        updated_at=slot.updated_at,
                        booking_date=slot.booking_date,
                        booking_time=slot.booking_time,
                        booking_durations=slot.Product.duration
                    )
                })
            else:
                return Response({"status": False, "message": "No data found for this tracking ID"}, status=status.HTTP_200_OK)
 
            return Response({
                "status": True,
                "statusCode": 200,
                "message": "Tracking details fetched successfully",
                "data": tracking_data[0] if tracking_data else {}
            }, status=status.HTTP_200_OK)
 
        except Exception as e:
            return Response({"status": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get_tracking_steps(
            self,  category_type,  current_status,    updated_at,booking_time,  booking_durations=None,  
            booking_date=None,  step_status_history=None,  is_paid=False
        ):
        from datetime import datetime
        from django.conf import settings

        now = datetime.now()

        def get_icon_url(icon_name):
            try:
                icon = OrderBookingIcons.objects.get(name=icon_name)
                if icon.icon and icon.icon.name:
                    if icon.icon.url.startswith('http'):
                        return icon.icon.url
                    else:
                        return f"{settings.AWS_S3_CUSTOM_DOMAIN}/{icon.icon.name}"
            except OrderBookingIcons.DoesNotExist:
                return ""
            return ""

        def parse_iso_datetime(dt_str):
            try:
                if dt_str.endswith('Z'):
                    dt_str = dt_str[:-1] + '+00:00'
                return datetime.fromisoformat(dt_str)
            except Exception:
                return None

        def build_step(image_key, title, description, status_key):
            status_data = step_status_history.get(status_key, {}) if step_status_history else {}
            was_active = status_data.get('active', False)
            was_updated_at = status_data.get('updated_at')

            is_payment_step = status_key == "is_paid"
            is_current = status_key.lower() == current_status.lower()

            active = is_current or was_active or (is_payment_step and is_paid)

            if is_current or is_payment_step:
                date_time = updated_at if isinstance(updated_at, datetime) else now
            else:
                date_time = parse_iso_datetime(was_updated_at) or now

            if status_key.lower() == "reminder" and booking_date:
                try:
                    booking_date_dt = datetime.strptime(booking_date, "%Y-%m-%d").date()
                    if (booking_date_dt - now.date()).days == 1:
                        active = True
                except Exception:
                    pass
                description = f"{description} Booking date: {booking_date}"   

            return {
                "image": get_icon_url(image_key),
                "title": title,
                "description": description,
                "date": date_time.strftime("%Y-%m-%d"),
                "time": "",  # Will be set later properly
                "active": active,
                "status": status_key,
                "updated_at": date_time.isoformat()
            }

        step_templates = {
            "product": [
                ("PaymentCompleted", "Payment Completed", "Your payment is Successfull.", "is_paid"),
                ("orderRecive", "Ready to confirm", "we have received Your Order please wait for confirm.","new order"),
                ("OrderConfirmed", "Order Confirmed", "Your Order is confirmed.", "accepted"),
                ("OrderProcess", "Order Processed", "We are preparing your order.", "processing"),
                ("OrderPlaced", "Order Placed", "Your order has been Placed.", "fulfilled"),
                ("Cancelled", "Order Cancelled", "Your order has been Cancelled.", "cancelled"),
            ],
            "service": [
                ("PaymentCompleted", "Payment Completed", "Your payment is Successfull.", "is_paid"),
                ("servicePending", "Service Pending", "Service pending please wait to confirm.", "pending"),
                ("ServiceConformed", "Service Confirmed", "Your Service is confirmed.", "confirmed"),
                ("ServiceCompleted", "Service Completed", "Thanks for attending.", "completed"),
                ("ServiceCancelled", "Order Cancelled", "Your order has been Cancelled.", "cancelled"),
            ],
            "reservation": [
                ("PaymentCompleted", "Payment Completed", "Your payment is Successfull", "is_paid"),
                ("reservationPending", "Reservation Pending", "Reservation is pending please wait for confirm.", "pending"),
                ("reservationConfirmed", "Reservation Confirmed", "Reservation is confirmed.", "confirmed"),
                ("ExperienceBookingReminder", "Pre-event Reminder", "Get ready for your reservation.", "Reminder"),
                ("reservationCompleted", "Reservation Completed", "Thanks for visiting.", "completed"),
                ("reservationCancelled", "Order Cancelled", "Your order has been Cancelled.", "cancelled"),
            ],
            "event": [
                ("PaymentCompleted", "Payment Completed", "Your payment is Successfull.", "is_paid"),
                ("EventTicketConfirmed", "Ticket Confirmed", "Your ticket is confirmed.", "confirmed"),
                ("ExperienceBookingReminder", "Pre-event Reminder", "Get ready for your event.", "Reminder"),
                ("EventTicketCompleted", "Event Completed", "Thanks for attending.", "completed"),
                ("EventTicketCancelled", "Order Cancelled", "Your order has been Cancelled.", "cancelled"),
            ],
            "experience": [
                ("PaymentCompleted", "Payment Completed", "Your payment is Successfull.", "is_paid"),
                ("ExperienceBookingPending", "Experience Booking Pending", "Your experience is pending please wait for confirm.", "pending"),
                ("ExperienceBookingConfirmed", "Experience Booking Confirmed", "Your experience is confirmed.", "confirmed"),
                ("ExperienceBookingReminder", "Pre-Experience Reminder", "Get ready for your experience.", "Reminder"),
                ("ExperienceBookingCompleted", "Experience Completed", "Thank you for joining!", "completed"),
                ("ExperienceBookingConfirmedCancelled", "Order Cancelled", "Your order has been Cancelled.", "cancelled"),
            ],
        }

        category_steps = step_templates.get(category_type.lower(), [])
        # Calculate booking end time
        now = timezone.now()
        tracking_steps = []
        booking_end_time = None
        
        # if category_steps not in ["experience", "product", "roombooking"]:
        #     if booking_date and booking_time:
        #         try:
        #             booking_dt_str = f"{booking_date} {booking_time}"
        #             booking_dt = datetime.strptime(booking_dt_str, "%Y-%m-%d %H:%M:%S")

        #             if timezone.is_naive(booking_dt):
        #                 booking_dt = timezone.make_aware(booking_dt)

        #             # Set default duration to 1 hour if missing
        #             try:
        #                 duration_hours = int(booking_durations)
        #                 if duration_hours <= 0:
        #                     duration_hours = 1
        #             except (ValueError, TypeError):
        #                 duration_hours = 1

        #             booking_end_time = booking_dt + timedelta(hours=duration_hours)

        #             if now >= booking_end_time:
        #                 current_status = "completed"

        #                 # Update tracking_step_count
        #                 tracking_step_count = len([
        #                     step for step in tracking_steps
        #                     if step.get("status") and step["status"] != "Reminder"
        #                 ])

        #                 # Activate completed step
        #                 for step in tracking_steps:
        #                     if step.get("status") == "completed":
        #                         step["active"] = True

        #         except Exception as e:
        #             print("Booking parse error:", e)


        # Now check if booking has ended and update status
        # if booking_end_time and now >= booking_end_time:
        #     category_type_lower = category_type.lower()
        #     if category_type_lower not in ["experience", "roombooking"]:
        #         current_status = "completed"
        current_status_lower = current_status.lower()
        is_cancelled = current_status_lower == "cancelled"

        previous_step_count = 1
        last_valid_status = ""

        if isinstance(step_status_history, dict):
            try:
                previous_step_count = int(step_status_history.get("tracking_step_count", 0))
            except (ValueError, TypeError):
                previous_step_count = 0
            last_valid_status = step_status_history.get("last_valid_status", "").lower()

        if is_cancelled:
            reached_index = 0
            if last_valid_status:
                reached_index = next(
                    (i for i, (_, _, _, key) in enumerate(category_steps) if key.lower() == last_valid_status),
                    0
                )
            elif previous_step_count > 0:
                reached_index = previous_step_count - 1

            steps_to_build = category_steps[:reached_index + 1]

            cancel_step = next((s for s in category_steps if s[3].lower() == "cancelled"), None)
            if cancel_step and cancel_step not in steps_to_build:
                steps_to_build.append(cancel_step)
        else:
            steps_to_build = [s for s in category_steps if s[3].lower() != "cancelled"]

        # Improved tracking_step_count logic
        tracking_step_count = 1
        for i, (_, _, _, status_key) in enumerate(steps_to_build):
            if status_key.lower() == current_status_lower:
                tracking_step_count = i + 1
                break
        else:
            tracking_step_count = len(steps_to_build)

        steps = []
        for i, (icon_key, title, desc, status_key) in enumerate(steps_to_build):
            step = build_step(icon_key, title, desc, status_key)

            step_time = ""
            if i < tracking_step_count:
                step_time = ""

# Always try to get time from step_status_history if available
                if isinstance(step_status_history, dict):
                    time_key = f"time_{status_key.lower()}"
                    if time_key in step_status_history and step_status_history[time_key]:
                        step_time = step_status_history[time_key]

                # If no time found in step_status_history, fallback to updated_at time for all steps regardless of i < tracking_step_count
                if not step_time:
                    updated_at_val = step.get("updated_at")
                    dt = parse_iso_datetime(updated_at_val) if isinstance(updated_at_val, str) else None
                    if dt:
                        step_time = dt.strftime("%I:%M %p")

                step["time"] = step_time


            step["time"] = step_time
            steps.append(step)

        step_count = len(steps)

        return {
            "tracking_steps": steps,
            "step_count": step_count,
            "tracking_step_count": tracking_step_count
        }


    # def get_tracking_steps(self, category_type, current_status, updated_at, booking_date=None, step_status_history=None):
    #     """
    #     Builds the tracking steps for orders based on their category and current status.
        
    #     :param category_type: str, e.g., 'product', 'service', 'reservation', etc.
    #     :param current_status: str, current status of the order
    #     :param updated_at: datetime, current status last update time
    #     :param booking_date: optional datetime, booking date
    #     :param step_status_history: optional dict tracking previous active steps and timestamps
    #     :return: dict with steps, total count, and current tracking step position
    #     """

    #     now = datetime.now()
    #     steps = []

    #     def get_icon_url(icon_name):
    #         try:
    #             icon = OrderBookingIcons.objects.get(name=icon_name)
    #             if icon.icon and icon.icon.url:
    #                 return (
    #                     f"https://markerplacemobileapp.s3.us-east-1.amazonaws.com/{icon.icon.name}"
    #                     if icon.icon.url.startswith('http')
    #                     else f"{settings.AWS_S3_CUSTOM_DOMAIN}/{icon.icon.name}"
    #                 )
    #         except OrderBookingIcons.DoesNotExist:
    #             pass
    #         return ""

    #     def build_step(image_key, title, description, status_key):
    #         # Check historical active state or match with current status
    #         was_active = step_status_history.get(status_key, {}).get('active') if step_status_history else False
    #         was_updated_at = step_status_history.get(status_key, {}).get('updated_at') if step_status_history else None

    #         is_current = status_key.lower() == current_status.lower()
    #         active = is_current or was_active

    #         date_time = (
    #             updated_at if is_current else
    #             datetime.fromisoformat(was_updated_at) if was_updated_at else now
    #         )

    #         return {
    #             "image": get_icon_url(image_key),
    #             "title": title,
    #             "description": description,
    #             "date": date_time.strftime("%Y-%m-%d"),
    #             "time": date_time.strftime("%I:%M %p"),
    #             "active": active,
    #             "status": status_key,
    #             "updated_at": date_time.isoformat()
    #         }

    #     step_templates = {
    #         "product": [
    #             ("orderRecive", "Ready to Pickup", "we have recieved Your Order.", "new order"),#pending
    #             ("PaymentCompleted", "Payment Confirmed", "Your payment is confirmed.", "is_paid"),#is_paid =true
    #             ("OrderConfirmed", "Order Confirmed", "Your Order is confirmed.", "accepted"),#accepted
    #             ("OrderProcess", "Order Processed", "We are preparing your order.", "processing"),#processing
    #             ("OrderPlaced", "Order Placed", "Your order has been Placed.", "fulfilled"),#fulfilled
    #             ("Cancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         ],
    #         "service": [
    #             ("PaymentCompleted", "Reservation Service PaymentCompleted", "Your Service PaymentCompleted confirmed.", "is_paid"),#is_paid =true
    #             ("servicePending", "Reservation Booking servicePending", "Reservation servicePending.", "pending"),#pending
    #             ("ServiceConformed", "Reservation Service Confirmed", "Your Service is confirmed.", "confirmed"),
    #             ("ServiceCompleted", "Service Completed", "Thanks for attending.", "completed"),
    #             ("ServiceCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         ],
    #         # "service": [
    #         #     ("ServiceConformed", "Reservation Service Confirmed", "Your Service is confirmed.", "confirmed"),
    #         #     ("ServiceCompleted", "Service Completed", "Thanks for attending.", "completed"),
    #         #     ("ServiceCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         # ],
    #         "reservation": [
    #             ("PaymentCompleted", "Reservation Booking PaymentConfirmed", "Reservation PaymentConfirmed.", "is_paid"),#is_paid =true
    #             ("reservationPending", "Reservation Booking reservationPending", "Reservation reservationPending.", "pending"),#pending
    #             ("reservationConfirmed", "Reservation Booking Confirmed", "Reservation confirmed.", "confirmed"),#conformed
    #             ("reservationCompleted", "Experience Completed", "Thanks for visiting.", "completed"),#completed
    #             ("reservationCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),#cancelled
    #         ],
    #         # "reservation": [
    #         #     ("reservationConfirmed", "Reservation Booking Confirmed", "Reservation confirmed.", "confirmed"),
    #         #     ("reservationCompleted", "Experience Completed", "Thanks for visiting.", "completed"),
    #         #     ("reservationCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         # ],
    #         "event": [
    #             ("PaymentCompleted", "Reservation Ticket PaymentCompleted", "Your ticket is confirmed.", "is_paid"),
    #             ("EventTicketConfirmed", "Reservation Ticket Confirmed", "Your ticket is confirmed.", "confirmed"),
    #             ("ExperienceBookingReminder", "Pre-Experience Reminder", "Get ready for your experience.", "Reminder"),
    #             ("EventTicketCompleted", "Event Completed", "Thanks for attending.", "completed"),
    #             ("EventTicketCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         ],
    #         "experience": [
    #             ("PaymentCompleted", "Reservation Booking PaymentCompleted", "Your experience PaymentCompleted.", "is_paid"),#is_paid =true
    #             ("ExperienceBookingPending", "Reservation Booking pending", "Your experience is pending.", "pending"),#pending
    #             ("ExperienceBookingConfirmed", "Reservation Booking Confirmed", "Your experience is confirmed.", "confirmed"),#conformed
    #             ("ExperienceBookingReminder", "Pre-Experience Reminder", "Get ready for your experience.", "Reminder"),
    #             ("ExperienceBookingCompleted", "Experience Completed", "Thank you for joining!", "completed"),#completed
    #             ("ExperienceBookingConfirmedCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),#cancelled
    #         ],
    #         # "experience": [
    #         #     ("ExperienceBookingConfirmed", "Reservation Booking Confirmed", "Your experience is confirmed.", "confirmed"),
    #         #     ("ExperienceBookingReminder", "Pre-Experience Reminder", "Get ready for your experience.", "Reminder"),
    #         #     ("ExperienceBookingCompleted", "Experience Completed", "Thank you for joining!", "completed"),
    #         #     ("ExperienceBookingConfirmedCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         # ],
    #     }

    #     category_steps = step_templates.get(category_type.lower(), [])

    #     # If order is cancelled, trim steps to include only up to and including cancellation
    #     cancel_index = next((i for i, step in enumerate(category_steps) if step[3].lower() == "cancelled"), None)
    #     if current_status.lower() == "cancelled" and cancel_index is not None:
    #         steps_to_build = category_steps[:cancel_index] + [category_steps[cancel_index]]
    #     else:
    #         steps_to_build = category_steps

    #     for icon_key, title, desc, status_key in steps_to_build:
    #         steps.append(build_step(icon_key, title, desc, status_key))

    #     step_count = len(steps)

    #     # Find the LAST step index that matches the current status
    #     tracking_matches = [
    #         index + 1 for index, step in enumerate(steps)
    #         if step["status"].lower() == current_status.lower()
    #     ]
    #     tracking_step_count = tracking_matches[-1] if tracking_matches else 0

    #     return {
    #         "tracking_steps": steps,
    #         "step_count": step_count,
    #         "tracking_step_count": tracking_step_count
    #     }

#-----------------------------------------#########################---------------
    # def get_tracking_steps(self, category_type, current_status, updated_at, booking_date=None, step_status_history=None):
    #     """
    #     step_status_history: Optional dict of previous status steps to track active=True persistently.
    #         Example:
    #         {
    #             "new order": {"active": True, "updated_at": "2024-06-01T12:00:00"},
    #             "paid": {"active": True, "updated_at": "2024-06-01T12:15:00"},
    #         }
    #     """

    #     steps = []
    #     now = datetime.now()

    #     def get_icon_url(icon_name):
    #         try:
    #             icon = OrderBookingIcons.objects.get(name=icon_name)
    #             if icon.icon and icon.icon.url:
    #                 if icon.icon.url.startswith('http'):
    #                     return f"https://markerplacemobileapp.s3.us-east-1.amazonaws.com/{icon.icon.name}"
    #                 return f"{settings.AWS_S3_CUSTOM_DOMAIN}/{icon.icon.name}"
    #         except OrderBookingIcons.DoesNotExist:
    #             pass
    #         return ""

    #     def build_step(image_key, title, description, status_key):
    #         was_active = step_status_history.get(status_key, {}).get('active') if step_status_history else False
    #         was_updated_at = step_status_history.get(status_key, {}).get('updated_at') if step_status_history else None

    #         active = status_key.lower() == current_status.lower() or was_active
    #         date_time = updated_at if status_key.lower() == current_status.lower() else (
    #             datetime.fromisoformat(was_updated_at) if was_updated_at else now
    #         )

    #         return {
    #             "image": get_icon_url(image_key),
    #             "title": title,
    #             "description": description,
    #             "date": date_time.strftime("%Y-%m-%d"),
    #             "time": date_time.strftime("%I:%M %p"),
    #             "active": active,
    #             "status": status_key,
    #             "updated_at": date_time.isoformat()
    #         }
    #     step_templates = {
    #         "product": [
    #             ("confirmed", "Ready to Pickup", "Your order is ready to be picked up.", "new order"),
    #             ("ConfirmedPayment", "Payment Confirmed", "Your payment is confirmed.", "paid"),
    #             ("OrderProcess", "Order Processed", "We are preparing your order.", "processing"),
    #             ("OrderPlaced", "Order Fulfilled", "Your order has been fulfilled.", "fulfilled"),
    #             ("Cancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         ],
    #         "service": [
    #             ("ServiceConformed", "Reservation Service Confirmed", "Your Service is confirmed.", "confirmed"),
    #             ("ServiceCompleted", "Service Completed", "Thanks for attending.", "completed"),
    #             ("ServiceCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         ],
    #         "reservation": [
    #             ("reservationConfirmed", "Reservation Booking Confirmed", "Reservation confirmed.", "confirmed"),
    #             ("reservationCompleted", "Experience Completed", "Thanks for visiting.", "completed"),
    #             ("reservationCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         ],
    #         "event": [
    #             ("EventTicketConfirmed", "Reservation Ticket Confirmed", "Your ticket is confirmed.", "confirmed"),
    #             ("EventTicketCompleted", "Event Completed", "Thanks for attending.", "completed"),
    #             ("EventTicketCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         ],
    #         "experience": [
    #             ("ExperienceBookingConfirmed", "Reservation Booking Confirmed", "Your experience is confirmed.", "confirmed"),
    #             ("ExperienceBookingReminder", "Pre-Experience Reminder", "Get ready for your experience.", "Reminder"),
    #             ("ExperienceBookingCompleted", "Experience Completed", "Thank you for joining!", "completed"),
    #             ("ExperienceBookingConfirmedCancelled", "Order Cancelled", "Your order has been Cancelled.", "Cancelled"),
    #         ]
    #     }

    #     category_steps = step_templates.get(category_type.lower(), [])
    #     cancel_index = next((i for i, step in enumerate(category_steps) if step[3].lower() == "cancelled"), None)
    #     current_index = next((i for i, step in enumerate(category_steps) if step[3].lower() == current_status.lower()), -1)

    #     if current_status.lower() == "cancelled" and cancel_index is not None:
    #         steps_to_build = category_steps[:cancel_index] + [category_steps[cancel_index]]
    #     else:
    #         steps_to_build = category_steps
    #     for icon_key, title, desc, key in steps_to_build:
    #         steps.append(build_step(icon_key, title, desc, key))
    #     step_count = len(steps)
    #     tracking_step_count = sum(1 for step in steps if step['active'])

    #     return {
    #         "tracking_steps": steps,
    #         "step_count": step_count,
    #         "tracking_step_count": tracking_step_count
    #     }


# category_steps = step_templates.get(category_type.lower(), [])
#         current_status_lower = current_status.lower()
#         is_cancelled = current_status_lower == "cancelled"

#         steps_to_build = []
#         steps = []

#         # Initialize tracking metadata
#         previous_step_count = 0
#         last_valid_status = ""

#         if isinstance(step_status_history, dict):
#             try:
#                 previous_step_count = int(step_status_history.get("tracking_step_count", 0))
#             except (ValueError, TypeError):
#                 previous_step_count = 0

#             last_valid_status = step_status_history.get("last_valid_status", "").lower()

#         # If the order is cancelled, keep all steps until last valid status and add cancelled
#         if is_cancelled:
#             # Determine how far to go in steps
#             reached_index = 0
#             if last_valid_status:
#                 reached_index = next(
#                     (i for i, (_, _, _, key) in enumerate(category_steps) if key.lower() == last_valid_status),
#                     0
#                 )
#             elif previous_step_count > 0:
#                 reached_index = previous_step_count - 1

#             # Get all steps up to reached_index
#             steps_to_build = category_steps[:reached_index + 1]

#             # Add "cancelled" step at the end if it's not already there
#             cancel_step = next((s for s in category_steps if s[3].lower() == "cancelled"), None)
#             if cancel_step and cancel_step not in steps_to_build:
#                 steps_to_build.append(cancel_step)
#         else:
#             # Normal case, just exclude "cancelled"
#             steps_to_build = [s for s in category_steps if s[3].lower() != "cancelled"]

#         # Build steps
#         for icon_key, title, desc, status_key in steps_to_build:
#             steps.append(build_step(icon_key, title, desc, status_key))

#         step_count = len(steps)

#         # Determine current step index
#         tracking_step_count = 1
#         for i, step in enumerate(steps):
#             if step["status"].lower() == current_status_lower:
#                 tracking_step_count = i + 1
#                 break

#         # Final result
#         return {
#             "tracking_steps": steps,
#             "step_count": step_count,
#             "tracking_step_count": tracking_step_count
#         }





class OrderTrackingViewNew(APIView):
    def get(self, request, order_id):
        try:
            order = get_object_or_404(Order, order_id=order_id)

            response_data = {
                "order_id": order.order_id,
                "order_type": order.order_type,
                "order_status": order.orderStatus,
                "total_price": float(order.total_price),
                "is_paid": order.is_paid,
                "created_at": order.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }

            steps = []
            step_definitions = {
                "OrderPlaced": {"image": "Images.OrderPlaced", "title": "Order Placed"},
                "ConfirmedPayment": {"image": "Images.ConfirmedPayment", "title": "Payment Confirmed"},
                "OrderProcess": {"image": "Images.OrderProcess", "title": "Order Processed"},
                "Shoppingbag": {"image": "Images.Shoppingbag", "title": "Ready to Pickup" if order.order_type == "Onsite" else "Out for Delivery"},
            }
            steps.append({
                **step_definitions["OrderPlaced"],
                "description": f"Order #{order.order_id} has been placed.",
                "time": order.created_at.strftime("%H:%M")
            })
            if order.orderStatus in ["paid", "processing"]:
                steps.append({
                    **step_definitions["ConfirmedPayment"],
                    "description": "Payment has been confirmed.",
                    "time": order.created_at.strftime("%H:%M")
                })
            if order.orderStatus == "processing":
                steps.append({
                    **step_definitions["OrderProcess"],
                    "description": "We are preparing your order." if order.order_type == "Onsite" else "Your order is being prepared for delivery.",
                    "time": order.created_at.strftime("%H:%M")
                })
            if order.orderStatus == "fulfilled":
                steps.append({
                    **step_definitions["Shoppingbag"],
                    "description": f"Order #{order.order_id} from {order.company.companyName}.",
                    "time": order.created_at.strftime("%H:%M")
                })
            room_booking = RoomBooking.objects.filter(product__in=order.cart_items.values_list('product', flat=True)).first()
            if room_booking:
                response_data['room_booking'] = {
                    "room_id": room_booking.room.room_id,
                    "room_type": room_booking.room.roomType,
                    "adults": room_booking.adults,
                    "total_price": float(room_booking.total_price),
                    "checkin_date": room_booking.checkin_date.strftime("%Y-%m-%d %H:%M:%S") if room_booking.checkin_date else None,
                    "checkout_date": room_booking.checkout_date.strftime("%Y-%m-%d %H:%M:%S") if room_booking.checkout_date else None,
                    "booking_status": room_booking.booking_status
                }
            event_booking = eventBooking.objects.filter(ticket_id__in=order.cart_items.values_list('product', flat=True)).first()
            if event_booking:
                response_data['event_booking'] = {
                    "ticket_id": event_booking.ticket_id.id,
                    "full_name": event_booking.full_name,
                    "email": event_booking.email,
                    "phone": event_booking.phone,
                    "booking_date": event_booking.booking_date.strftime("%Y-%m-%d") if event_booking.booking_date else None,
                    "booking_time": event_booking.booking_time.strftime("%H:%M") if event_booking.booking_time else None,
                    "number_of_people": event_booking.number_of_people,
                    "status": event_booking.status
                }

            response_data["tracking_steps"] = steps

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Order details fetched successfully",
                "data": response_data
            }, status=status.HTTP_200_OK)

        except Order.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Order not found"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"An error occurred: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CancelReasonsAPIView(APIView):
    def get(self, request):
        cancel_reasons = [
            {"reason": choice[0], "label": choice[1]} 
            for choice in Order.CANCEL_REASONS
        ]
        return Response({"cancel_reasons": cancel_reasons}, status=status.HTTP_200_OK)
 

class CancelOrderBookingsAPIView(APIView):
    """
    API to cancel an order or booking based on identifier (order_id or booking_id).
    Stores who cancelled the record in the `cancel_by` field.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, identifier):
        user = request.user
        cancel_reason = request.data.get("cancel_reasons")

        if not cancel_reason:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Cancel reason is required.",
                "data": None
            }, status=status.HTTP_200_OK)
        try:
            order = Order.objects.get(order_id=identifier, user=user)
            if order.orderStatus not in ["new order", "processing","confirmed","accepted","paid"]:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Order cannot be cancelled in '{order.orderStatus}' status.",
                    "data": None
                }, status=status.HTTP_200_OK)
            order.orderStatus = "cancelled"
            order.cancel_reasons = cancel_reason
            order.cancel_by = "user"
            order.save()
            return Response({
                "statusCode": 200,
                "status": True,
                "message": f"Order {order.order_id} cancelled successfully.",
                "data": {
                    "order_id": order.order_id,
                    "status": order.orderStatus,
                    "cancel_reason": order.cancel_reasons,
                    "cancel_by": order.cancel_by
                }
            }, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            pass
        try:
            booking = RoomBooking.objects.get(booking_id=identifier, user=user)
            if booking.booking_status not in ["pending", "confirmed"]:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Room booking cannot be cancelled in '{booking.booking_status}' status.",
                    "data": None
                }, status=status.HTTP_200_OK)
            booking.booking_status = "cancelled"
            booking.cancel_reason = cancel_reason
            booking.cancel_by = "user"
            booking.save()
            return Response({
                "statusCode": 200,
                "status": True,
                "message": f"Room booking {booking.booking_id} cancelled successfully.",
                "data": {
                    "booking_id": booking.booking_id,
                    "status": booking.booking_status,
                    "cancel_reason": booking.cancel_reason,
                    "cancel_by": booking.cancel_by
                }
            }, status=status.HTTP_200_OK)
        except RoomBooking.DoesNotExist:
            pass
        try:
            booking = eventBooking.objects.get(booking_id=identifier, user=user)
            if booking.status not in ["pending", "confirmed"]:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Event booking cannot be cancelled in '{booking.status}' status.",
                    "data": None
                }, status=status.HTTP_200_OK)
            booking.status = "cancelled"
            booking.cancel_reason = cancel_reason
            booking.cancel_by = "user"
            booking.save()
            return Response({
                "statusCode": 200,
                "status": True,
                "message": f"Event booking {booking.booking_id} cancelled successfully.",
                "data": {
                    "booking_id": booking.booking_id,
                    "status": booking.status,
                    "cancel_reason": booking.cancel_reason,
                    "cancel_by": booking.cancel_by
                }
            }, status=status.HTTP_200_OK)
        except eventBooking.DoesNotExist:
            pass
        try:
            booking = experienceBooking.objects.get(booking_id=identifier, user=user)
            if booking.status not in ["pending", "confirmed"]:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Experience booking cannot be cancelled in '{booking.status}' status.",
                    "data": None
                }, status=status.HTTP_200_OK)
            booking.status = "cancelled"
            booking.cancel_reason = cancel_reason
            booking.cancel_by = "user"
            booking.save()
            return Response({
                "statusCode": 200,
                "status": True,
                "message": f"Experience booking {booking.booking_id} cancelled successfully.",
                "data": {
                    "booking_id": booking.booking_id,
                    "status": booking.status,
                    "cancel_reason": booking.cancel_reason,
                    "cancel_by": booking.cancel_by
                }
            }, status=status.HTTP_200_OK)
        except experienceBooking.DoesNotExist:
            pass
        try:
            booking = slotBooking.objects.get(booking_id=identifier, user=user)
            if booking.status not in ["pending", "confirmed"]:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Slot booking cannot be cancelled in '{booking.status}' status.",
                    "data": None
                }, status=status.HTTP_200_OK)
            booking.status = "cancelled"
            booking.cancel_by = "user"
            booking.save()
            return Response({
                "statusCode": 200,
                "status": True,
                "message": f"Slot booking {booking.booking_id} cancelled successfully.",
                "data": {
                    "booking_id": booking.booking_id,
                    "status": booking.status,
                    "cancel_by": booking.cancel_by
                }
            }, status=status.HTTP_200_OK)
        except slotBooking.DoesNotExist:
            pass
        try:
            booking = aestheticsBooking.objects.get(booking_id=identifier, user=user)
            if booking.status not in ["pending", "confirmed"]:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Aesthetics booking cannot be cancelled in '{booking.status}' status.",
                    "data": None
                }, status=status.HTTP_200_OK)
            booking.status = "cancelled"
            booking.cancel_by = "user"
            booking.save()
            return Response({
                "statusCode": 200,
                "status": True,
                "message": f"Aesthetics booking {booking.booking_id} cancelled successfully.",
                "data": {
                    "booking_id": booking.booking_id,
                    "status": booking.status,
                    "cancel_by": booking.cancel_by
                }
            }, status=status.HTTP_200_OK)
        except aestheticsBooking.DoesNotExist:
            pass
        try:
            booking = relaxationBooking.objects.get(booking_id=identifier, user=user)
            if booking.status not in ["pending", "confirmed"]:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Relaxation booking cannot be cancelled in '{booking.status}' status.",
                    "data": None
                }, status=status.HTTP_200_OK)
            booking.status = "cancelled"
            booking.cancel_by = "user"
            booking.save()
            return Response({
                "statusCode": 200,
                "status": True,
                "message": f"Relaxation booking {booking.booking_id} cancelled successfully.",
                "data": {
                    "booking_id": booking.booking_id,
                    "status": booking.status,
                    "cancel_by": booking.cancel_by
                }
            }, status=status.HTTP_200_OK)
        except relaxationBooking.DoesNotExist:
            pass
        try:
            booking = artandcultureBooking.objects.get(booking_id=identifier, user=user)
            if booking.status not in ["pending", "confirmed"]:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Art & Culture booking cannot be cancelled in '{booking.status}' status.",
                    "data": None
                }, status=status.HTTP_200_OK)
            booking.status = "cancelled"
            booking.cancel_by = "user"
            booking.save()
            return Response({
                "statusCode": 200,
                "status": True,
                "message": f"Art & Culture booking {booking.booking_id} cancelled successfully.",
                "data": {
                    "booking_id": booking.booking_id,
                    "status": booking.status,
                    "cancel_by": booking.cancel_by
                }
            }, status=status.HTTP_200_OK)
        except artandcultureBooking.DoesNotExist:
            pass
        return Response({
            "statusCode": 404,
            "status": False,
            "message": "No matching order or booking found for cancellation.",
            "data": None
        }, status=status.HTTP_200_OK)


class OrderFeedBackAPIView(APIView):
    """
    API to submit feedback for orders or various bookings based on identifier.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, identifier):
        user = request.user
        feedback_text = request.data.get("comments")
        rating = request.data.get("rating")  # Optional, if you allow rating

        if not feedback_text:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Feedback text is required.",
                "data": None
            }, status=status.HTTP_200_OK)

        def handle_feedback(instance, id_field="booking_id"):
            instance.feedback = feedback_text
            instance.rating = rating if rating else None
            instance.feedback_by = user.username
            instance.save()
            return Response({
                "statusCode": 200,
                "status": True,
                "message": f"Feedback submitted successfully for {getattr(instance, id_field)}.",
                "data": {
                "order_id": getattr(instance, id_field),
                "comments": instance.feedback,
                "rating": instance.rating,
                "comments_by": instance.feedback_by
                }
            }, status=status.HTTP_200_OK)
       
        from ProfessionalUser.models import (Order, RoomBooking,
                                             aestheticsBooking,
                                             artandcultureBooking,
                                             eventBooking, experienceBooking,
                                             relaxationBooking, slotBooking)

        try:
            order = Order.objects.get(order_id=identifier, user=user)
            return handle_feedback(order, id_field="order_id")
        except Order.DoesNotExist:
            pass

        booking_models = [
            (RoomBooking, "booking_id"),
            (eventBooking, "booking_id"),
            (experienceBooking, "booking_id"),
            (slotBooking, "booking_id"),
            (aestheticsBooking, "booking_id"),
            (relaxationBooking, "booking_id"),
            (artandcultureBooking, "booking_id"),
        ]

        for model, id_field in booking_models:
            try:
                booking = model.objects.get(**{id_field: identifier, "user": user})
                return handle_feedback(booking, id_field=id_field)
            except model.DoesNotExist:
                continue

        return Response({
            "statusCode": 404,
            "status": False,
            "message": "No matching order or booking found for feedback.",
            "data": None
        }, status=status.HTTP_200_OK)



class LoyaltyPurchaseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        product_ids = request.data.get("product_ids")  # expecting a list of product ids
        company_id = request.data.get("company_id")
        card_id = request.data.get("card_id")
        order_type = request.data.get("order_type")

        if not all([product_ids, company_id, card_id, order_type]):
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Missing required fields."
            }, status=status.HTTP_200_OK)

        if not isinstance(product_ids, list) or len(product_ids) == 0:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "product_ids must be a non-empty list."
            }, status=status.HTTP_200_OK)

        try:
            company = CompanyDetails.objects.get(id=company_id)
        except CompanyDetails.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Company not found."
            }, status=status.HTTP_200_OK)

        try:
            loyalty = LoyaltyPoint.objects.get(user=request.user, company=company)
        except LoyaltyPoint.DoesNotExist:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "User has no loyalty points with this company."
            }, status=status.HTTP_200_OK)

        results = []
        total_points_needed = 0
        cards = {}
        for pid in product_ids:
            try:
                product = Product.objects.get(id=pid)
            except Product.DoesNotExist:
                results.append({
                    "product_id": pid,
                    "status": False,
                    "message": "Product not found."
                })
                continue

            card = LoyaltyCard.objects.filter(product=product, company=company).first()
            if not card:
                results.append({
                    "product_id": pid,
                    "status": False,
                    "message": "No loyalty card found for this product and company."
                })
                continue
            
            cards[pid] = (product, card)
            total_points_needed += card.threshold_point

        if total_points_needed == 0:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "No valid products found to redeem loyalty points."
            }, status=status.HTTP_200_OK)

        if loyalty.total_points < total_points_needed:
            return Response({
                "statusCode": 403,
                "status": False,
                "message": f"Not enough loyalty points. Required: {total_points_needed}, Available: {loyalty.total_points}"
            }, status=status.HTTP_403_FORBIDDEN)
        loyalty.total_points -= total_points_needed
        loyalty.save()
        for pid, (product, card) in cards.items():
            results.append({
                "product_id": product.id,
                "product_name": product.productname,
                "status": True,
                "message": "Product successfully purchased with loyalty points."
            })

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Loyalty points redeemed for products.",
            "results": results,
            "remaining_points": loyalty.total_points,
            "order_type": order_type
        }, status=status.HTTP_200_OK)
    


    
class StorePlayerIdView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            player_id = request.data.get("player_id")
            if not player_id or not isinstance(player_id, str):
                return Response(
                    {
                    "statusCode": 400,
                    "status": False,
                    "message": "Valid 'player_id' is required."
                    },status=status.HTTP_200_OK
                )

            user = request.user
            user.onesignal_player_id = player_id
            user.save()

            return Response(
                {
                    "statusCode": 200,
                    "status": True,
                    "message": "player_id saved successfully"},
                status=status.HTTP_200_OK
            )

        except DatabaseError as db_err:
            return Response(
                {
                    "statusCode": 500,
                    "status": False,
                    "message": "Database error: " + str(db_err)
                },status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {
                    "statusCode": 500,
                    "status": False,
                    "message": "An unexpected error occurred: " + str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
