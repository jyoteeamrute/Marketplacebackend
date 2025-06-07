from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.tokens import UntypedToken
from Admin import admin
from UserApp.models import Users  # Directly import your custom Users model
from asgiref.sync import sync_to_async
from .models import *
from django.db.models import Max
from ProfessionalUser.models import ProfessionalUser
import logging
from django.utils.timesince import timesince
from django.utils import timezone
from django.db.models import Q


logger = logging.getLogger(__name__)

def decode_token(token):
    try:
        access_token = UntypedToken(token)
        payload = access_token.payload

        logger.debug(f"Decoded payload: {payload}")

        user_id = payload.get("user_id")
        professional_id = payload.get("professional_id")
        admin_id = payload.get("admin_id")
        
        if user_id:
            print("---Utils.py----------user_id", user_id)
            return {"type": "users", "id": int(user_id)}
        elif professional_id:
            print("-----Utils.py--------professional_id", professional_id)
            return {"type": "professional", "id": int(professional_id)}
        elif admin_id:
            print("-----Utils.py--------admin_id", admin_id)
            return {"type": "admin", "id": int(admin_id)}
        else:
            raise ValueError("Token missing user_id or professional_id")

    except Exception as e:
        logger.error(f"Failed to decode token: {str(e)}")
        return None


@sync_to_async
def get_user_by_id(user_id):
    try:
        return Users.objects.get(id=user_id)  
    except Users.DoesNotExist:
        return None

def get_time_difference(created_at):
    if timezone.is_naive(created_at):
        created_at = timezone.make_aware(created_at)

    now = timezone.now()
    minutes = (now - created_at).total_seconds() // 60
    hours = minutes // 60
    days = hours // 24

    if minutes < 60:
        return f"{int(minutes)} min ago"
    elif hours < 24:
        return f"{int(hours)} hour{'s' if hours != 1 else ''} ago"
    else:
        return f"{int(days)} day{'s' if days != 1 else ''} ago"

@sync_to_async
def get_user_from_token(token):
    decoded = decode_token(token)
    if not decoded:
        return None

    user_id = decoded.get("id")
    user_type = decoded.get("type")

    try:
        if user_type == "user":
            return Users.objects.get(id=user_id)
        elif user_type == "professional":
            return ProfessionalUser.objects.get(id=user_id)
    except Exception:
        return None


def get_user_info(user_id, user_type):
    
    profile_image_url = None
    name = ""

    if user_type == 'users':
        print()
        try:
            from UserApp.models import Users
            user = Users.objects.get(id=user_id)
            name = f"{user.firstName} {user.lastName}".strip()
            if user.profileImage:
                profile_image_url = user.profileImage.url
        except Users.DoesNotExist:
            logger.error(f"Users with id {user_id} does not exist.")

    elif user_type == 'professional':
        try:
            print("\n \n \n \n \n")
            from ProfessionalUser.models import ProfessionalUser
            professional = ProfessionalUser.objects.select_related('company').get(id=user_id)
            name = professional.company.companyName 
            if professional.company:
                name = professional.company.companyName
                if professional.company.profilePhoto:
                    profile_image_url = professional.company.profilePhoto.url
                
        except ProfessionalUser.DoesNotExist:
            logger.error(f"ProfessionalUser with id {user_id} does not exist.")

        
    return {
        "id": user_id,
        "type": user_type,
        "name": name,
        "profile_image": profile_image_url
    }

   
@sync_to_async
def fetch_user_chats(user_type, user_id):
    user_instance = None
 
    if user_type == "users":
        try:
            user_instance = Users.objects.get(id=user_id)
        except Users.DoesNotExist:
            return []
        chat_ids = UserChat.objects.filter(user=user_instance).values_list("chat", flat=True)
 
    elif user_type == "professional":
        try:
            user_instance = ProfessionalUser.objects.get(id=user_id)
        except ProfessionalUser.DoesNotExist:
            return []
        chat_ids = UserChat.objects.filter(professional=user_instance).values_list("chat", flat=True)

 
    else:
        return []
 
    chats = Chat.objects.filter(id__in=chat_ids).filter(Q(name__isnull=True) | Q(name=""))  \
        .prefetch_related("messages", "users", "professional_user") \
        .annotate(latest_message_time=Max("messages__created_at")) \
        .order_by("-latest_message_time")

    result = []

    for chat in chats:
        last_msg = chat.messages.order_by("-created_at").first()
        
        if not last_msg:
            continue
        
        show_message = True
        if last_msg:
            if user_type == "users":
                is_hidden = ChatHistoryHide.objects.filter(user=user_instance, message=last_msg).exists()
            elif user_type == "professional":
                is_hidden = ChatHistoryHide.objects.filter(professional=user_instance, message=last_msg).exists()
            else:
                is_hidden = False
 
            if is_hidden:
                show_message = False
 
        # If not hidden and no real message content, skip
        if not is_hidden and not (last_msg.content or last_msg.image or last_msg.video):
            continue
 

        chat_participants = UserChat.objects.filter(chat=chat)
        print("---------------chat participants", chat_participants)
        participant = None
 
        for uc in chat_participants:
            # Skip current user instance based on actual object match
            if uc.user and (not isinstance(user_instance, Users) or uc.user.id != user_instance.id):
                participant = get_user_info(uc.user.id, "users")
                break
            elif uc.professional and (not isinstance(user_instance, ProfessionalUser) or uc.professional.id != user_instance.id):
                participant = get_user_info(uc.professional.id, "professional")
                break
            

 
        if not participant and chat.receiver_type and str(chat.receiver_id) != str(user_id):
            participant = get_user_info(chat.receiver_id, chat.receiver_type)
 
        
        if is_hidden:
            last_message_content = ""
            
        else:    
                if last_msg.image:
                    last_message_content = last_msg.image.url
                elif last_msg.video:
                    last_message_content = last_msg.video.url
                else:
                    last_message_content = last_msg.content
 
        result.append({
            "chat_id": chat.id,
            "last_message": last_message_content,
            "last_message_time": get_time_difference(last_msg.created_at) if last_msg else "",
            "participant_id": participant.get("id") if participant else None,
            "participant_type": participant.get("type") if participant else None,
            "participant_username": participant.get("name") if participant else None,
            "participant_profile_image": participant.get("profile_image") if participant else None,
        })
 
    return result
 
 
 