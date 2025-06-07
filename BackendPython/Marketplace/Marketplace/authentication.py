from venv import logger
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
import logging
logger = logging.getLogger(__name__)
from Admin.models import AdminUser
from ProfessionalUser.models import ProfessionalUser
from UserApp.models import Users

class CustomJWTAuthentication(JWTAuthentication):
    
    def get_user(self, validated_token):
        try:
            user_id = validated_token.get("user_id")
            email = validated_token.get("email")
            print("777777777777777")
            user_type = validated_token.get("user_type")  # Get the user_type from token
            print(user_type,"user_type;;")
            logger.info(f"user_type::{user_type}")

            if not user_id and not email:
                raise AuthenticationFailed("Invalid token: No user_id or email found")

            # Determine which model to use based on user_type
            if user_type.lower() == "professional_user":
                if email:
                    user = ProfessionalUser.objects.filter(email=email).first()
                elif user_id:
                    user = ProfessionalUser.objects.filter(id=user_id).first()
            elif user_type.lower() == "users" or user_type.lower() == "user":
                if email:
                    user = Users.objects.filter(email=email).first()
                elif user_id:
                    user = Users.objects.filter(id=user_id).first()
            elif user_type.lower() == "admin":
                logger.info(f"admin user")
                if email:
                    user = AdminUser.objects.filter(email=email).first()
                elif user_id:
                    user = AdminUser.objects.filter(id=user_id).first()
            else:
                raise AuthenticationFailed("Invalid user type in token")

            if not user:
                raise AuthenticationFailed("User not found")

            return user

        except Exception as e:
            raise AuthenticationFailed(f"Authentication error: {str(e)}")
        

        
 
# class CuddstomJWTAuthentication(JWTAuthentication):
    
#     def get_user(self, validated_token):
#         try:
#             user_id = validated_token.get("user_id")
#             email = validated_token.get("email")
 
#             if not user_id and not email:
#                 raise AuthenticationFailed("Invalid token: No user_id or email found")
 
#             # Try to find the user in ProfessionalUser first
#             if email:
#                 user = ProfessionalUser.objects.filter(email=email).first()
#                 if user:
#                     return user
 
#             # If not found in ProfessionalUser, check in Users
#             if user_id:
#                 user = Users.objects.filter(id=user_id).first()
#                 if user:
#                     return user
                
#             if email:
#                 user = AdminUser.objects.filter(email=email).first()
#                 if user:
#                     return user
 
#             raise AuthenticationFailed("User not found in both ProfessionalUser and UserApp")
 
#         except Exception as e:
#             raise AuthenticationFailed(f"Authentication error: {str(e)}")
 
 

#-----------------------------------------------------------------------





# ====================================================================================
        
from django.contrib.auth.hashers import check_password
from django.utils.timezone import now

from UserApp.models import Users

# def authenticate_user(email, password):

#     print(email, password)
    
#     if "@" not in email:
#         return {"message": "Enter a valid email and password are required"}

#     try:
#         user = Users.objects.get(email=email)

#         if check_password(password, user.password):
#             print("Password matched, updating last login...")
#             user.last_login = now()
#             user.save(update_fields=['last_login'])
#             return user

#         return {"message": "Invalid email or password"}

#     except Users.DoesNotExist:
#         return {"message": "User not found"}



def authenticate_user(identifier, password):
    
    print(identifier, password)

    try:
        # Check if identifier is an email or username
        if "@" in identifier:
            user = Users.objects.get(email=identifier)
        else:
            user = Users.objects.get(username=identifier)

        # Check password
        if check_password(password, user.password):
            print("Password matched, updating last login...")
            user.last_login = now()
            user.save(update_fields=['last_login'])
            return user  # Return the authenticated user

        return {"message": "Invalid username/email or password"}

    except Users.DoesNotExist:
        return {"message": "User not found"}
