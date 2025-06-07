# from tkinter import N
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ChatApp.serializers import *
import logging
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from ChatApp.models import *
import os
from django.utils import timezone
from PIL import Image
import io
from django.core.files.base import ContentFile
import os
from moviepy.video.io.VideoFileClip import VideoFileClip
from django.core.files.base import ContentFile
import tempfile
import time
from urllib.parse import urlencode
from django.db.models import Q


logger = logging.getLogger(__name__)  


class ChatHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chat_id):
        chat = Chat.objects.filter(id=chat_id, userchat__user=request.user).first()
        if not chat:
            return Response({False: "Chat not found."}, status=404)

        messages = Message.objects.filter(chat=chat).order_by("-created_at")[:50]
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data, status=200)

def compress_image(image_file, quality=75):
    image = Image.open(image_file)
    image_format = image.format  # Preserve original format (e.g., PNG, JPEG)

    image_io = io.BytesIO()

    save_kwargs = {
        'optimize': True,
    }

    if image_format == 'JPEG':
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")  # JPEG doesn't support transparency
        save_kwargs['quality'] = quality
        save_kwargs['format'] = 'JPEG'
    else:
        # Keep original format (e.g., PNG)
        save_kwargs['format'] = image_format

    image.save(image_io, **save_kwargs)

    return ContentFile(image_io.getvalue(), name=f"compressed_{image_file.name}")


def compress_video( video_file):
        """Compress video without changing resolution."""
        try:
 
            # Save uploaded file temporarily
            input_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
            with open(input_path, 'wb') as f:
                f.write(video_file.read())
 
            # Load video
            clip = VideoFileClip(input_path)
 
            # Output path
            output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
 
            # Compress without changing resolution
            clip.write_videofile(
                output_path,
                bitrate="1000k",  # control compression rate
                codec="libx264",
                audio_codec="aac"
            )
 
            # Read and return compressed video as Django file
            with open(output_path, 'rb') as f:
                return ContentFile(f.read(), name=os.path.basename(video_file.name))
 
        except Exception as e:
            print(f"Compression error: {e}")
            return video_file



ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.avi', '.mkv', '.webm']


class UploadMediaAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            file = request.FILES.get('file')
            chat_id = request.data.get('chat_id')
            receiver_id = request.data.get('receiver_id')
            receiver_type = request.data.get('receiver_type')

            if not file or not chat_id:
                return Response({
                    'status': False,
                    'statusCode': 400,
                    'message': 'All fields (file, chat_id) are required.'
                }, status=status.HTTP_200_OK)

            try:
                chat = Chat.objects.get(id=chat_id)
                
            except Chat.DoesNotExist:
                return Response({
                    'status': False,
                    'statusCode': 404,
                    'message': 'Chat not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Get sender from token
            sender = request.user
            sender_type = self.get_user_type(sender)
            sender_id = sender.id

            # Validate file type
            ext = os.path.splitext(file.name)[1].lower()
            content_type = file.content_type
            image, video = None, None

            if content_type.startswith('image/') and ext in ALLOWED_IMAGE_EXTENSIONS:
                image = compress_image(file)
            elif content_type.startswith('video/') and ext in ALLOWED_VIDEO_EXTENSIONS:
                video = compress_video(file)
            else:
                return Response({
                    'status': False,
                    'statusCode': 400,
                    'message': f'Unsupported file type: {file.name}. Allowed image formats: {ALLOWED_IMAGE_EXTENSIONS}, video formats: {ALLOWED_VIDEO_EXTENSIONS}'
                }, status=status.HTTP_200_OK)

            # Create Message
            message = Message.objects.create(
                    chat=chat,
                    sender_content_type=ContentType.objects.get_for_model(sender),
                    sender_object_id=sender.id,
                    image=image,
                    video=video,
                    content=""
                )
   

            message_data = {
                'id': message.id,
                'sender_id': sender_id,
                'sender_type': sender_type,
                'receiver_id': receiver_id,
                'receiver_type': receiver_type,
                'content': '',
                'image': message.image.url if message.image else None,
                'video': message.video.url if message.video else None,
                'message_type': 'image' if message.image else 'video',
                'created_at': self.get_time_difference(message.created_at)
            }

            # WebSocket push
            group_name = chat.name if chat.is_group else f"chat_{chat.id}"
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'chat_message',
                    'message': message_data
                }
            )

            return Response({
                'status': True,
                'statusCode': 200,
                'message': 'Media uploaded successfully.',
                'data': message_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error in UploadMediaAPIView: {str(e)}")
            return Response({
                'status': False,
                'statusCode': 500,
                'message': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_user_type(self, user):
        if hasattr(user, 'professionaluser'):
            return 'professional'
        elif hasattr(user, 'adminuser'):
            return 'admin'
        return 'user'
    
    def get_time_difference(self, created_at):
        delta = timezone.now() - created_at
        minutes = int(delta.total_seconds() // 60)
        if minutes < 60:
            return f"{minutes} min ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hours ago"
        days = hours // 24
        return f"{days} days ago"
    

class ShareReelAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            reel_id = request.data.get('reel_id')
            receiver_user_ids = request.data.get('receiver_user_ids', [])

            if not reel_id or not receiver_user_ids:
                return Response({
                    'status': False,
                    'statusCode': 400,
                    'message': 'Both reel_id and receiver_user_ids are required.'
                }, status=status.HTTP_200_OK)
            
            try:
                reel = StoreReel.objects.get(id=reel_id)
            except StoreReel.DoesNotExist:
                return Response({
                    'status': False,
                    'statusCode': 404,
                    'message': 'Reel not found.'
                }, status=status.HTTP_200_OK)
            
            sender = request.user
            sender_type = self.get_user_type(sender)
            responses = []

            for receiver_id in receiver_user_ids:
                try:
                    receiver = Users.objects.get(id=receiver_id)
                except Users.DoesNotExist:
                    continue  

                chat = Chat.objects.filter(
                    is_group=False,
                    users=sender
                ).filter(users=receiver).distinct().first()

                if not chat:
                    chat = Chat.objects.create(is_group=False)
                    chat.users.add(sender, receiver)

                # Create and send message
                message = Message.objects.create(
                    chat=chat,
                    sender_content_type=ContentType.objects.get_for_model(sender),
                    sender_object_id=sender.id,
                    content="",
                    reels=reel
                )
                message_data = {
                    'id': message.id,
                    'sender_id': sender.id,
                    'sender_type': sender_type,
                    'receiver_id': receiver.id,
                    'content': '',
                    'reel': {
                        'id': reel.id,
                        'title': reel.title,
                        'video_url': reel.video.url if reel.video else None,
                    },
                    'message_type': 'reel',
                    'created_at': self.get_time_difference(message.created_at)
                }
                group_name = chat.name if chat.is_group else f"chat_{chat.id}"
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'chat_message',
                        'message': message_data
                    }
                )

                responses.append(message_data)

            return Response({
                'status': True,
                'statusCode': 200,
                'message': 'Reel shared successfully.',
                'data': responses
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error in ShareReelAPIView: {str(e)}")
            return Response({
                'status': False,
                'statusCode': 500,
                'message': f'Internal server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_user_type(self, user):
        if hasattr(user, 'professional_user'):
            return 'professional'
        elif hasattr(user, 'adminuser'):
            return 'admin'
        return 'user'

    def get_time_difference(self, created_at):
        delta = timezone.now() - created_at
        minutes = int(delta.total_seconds() // 60)
        if minutes < 60:
            return f"{minutes} min ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hours ago"
        days = hours // 24
        return f"{days} days ago"



            

class GroupChatMessageAPIView(APIView):
    
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            chat_id = request.query_params.get("chat_id")
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 10))

            if not chat_id:
                return Response({
                    "status": False,
                    "statusCode": 400,
                    "message": "chat_id is required."
                }, status=status.HTTP_200_OK)

            try:
                chat = Chat.objects.get(id=chat_id)
            except Chat.DoesNotExist:
                return Response({
                    "status": False,
                    "statusCode": 404,
                    "message": "Group Chat not found."
                }, status=status.HTTP_200_OK)

            offset = (page - 1) * page_size

            all_messages = Message.objects.filter(chat_id=chat_id).order_by("-created_at")

            # Hide logic (if user/professional has hidden messages)
            if isinstance(request.user, Users):
                hidden_msgs = ChatHistoryHide.objects.filter(
                    user=request.user, message__in=all_messages
                ).values_list("message_id", flat=True)
            elif isinstance(request.user, ProfessionalUser):
                hidden_msgs = ChatHistoryHide.objects.filter(
                    professional=request.user, message__in=all_messages
                ).values_list("message_id", flat=True)
            elif isinstance(request.user, AdminUser):
                hidden_msgs = ChatHistoryHide.objects.filter(
                    admin=request.user, message__in=all_messages
                ).values_list("message_id", flat=True)
            else:
                hidden_msgs = []

            visible_messages = all_messages.exclude(id__in=hidden_msgs)
            total_messages = visible_messages.count()
            messages = visible_messages[offset:offset + page_size]
            has_more = offset + page_size < total_messages

            
            user_chats = UserChat.objects.filter(chat=chat)

            participants = []

            for uc in user_chats:
                if uc.user:
                    participants.append({
                        "id": uc.user.id,
                        "type": "user"
                    })
                elif uc.professional:
                    participants.append({
                        "id": uc.professional.id,
                        "type": "professional"
                    })
                elif uc.admin:
                    participants.append({
                        "id": uc.admin.id,
                        "type": "admin"
                    })
            
            def get_time_diff(created_at):
                now = timezone.now()
                diff_minutes = (now - created_at).total_seconds() // 60
                if diff_minutes < 1:
                    return "0 min ago"
                elif diff_minutes < 60:
                    return f"{int(diff_minutes)} min ago"
                elif diff_minutes < 1440:
                    return f"{int(diff_minutes // 60)} hours ago"
                else:
                    return f"{int(diff_minutes // 1440)} days ago"

            chat_history = []
            for msg in messages:
                sender = msg.sender
                sender_id = sender.id if sender else None
                
                if isinstance(sender, Users):
                    sender_type = "user"
                elif isinstance(sender, ProfessionalUser):
                    sender_type = "professional"
                elif isinstance(sender, AdminUser):
                    sender_type = "admin"
                else:
                    sender_type = "unknown"

                chat_history.append({
                    "message": msg.content,
                    "sender_id": sender_id,
                    "sender_type": sender_type,
                    "chat_id": chat.id,
                    "image": msg.image.url if msg.image else None,
                    "video": msg.video.url if msg.video else None,
                    "message_type": "image" if msg.image else "video" if msg.video else "message",
                    "created_at": get_time_diff(msg.created_at)
                })

            if has_more:
                query_params = request.query_params.dict()
                query_params["page"] = page + 1
                next_page_url = f"{request.build_absolute_uri(request.path)}?{urlencode(query_params)}"
            else:
                next_page_url = None

            previous_page_url = None
            if page > 1:
                query_params["page"] = page - 1
                previous_page_url = f"{request.build_absolute_uri(request.path)}?{urlencode(query_params)}"

            return Response({
                "status": True,
                "statusCode": 200,
                "message": "Group chat history retrieved successfully.",
                "chat_id": chat.id,
                "group_name": chat.name,
                "participants": participants,
                "page": page,
                "next_page": next_page_url,
                "previous_page": previous_page_url,
                "page_size": page_size,
                "has_more": has_more,
                "chat_history": list(reversed(chat_history))  # oldest first
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"GroupChatMessageAPIView error: {str(e)}", exc_info=True)
            return Response({
                "status": False,
                "statusCode": 500,
                "message": f"Internal server error: {str(e)}",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
       

class ToggleBlockUserByChatIDAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        chat_id = request.query_params.get("chat_id")
        if not chat_id:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "chat_id is required.",
                "is_blocked": None
            }, status=status.HTTP_200_OK)

        try:
            chat = Chat.objects.get(id=chat_id)
            print(f"======================{ chat.__dict__ }==============================")
            current_user = request.user
            print(f"****************{ current_user}**********************")
            # Get all participants
            user_chats = chat.userchat_set.all()
            print(f"***==============*************{ user_chats}*****==============*****************")
            opponent_user = None
            opponent_type = None

            for uc in user_chats:
                if uc.user and uc.user.id != current_user.id:
                    opponent_user = uc.user
                    opponent_type = "user"
                elif uc.professional and uc.professional.id != current_user.id:
                    opponent_user = uc.professional
                    opponent_type = "professional"
                elif uc.admin and uc.admin.id != current_user.id:
                    opponent_user = uc.admin
                    opponent_type = "admin"

            if not opponent_user:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "No opponent user found.",
                    "is_blocked": None
                }, status=status.HTTP_200_OK)

            # Prepare filter based on user types
            block_filter = {}

            if isinstance(current_user, Users):
                block_filter["blocked_by"] = current_user
            elif isinstance(current_user, ProfessionalUser):
                block_filter["blocked_by_professional"] = current_user
            elif isinstance(current_user, AdminUser):
                block_filter["blocked_by_admin"] = current_user
            else:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Unsupported current user type.",
                    "is_blocked": None
                }, status=status.HTTP_200_OK)

            # Set blocked_user based on opponent type
            if opponent_type == "user":
                block_filter["blocked_user"] = opponent_user
            elif opponent_type == "professional":
                block_filter["blocked_user_professional"] = opponent_user
            elif opponent_type == "admin":
                block_filter["blocked_user_admin"] = opponent_user
            else:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Unsupported opponent user type.",
                    "is_blocked": None
                }, status=status.HTTP_200_OK)

            # Toggle block
            existing_block = BlockedUser.objects.filter(**block_filter)
            if existing_block.exists():
                existing_block.delete()
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": f"User ID {opponent_user.id} unblocked successfully.",
                    "is_blocked": False
                }, status=status.HTTP_200_OK)
            else:
                BlockedUser.objects.create(**block_filter)
                return Response({
                    "statusCode": 200,
                    "status": True,
                    "message": f"User ID {opponent_user.id} blocked successfully.",
                    "is_blocked": True
                }, status=status.HTTP_200_OK)

        except Chat.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Chat not found.",
                "is_blocked": None
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"ToggleBlockUserByChatIDAPIView error: {str(e)}", exc_info=True)
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"Internal server error: {str(e)}",
                "is_blocked": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReportUserByChatIDAPIView(APIView): 
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        chat_id = request.query_params.get("chat_id")
        reason = request.data.get("reason", "").strip()

        if not chat_id:
            return Response({
                "status": False,
                "statusCode": 400,
                "message": "chat_id is required.",
                "is_reported": None,
                "report_reason": None
            }, status=status.HTTP_200_OK)

        if not reason:
            return Response({
                "status": False,
                "statusCode": 400,
                "message": "reason is required.",
                "is_reported": None,
                "report_reason": None
            }, status=status.HTTP_200_OK)

        try:
            chat = Chat.objects.get(id=chat_id)
            current_user = request.user

            # Fetch all UserChat participants
            participants = chat.userchat_set.all()

            opponent_user = None
            opponent_type = None

            for participant in participants:
                if isinstance(current_user, Users) and participant.user and participant.user != current_user:
                    opponent_user = participant.user
                    opponent_type = "user"
                    break
                elif isinstance(current_user, Users) and participant.professional:
                    opponent_user = participant.professional
                    opponent_type = "professional"
                    break
                elif isinstance(current_user, ProfessionalUser) and participant.user:
                    opponent_user = participant.user
                    opponent_type = "user"
                    break
                elif isinstance(current_user, ProfessionalUser) and participant.professional and participant.professional != current_user:
                    opponent_user = participant.professional
                    opponent_type = "professional"
                    break
                elif isinstance(current_user, Users) and participant.admin:
                    opponent_user = participant.admin
                    opponent_type = "admin"
                    break
                elif isinstance(current_user, AdminUser) and participant.user:
                    opponent_user = participant.user
                    opponent_type = "user"
                    break
                elif isinstance(current_user, AdminUser) and participant.professional:
                    opponent_user = participant.professional
                    opponent_type = "professional"
                    break

            if not opponent_user:
                return Response({
                    "status": False,
                    "statusCode": 400,
                    "message": "No opponent user found.",
                    "is_reported": None,
                    "report_reason": None
                }, status=status.HTTP_200_OK)

            # Prepare report filter and data
            report_data = {"reason": reason}
            report_filter = {}

            if isinstance(current_user, Users):
                report_data["report_by_user"] = current_user
                if opponent_type == "user":
                    report_data["reported_user"] = opponent_user
                    report_filter = {
                        "report_by_user": current_user,
                        "reported_user": opponent_user
                    }
                elif opponent_type == "professional":
                    report_data["reported_professional"] = opponent_user
                    report_filter = {
                        "report_by_user": current_user,
                        "reported_professional": opponent_user
                    }
                elif opponent_type == "admin":
                    report_data["reported_admin"] = opponent_user
                    report_filter = {
                        "report_by_user": current_user,
                        "reported_admin": opponent_user
                    }

            elif isinstance(current_user, ProfessionalUser):
                report_data["report_by_professional"] = current_user
                if opponent_type == "user":
                    report_data["reported_user"] = opponent_user
                    report_filter = {
                        "report_by_professional": current_user,
                        "reported_user": opponent_user
                    }
                elif opponent_type == "admin":
                    report_data["reported_admin"] = opponent_user
                    report_filter = {
                        "report_by_professional": current_user,
                        "reported_admin": opponent_user
                    }

            elif isinstance(current_user, AdminUser):
                report_data["report_by_admin"] = current_user
                if opponent_type == "user":
                    report_data["reported_user"] = opponent_user
                    report_filter = {
                        "report_by_admin": current_user,
                        "reported_user": opponent_user
                    }
                elif opponent_type == "professional":
                    report_data["reported_professional"] = opponent_user
                    report_filter = {
                        "report_by_admin": current_user,
                        "reported_professional": opponent_user
                    }

            else:
                return Response({
                    "status": False,
                    "statusCode": 400,
                    "message": "Unsupported reporting combination.",
                    "is_reported": None,
                    "report_reason": None
                }, status=status.HTTP_200_OK)

            # Check if already reported
            existing_report = ReportedUser.objects.filter(**report_filter).first()
            if existing_report:
                return Response({
                    "status": True,
                    "statusCode": 200,
                    "message": "You have already reported this user.",
                    "is_reported": True,
                    "report_reason": existing_report.reason
                }, status=status.HTTP_200_OK)

            ReportedUser.objects.create(**report_data)

            return Response({
                "status": True,
                "statusCode": 200,
                "message": f"User ID {opponent_user.id} reported successfully.",
                "is_reported": True,
                "report_reason": reason
            }, status=status.HTTP_200_OK)

        except Chat.DoesNotExist:
            return Response({
                "status": False,
                "statusCode": 404,
                "message": "Chat not found.",
                "is_reported": None,
                "report_reason": None
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"ReportUserByChatIDAPIView error: {str(e)}", exc_info=True)
            return Response({
                "status": False,
                "statusCode": 500,
                "message": f"Internal error: {str(e)}",
                "is_reported": None,
                "report_reason": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    

class ClearChatAPIView(APIView):
    permission_classes = [IsAuthenticated]        
    
    def post(self, request):
        chat_id = request.query_params.get("chat_id")
        if not chat_id:
            return Response({
                "status": False,
                "statusCode": 400,
                "message": "chat_id is required."
            }, status=status.HTTP_200_OK)
        try:
            chat = Chat.objects.get(id=chat_id)
            user = request.user

            is_user = isinstance(user, Users)
            is_pro = isinstance(user, ProfessionalUser)

            if not is_user and not is_pro:
                return Response({
                    "status": False,
                    "statusCode": 400,
                    "message": "Invalid user type"
                }, status=status.HTTP_200_OK)

            if is_user:
                in_chat = UserChat.objects.filter(chat=chat, user=user).exists()
            else:
                in_chat = UserChat.objects.filter(chat=chat, professional=user).exists()

            if not in_chat:
                return Response({
                    "status": False,
                    "statusCode": 403,
                    "message": "You are not a participant in this chat."
                }, status=status.HTTP_403_FORBIDDEN)

            messages = Message.objects.filter(chat=chat)
            message_ids = messages.values_list("id", flat=True)

            if is_user:
                existing_ids = set(ChatHistoryHide.objects.filter(user=user, message_id__in=message_ids).values_list("message_id", flat=True))
                hidden_list = [ChatHistoryHide(user=user, message=msg) for msg in messages if msg.id not in existing_ids]
            else:
                existing_ids = set(ChatHistoryHide.objects.filter(professional=user, message_id__in=message_ids).values_list("message_id", flat=True))
                hidden_list = [ChatHistoryHide(professional=user, message=msg) for msg in messages if msg.id not in existing_ids]

            ChatHistoryHide.objects.bulk_create(hidden_list)

            return Response({
                "status": True,
                "statusCode": 200,
                "message": "Chat cleared for current user only"
            }, status=status.HTTP_200_OK)

        except Chat.DoesNotExist:
            return Response({
                "status": False,
                "statusCode": 404,
                "message": "Chat not found"
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"ClearChatAPIView error: {str(e)}", exc_info=True)
            return Response({
                "status": False,
                "statusCode": 500,
                "message": f"Internal server error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class NotificationsListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            user_content_type = ContentType.objects.get_for_model(user)
            notifications = ChatNotifications.objects.filter(
                receiver_content_type=user_content_type,
                receiver_object_id=user.id
            ).order_by('-created_at')

            if not notifications.exists():
                return Response({
                    "status": True,
                    "statusCode": 200,
                    "message": "No notifications found.",
                    "data": []
                }, status=status.HTTP_200_OK)

            serializer = ChatNotificationsSerializer(notifications, many=True)
            return Response({
                "status": True,
                "statusCode": 200,
                "message": "Notifications fetched successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"NotificationsListAPIView error: {str(e)}", exc_info=True)
            return Response({
                "status": False,
                "statusCode": 400,
                "message": "Failed to fetch notifications.",
                "error": str(e)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"NotificationsListAPIView error: {str(e)}", exc_info=True)
            return Response({
                "status": False,
                "statusCode": 500,
                "message": f"Internal server error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
 
 
class AddProfessionalToChatAPIView(APIView):
    
    def post(self, request):
        
        professional_id = request.query_params.get("professional_id")
        chat_id = request.query_params.get("chat_id")

        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            return Response({
                "status": False,
                "statuCode": 404,
                "message": "Chat not found"}, status=status.HTTP_200_OK)

        if not isinstance(request.user, AdminUser):
            return Response({
                "status": False,
                "statuCode": 403,
                "message": "Only admin can add professionals"
                }, status=status.HTTP_200_OK)

        try:
            professional = ProfessionalUser.objects.get(id=professional_id)
        except ProfessionalUser.DoesNotExist:
            return Response({
                "status": False,
                "statuCode": 404,
                "message": "Professional not found"}, status=status.HTTP_200_OK)

        # Check if professional is already in chat
        if UserChat.objects.filter(chat=chat, professional=professional).exists():
            return Response({
                "status": False,
                "statusCode": 400,
                "message": "Professional already in chat"
            }, status=status.HTTP_200_OK)

        # Add the professional to the chat
        UserChat.objects.create(chat=chat, professional=professional)

        return Response({
            "status": True,
            "statusCode": 200,
            "message": "Professional added to chat"
        }, status=status.HTTP_200_OK)           
        

     
from ChatApp.consumers import FlexibleChatConsumer       
from django.urls import reverse

class ShareProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            receiver_id = request.data.get("receiver_id")
            profile_id = request.data.get("profile_id")
            profile_type = request.data.get("profile_type", "users")

            if not receiver_id or not profile_id:
                return Response({
                    "status_code": 400,
                    "status_message": "receiver_id and profile_id are required."
                }, status=status.HTTP_400_BAD_REQUEST)

            sender = request.user
            print("sender:", sender)
            if not isinstance(sender, Users):
                return Response({
                    "status_code": 403,
                    "status_message": "Only users can share profiles."
                }, status=status.HTTP_403_FORBIDDEN)

            try:
                receiver = Users.objects.get(id=receiver_id)
            except Users.DoesNotExist:
                return Response({
                    "status_code": 404,
                    "status_message": "Receiver not found."
                }, status=status.HTTP_404_NOT_FOUND)

            # Fetch profile to be shared
            if profile_type == "users":
                try:
                    shared_profile = Users.objects.get(id=profile_id)
                    url_name = "public-user-profile"
                    
                    url_args = [shared_profile.id, shared_profile.username]
                except Users.DoesNotExist:
                    return Response({
                        "status_code": 404,
                        "status_message": "User profile to share not found."
                    }, status=status.HTTP_404_NOT_FOUND)
            elif profile_type == "professional":
                try:
                    shared_profile = ProfessionalUser.objects.get(id=profile_id)
                    url_name = "public-professional-profile"
                    url_args = [shared_profile.id, shared_profile.username]
                except ProfessionalUser.DoesNotExist:
                    return Response({
                        "status_code": 404,
                        "status_message": "Professional profile to share not found."
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({
                    "status_code": 400,
                    "status_message": "Invalid profile_type. Must be 'users' or 'professional'."
                }, status=status.HTTP_400_BAD_REQUEST)

            # Use chat consumer logic
            consumer = FlexibleChatConsumer(scope={"user": sender})
            consumer.user = sender
            consumer.user_type = "users"
            consumer.receiver_type = "users"
            consumer.receiver_id = int(receiver_id)

            chat = async_to_sync(consumer.get_or_create_chat)()
            profile_path = reverse(url_name, args=url_args)
            full_url = request.build_absolute_uri(profile_path)
            
            # Construct message content
            sender_ct = ContentType.objects.get_for_model(sender)

            # Save message with shared profile
            message = Message.objects.create(
                chat=chat,
                sender_content_type=sender_ct,
                sender_object_id=sender.id,
                content=f"Shared a profile link: {full_url}",
            )

            return Response({
                "status_code": 200,
                "status_message": "Profile shared successfully.",
                "chat_id": chat.id,
                "message_id": message.id
            }, status=status.HTTP_200_OK)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                "status_code": 500,
                "status_message": "Internal server error.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        