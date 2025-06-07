import json
import logging
from operator import is_
import re
from channels.layers import get_channel_layer
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model
from ProfessionalUser.signals import get_player_ids_by_professional_id
from UserApp.utils import get_player_ids_by_user_id
import uuid
from asgiref.sync import async_to_sync
import base64
from .models import *
from ProfessionalUser.models import ProfessionalUser
from django.contrib.contenttypes.models import ContentType
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from .utils import get_user_from_token
from ProfessionalUser.models import Friendship, ProfessionalUser
from ChatApp.models import ProUserChat, ProChat, ProMessage
from django.contrib.contenttypes.models import ContentType
from ChatApp.utils import get_user_info, fetch_user_chats
from django.db.models import Q
from .utils import decode_token
from urllib.parse import parse_qs
import json
import logging
from django.utils.timesince import timesince
from django.utils import timezone
import traceback

logger = logging.getLogger(__name__)
User = get_user_model()





class ChatGroupListConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.query_params = parse_qs(self.scope["query_string"].decode())
        self.user_type = self.query_params.get("type", [None])[0]
        self.user_id = self.query_params.get("id", [None])[0]

        if not self.user_type or not self.user_id:
            await self.close()
            return

        self.user_group_name = f"group_list_{self.user_type}_{self.user_id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

        await self.send_chat_list()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def send_chat_list(self):
        chats = await self.get_user_chats(self.user_type, self.user_id)
        await self.send(text_data=json.dumps({"type": "chat_list", "chats": chats}))

    async def send_chat_list(self):
        chats = await fetch_user_chats(self.user_type, self.user_id)
        await self.send_json({
            "type": "chat_group_list",
            "chats": chats,
        })
        
    async def chat_list_update(self, event):
        
        chat = event.get("chat")
        if chat:
            await self.send_json({
                "type": "chat_list_update",
                "chat": chat,
            })
            
        
async def send_chat_list_update(user_type, user_id, chat_id):
    chats = await fetch_user_chats(user_type, user_id)  # now awaited correctly
    updated_chat = next((c for c in chats if c["chat_id"] == chat_id), None)
    if updated_chat:
        channel_layer = get_channel_layer()
        group_name = f"group_list_{user_type}_{user_id}"
        
        await channel_layer.group_send(
            group_name,
            {
                "type": "chat_list_update",  
                "chat": updated_chat,
            }
        )
    else:
        print(f"[send_chat_list_update] No updated chat found with id {chat_id} for {user_type}:{user_id}")
            
class FlexibleChatConsumer(AsyncWebsocketConsumer):
    
    
    
    def decode_base64_file(data):
        try:
            format, imgstr = data.split(';base64,')  
            ext = format.split('/')[-1]  
            filename = f"{uuid.uuid4()}.{ext}"  
            return ContentFile(base64.b64decode(imgstr), name=filename)
        except Exception as e:
            print("Base64 decode error:", e)
            return None

    @sync_to_async
    def get_or_create_chat(self):
        # Determine receiver model
        receiver_model = Users if self.receiver_type == "users" else ProfessionalUser
        receiver = receiver_model.objects.filter(id=self.receiver_id).first()
        if not receiver:
            raise Exception("Receiver not found")

        sender_type = "users" if isinstance(self.user, Users) else "professional"
        sender_id = self.user.id

        receiver_type = "professional" if receiver_model == ProfessionalUser else "users"
        receiver_id = receiver.id

        user_chats = Chat.objects.filter(
            Q(userchat__user_id=self.user.id) | Q(userchat__professional_id=self.user.id)
        ).distinct()

        # Find existing chat between sender and receiver
        for chat in user_chats:
            participants = set()
            for uc in chat.userchat_set.all():
                if uc.user:
                    participants.add(("users", uc.user.id))
                elif uc.professional:
                    participants.add(("professional", uc.professional.id))

            expected = {(sender_type, sender_id), (receiver_type, receiver_id)}
            if participants == expected:
                return chat

        # Create new chat
        chat = Chat.objects.create(receiver_type=self.receiver_type, receiver_id=receiver.id)
        entries = []
        if isinstance(self.user, Users):
            entries.append(UserChat(user=self.user, chat=chat))
        else:
            entries.append(UserChat(professional=self.user, chat=chat))

        if isinstance(receiver, Users):
            entries.append(UserChat(user=receiver, chat=chat))
        else:
            entries.append(UserChat(professional=receiver, chat=chat))

        UserChat.objects.bulk_create(entries)
        return chat

    @sync_to_async
    def get_chat_history(self,page=1, page_size=20):
        messages = Message.objects.filter(chat_id=self.chat.id).order_by("created_at").select_related('sender_content_type')
        
        if isinstance(self.user, Users):
            hidden_messages = ChatHistoryHide.objects.filter(user=self.user).values_list('message_id', flat=True)
        else:
            hidden_messages = ChatHistoryHide.objects.filter(professional=self.user).values_list('message_id', flat=True)
        
        messages = messages.exclude(id__in=hidden_messages)
        
        participants = list(self.chat.userchat_set.values_list("user_id", "professional_id"))
        
        paginator = Paginator(messages, page_size)
        page_obj = paginator.get_page(page)
        
        participants = list(self.chat.userchat_set.all())
        participant_ids = [uc.user.id if uc.user else uc.professional.id for uc in participants if uc.user or uc.professional]

        opponent = None
        opponent_id = None
        opponent_type = None

        for uc in participants:
            if uc.user and uc.user.id != self.user.id:
                opponent = uc.user
                opponent_id = uc.user.id
                opponent_type = "users"
                break
            elif uc.professional and uc.professional.id != self.user.id:
                opponent = uc.professional
                opponent_id = uc.professional.id
                opponent_type = "professional"
                break

        print("✅ Opponent ID:", opponent_id)
        print("✅ Opponent Type:", opponent_type)

        

        is_blocked = False
        is_blocked_opponent = False

        if opponent_id:
            if self.user_type == "users":
                if opponent_type == "users":
                    # opponent blocked self.user
                    is_blocked = BlockedUser.objects.filter(
                        blocked_by_id=opponent_id,
                        blocked_user_id=self.user.id
                    ).exists()
                    # self.user blocked opponent
                    is_blocked_opponent = BlockedUser.objects.filter(
                        blocked_by_id=self.user.id,
                        blocked_user_id=opponent_id
                    ).exists()

                elif opponent_type == "professional":
                    is_blocked = BlockedUser.objects.filter(
                        blocked_by_professional_id=opponent_id,
                        blocked_user_id=self.user.id
                    ).exists()
                    is_blocked_opponent = BlockedUser.objects.filter(
                        blocked_by_id=self.user.id,
                        blocked_user_professional_id=opponent_id
                    ).exists()

            elif self.user_type == "professional":
                if opponent_type == "users":
                    is_blocked = BlockedUser.objects.filter(
                        blocked_by_id=opponent_id,
                        blocked_user_professional_id=self.user.id
                    ).exists()
                    is_blocked_opponent = BlockedUser.objects.filter(
                        blocked_by_professional_id=self.user.id,
                        blocked_user_id=opponent_id
                    ).exists()

                elif opponent_type == "professional":
                    is_blocked = BlockedUser.objects.filter(
                        blocked_by_professional_id=opponent_id,
                        blocked_user_professional_id=self.user.id
                    ).exists()
                    is_blocked_opponent = BlockedUser.objects.filter(
                        blocked_by_professional_id=self.user.id,
                        blocked_user_professional_id=opponent_id
                    ).exists()

                
        result = []

        for msg in messages:
            # Identify receiver as the other participant in chat
            receiver_ids = [pid for pid in participant_ids if pid != msg.sender_object_id]
            receiver_id = receiver_ids[0] if receiver_ids else None

            # Determine receiver type based on id
            if receiver_id:
                if Users.objects.filter(id=receiver_id).exists():
                    receiver_type = "users"
                elif ProfessionalUser.objects.filter(id=receiver_id).exists():
                    receiver_type = "professional"
                else:
                    receiver_type = None
            else:
                receiver_type = None

            time_diff = self.get_time_difference(msg.created_at)
            message_type = "message"
            if msg.image:
                message_type = "image"
            elif msg.video:
                message_type = "video"
            elif msg.reels:
                message_type = "reels"

            result.append({
                "message": msg.content,
                "sender_id": msg.sender_object_id,
                "receiver_id": receiver_id,
                "receiver_type": receiver_type,
                "chat_id": self.chat.id,
                "image": self.get_s3_url(msg.image) if msg.image else None,
                "video": self.get_s3_url(msg.video) if msg.video else None,
                "reels": self.get_s3_url(msg.reels.video) if msg.reels else None,
                
                "message_type": message_type,
                "created_at": time_diff
            })
            
            
        return {
            "results": result[::-1], 
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "is_blocked": is_blocked,
            "is_blocked_opponent": is_blocked_opponent
        }

    def get_s3_url(self, file_field):
        return file_field.url if file_field else None

    def get_time_difference(self, created_at):
        if timezone.is_naive(created_at):
            created_at = timezone.make_aware(created_at)

        now = timezone.now()
        delta = now - created_at
        minutes = int(delta.total_seconds() // 60)
        hours = minutes // 60
        days = hours // 24

        if minutes < 60:
            return f"{minutes} min ago"
        elif hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            return f"{days} day{'s' if days != 1 else ''} ago"

    async def connect(self):
        self.receiver_id = int(self.scope["url_route"]["kwargs"]["receiver_id"])
        self.receiver_type = self.scope["url_route"]["kwargs"]["receiver_type"]
        query_string = self.scope["query_string"].decode()
        self.token = query_string.split("=")[-1]

        decoded = decode_token(self.token)
        if not decoded:
            await self.close()
            return

        self.user_type = decoded["type"]
        self.user_id = decoded["id"]

        try:
            if self.user_type == "users":
                self.user = await sync_to_async(Users.objects.get)(id=self.user_id)
            else:
                self.user = await sync_to_async(ProfessionalUser.objects.get)(id=self.user_id)
        except Exception:
            await self.close()
            return

        try:
            self.chat = await self.get_or_create_chat()
            self.room_name = f"chat_{self.chat.id}"
            self.room_group_name = self.room_name

            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()

            chat_history = await self.get_chat_history(page=1, page_size=20)
            await self.send(text_data=json.dumps({
                "chat_id": self.chat.id,
                "receiver_id": self.receiver_id,
                "receiver_type": self.receiver_type,
                "chat_history": chat_history
            }))
        except Exception:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    @sync_to_async
    def is_sender_blocked_by_receiver(self, user1, user2):
        queries = Q()

        # user1 blocked user2
        if isinstance(user1, Users) and isinstance(user2, Users):
            queries |= Q(blocked_by=user1, blocked_user=user2)
        if isinstance(user1, Users) and isinstance(user2, ProfessionalUser):
            queries |= Q(blocked_by=user1, blocked_user_professional=user2)
        if isinstance(user1, ProfessionalUser) and isinstance(user2, Users):
            queries |= Q(blocked_by_professional=user1, blocked_user=user2)
        if isinstance(user1, ProfessionalUser) and isinstance(user2, ProfessionalUser):
            queries |= Q(blocked_by_professional=user1, blocked_user_professional=user2)

        # user2 blocked user1
        if isinstance(user2, Users) and isinstance(user1, Users):
            queries |= Q(blocked_by=user2, blocked_user=user1)
        if isinstance(user2, Users) and isinstance(user1, ProfessionalUser):
            queries |= Q(blocked_by=user2, blocked_user_professional=user1)
        if isinstance(user2, ProfessionalUser) and isinstance(user1, Users):
            queries |= Q(blocked_by_professional=user2, blocked_user=user1)
        if isinstance(user2, ProfessionalUser) and isinstance(user1, ProfessionalUser):
            queries |= Q(blocked_by_professional=user2, blocked_user_professional=user1)

        return BlockedUser.objects.filter(queries).exists()


    @sync_to_async
    def save_message(self, content, image=None, video=None,reel_id=None):
        reels = None
        if reel_id:
            try:
                reels = StoreReel.objects.get(id=reel_id)
            except StoreReel.DoesNotExist:
                print("Reel does not exist")    
            
        return Message.objects.create(
            chat=self.chat,
            sender_content_type=ContentType.objects.get_for_model(self.user),
            sender_object_id=self.user.id,
            content=content,
            image=image,
            video=video,
            reels=reels
        )

    async def receive(self, text_data):
        try:
            if not text_data:
                return

            try:
                data = json.loads(text_data)
                
                if isinstance(data, dict): 
                    if data.get("type") == "pagination":
                        page = int(data.get("page", 1))
                        page_size = int(data.get("page_size", 10))
                        chat_history = await self.get_chat_history(page=page, page_size=page_size)
                        await self.send(text_data=json.dumps({
                            "chat_history": chat_history
                        }))
                        return
                    else:
                        message = data.get("message", "")
                        image = data.get("image")
                        video = data.get("video")
                        reels = data.get("reel_id")
                        image = self.decode_base64_file(image) if image else None
                        video = self.decode_base64_file(video) if video else None
                else:
                    message = str(data)
                    
            except json.JSONDecodeError:
                message = text_data
                image = None
                video = None
                reels = None
                
            except Exception:
                return

            participants = await sync_to_async(lambda: list(self.chat.userchat_set.values("user_id", "professional_id")))()
            
            participant_ids = [
                item["user_id"] if item["user_id"] is not None else item["professional_id"]
                for item in participants
            ]

            receiver_id = [pid for pid in participant_ids if pid != self.user.id][0] if len(participant_ids) == 2 else None
            if not receiver_id:
                await self.send(text_data=json.dumps({"error": "Receiver not found"}))
                return

            # Identify receiver instance
            try:
                # First check if it's a ProfessionalUser
                receiver = await sync_to_async(ProfessionalUser.objects.get)(id=receiver_id)
                receiver_type = "professional"
            except ProfessionalUser.DoesNotExist:
                try:
                    receiver = await sync_to_async(Users.objects.get)(id=receiver_id)
                    receiver_type = "users"
                except Users.DoesNotExist:
                    await self.send(text_data=json.dumps({"error": "Receiver not found"}))
                    return


            is_blocked_by_receiver = await self.is_sender_blocked_by_receiver(self.user, receiver)
            print("----------- is_blocked_by_receiver", is_blocked_by_receiver)
            is_blocked_by_sender = await self.is_sender_blocked_by_receiver(receiver, self.user)
            print("----------- is_blocked_by_sender", is_blocked_by_sender)
                
           # Block message if either user has blocked the other
            if is_blocked_by_receiver or is_blocked_by_sender:
                await self.send(text_data=json.dumps({
                    "error": "Messaging not allowed. One of you has blocked the other."
                }))
                return


            msg = await self.save_message(message, image, video, reels)
            
            
            
            sender_name = getattr(self.user, "username", None) or getattr(self.user, "userName", "Someone")
            content_msg = f"{sender_name} sent a new message"
        
            if receiver_type == "professional":
                print("=== Receiver is Professional ===")
                await sync_to_async(get_player_ids_by_professional_id)(receiver.id, content_msg)

            elif receiver_type == "users":
                print("=== Receiver is User ===")
                await sync_to_async(get_player_ids_by_user_id)(receiver.id, content_msg)

            await send_chat_list_update(self.user_type, self.user.id, self.chat.id)
            await send_chat_list_update(receiver_type, receiver.id, self.chat.id)
            
            time_diff = self.get_time_difference(msg.created_at)

            message_type = "message"
            if image:
                message_type = "image"
            elif video:
                message_type = "video"
            elif msg.reels:
                message_type = "reel"
                
            reel_data = None
            if msg.reels:
                reel_data = {
                    "id": msg.reels.id,
                    "title": msg.reels.title,
                    "video_url": self.get_s3_url(msg.reels.video),
                }

            response = {
                "message": msg.content,
                "sender_id": msg.sender_object_id,
                "receiver_id": receiver.id,
                # "receiver_type": "users" if isinstance(receiver, Users) else "professional",
                "receiver_type": receiver_type, 
                "chat_id": self.chat.id,
                "image": self.get_s3_url(msg.image) if msg.image else None,
                "video": self.get_s3_url(msg.video) if msg.video else None,
                "reel": reel_data,
                "message_type": message_type,
                "created_at": time_diff,
            }

            await self.channel_layer.group_send(self.room_group_name, {
                "type": "chat_message",
                "message": response
            })
            
       
        except Exception as e:
            # Log the error properly in real app
            print(f"Error in receive: {e}")
            traceback.print_exc()
            await self.send(text_data=json.dumps({"error": "An error occurred while processing"}))
            
    async def chat_message(self, event):
        try:
           
            # The message is sent with the correct receiver details
            message = event["message"]
            await self.send(text_data=json.dumps(message))
            
        except Exception as e:
            print(f"Error in chat_message: {e}")
            traceback.print_exc()



# class ChatConsumer(AsyncWebsocketConsumer):

#     def decode_base64_file(data):
#         try:
#             format, imgstr = data.split(';base64,')  
#             ext = format.split('/')[-1]  
#             filename = f"{uuid.uuid4()}.{ext}"  
#             return ContentFile(base64.b64decode(imgstr), name=filename)
#         except Exception as e:
#             print("Base64 decode error:", e)
#             return None
    
#     async def connect(self):
#         query_string = self.scope["query_string"].decode()
#         self.token = query_string.split("=")[-1]

#         decoded = decode_token(self.token)
#         if not decoded or decoded["type"] not in ["users", "admin"]:
#             await self.close()
#             return

#         self.user_type = decoded["type"]
#         self.user_id = decoded["id"]
        
        
#         try:
#             if self.user_type == "users":
               
#                 self.user = await sync_to_async(Users.objects.get)(id=self.user_id)
#                 self.receiver = await sync_to_async(AdminUser.objects.first)()
#                 if not self.receiver:
#                     await self.close()
#                     return
#                 self.receiver_type = "admin"
#                 self.receiver = await sync_to_async(AdminUser.objects.first)()
#                 self.receiver_id = self.receiver.id
#             else:
                
#                 self.user = await sync_to_async(AdminUser.objects.get)(id=self.user_id)
#                 self.receiver_type = self.scope["url_route"]["kwargs"].get("receiver_type")
#                 receiver_id = self.scope["url_route"]["kwargs"].get("receiver_id")

#                 if self.receiver_type != "users" or not receiver_id:
#                     await self.close()
#                     return

#                 self.receiver = await sync_to_async(Users.objects.get)(id=receiver_id)
#                 self.receiver_id = self.receiver.id
                

#         except Exception as e:
#             print(f"Error in connect: {e}")
#             await self.close()
#             return

#         try:
#             self.chat = await self.get_or_create_chat()
#             self.room_name = f"chat_{self.chat.id}"
#             self.room_group_name = self.room_name

#             await self.channel_layer.group_add(self.room_group_name, self.channel_name)
#             await self.accept()

#             chat_history = await self.get_chat_history(page=1, page_size=20)
#             await self.send(text_data=json.dumps({
#                 "chat_id": self.chat.id,
#                 "receiver_type": self.receiver_type,
#                 "receiver_id": self.receiver.id,
#                 "chat_history": chat_history
#             }))
#         except Exception as e:
#             print(f"Error in connect: {e}")
#             traceback.print_exc()
#             await self.close()
    

#     @sync_to_async
#     def get_or_create_chat(self):
#         # Determine receiver instance
#         print(f"[DEBUG] Receiver ID: {self.receiver_id}")
#         print(f"[DEBUG] Receiver Type: {self.receiver_type}")
        
#         receiver_model = Users if self.receiver_type == "users" else AdminUser
#         receiver = receiver_model.objects.filter(id=self.receiver_id).first()
#         if not receiver:
#             raise Exception("Receiver not found")

#         # Define sender and receiver types and IDs
#         sender_type = "users" if isinstance(self.user, Users) else "admin"
#         sender_id = self.user.id
#         receiver_type = "users" if isinstance(receiver, Users) else "admin"
#         receiver_id = receiver.id

#         # Get all chats involving the sender
#         user_chats = Chat.objects.filter(
#             Q(userchat__user_id=sender_id) | Q(userchat__admin_id=sender_id)
#         ).distinct()

#         # Search for a chat with exactly these two participants
#         for chat in user_chats:
#             participants = set()
#             for uc in chat.userchat_set.all():
#                 if uc.user:
#                     participants.add(("users", uc.user.id))
#                 elif uc.admin:
#                     participants.add(("admin", uc.admin.id))

#             if participants == {(sender_type, sender_id), (receiver_type, receiver_id)}:
#                 return chat

#         # Create new chat if none exists
#         chat = Chat.objects.create(receiver_type=self.receiver_type, receiver_id=receiver.id)
#         entries = []

#         if sender_type == "users":
#             entries.append(UserChat(user=self.user, chat=chat))
#         else:
#             entries.append(UserChat(admin=self.user, chat=chat))

#         if receiver_type == "users":
#             entries.append(UserChat(user=receiver, chat=chat))
#         else:
#             entries.append(UserChat(admin=receiver, chat=chat))

#         UserChat.objects.bulk_create(entries)
#         return chat

    
#     @sync_to_async
#     def get_chat_history(self,page=1, page_size=20):
#         messages = Message.objects.filter(chat=self.chat).order_by("created_at").select_related("sender_content_type")
#         paginator = Paginator(messages, page_size)
#         page_obj = paginator.get_page(page)
        
#         result = []
#         for msg in messages:
#             sender_id = msg.sender_object_id
#             receiver_id = self.receiver.id if sender_id != self.receiver.id else self.user.id

#             result.append({
#                 "message": msg.content,
#                 "sender_id": sender_id,
#                 "receiver_id": receiver_id,
#                 "receiver_type": self.receiver_type,
#                 "chat_id": self.chat.id,
#                 "image": self.get_s3_url(msg.image) if msg.image else None,
#                 "video": self.get_s3_url(msg.video) if msg.video else None,
#                 "message_type": "image" if msg.image else "video" if msg.video else "message",
#                 "created_at": self.get_time_difference(msg.created_at)
#             })

#         return {
#             "results": result[::-1], 
#             "total_pages": paginator.num_pages,
#             "current_page": page_obj.number,
#             "has_next": page_obj.has_next(),
#             "has_previous": page_obj.has_previous()
#         }

#     def get_s3_url(self, file_field):
#         return file_field.url if file_field else None

#     def get_time_difference(self, created_at):
#         if timezone.is_naive(created_at):
#             created_at = timezone.make_aware(created_at)
#         delta = timezone.now() - created_at
#         minutes = int(delta.total_seconds() // 60)
#         hours = minutes // 60
#         days = hours // 24

#         if minutes < 60:
#             return f"{minutes} min ago"
#         elif hours < 24:
#             return f"{hours} hour{'s' if hours != 1 else ''} ago"
#         return f"{days} day{'s' if days != 1 else ''} ago"

#     async def disconnect(self, close_code):
#         if hasattr(self, "room_group_name"):
#             await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

#     @sync_to_async
#     def save_message(self, content, image=None, video=None):
#         return Message.objects.create(
#             chat=self.chat,
#             sender_content_type=ContentType.objects.get_for_model(self.user),
#             sender_object_id=self.user.id,
#             content=content,
#             image=image,
#             video=video,
#         )

#     async def receive(self, text_data):
#         try:
#             if not text_data:
#                 return
            
#             data = {}
#             message, image, video = "", None, None
#             try:
#                 data = json.loads(text_data)
#                 if isinstance(data, dict): 
#                     if data.get("type") == "pagination":
#                         page = int(data.get("page", 1))
#                         page_size = int(data.get("page_size", 10))
#                         chat_history = await self.get_chat_history(page=page, page_size=page_size)
#                         await self.send(text_data=json.dumps({
#                             "chat_history": chat_history
#                         }))
#                         return
#                     else:
#                         message = data.get("message", "")
#                         image = data.get("image")
#                         video = data.get("video")
#                         image = self.decode_base64_file(image) if image else None
#                         video = self.decode_base64_file(video) if video else None
#                 else:
#                     message = str(data)
                    
#             except json.JSONDecodeError:
#                 message, image, video = text_data, None, None

            
            
#             msg = await self.save_message(message, image, video)
            
#             #-------- notifications --------
            
#             await self.send_notification(self.user, self.receiver, msg.content)
            
#             response = {
#                 "message": msg.content,
#                 "sender_id": msg.sender_object_id,
#                 "receiver_id": self.receiver.id,
#                 "receiver_type": self.receiver_type,
#                 "chat_id": self.chat.id,
#                 "image": self.get_s3_url(msg.image) if msg.image else None,
#                 "video": self.get_s3_url(msg.video) if msg.video else None,
#                 "message_type": "image" if msg.image else "video" if msg.video else "message",
#                 "created_at": self.get_time_difference(msg.created_at)
#             }

#             await self.channel_layer.group_send(self.room_group_name, {
#                 "type": "chat_message",
#                 "message": response
#             })

#         except Exception as e:
#             print(f"Error in receive: {e}")
#             traceback.print_exc()
#             await self.send(text_data=json.dumps({"error": "An error occurred while processing"}))

#     async def chat_message(self, event):
#         try:
#             await self.send(text_data=json.dumps(event["message"]))
#         except Exception as e:
#             print(f"Error in chat_message: {e}")
#             traceback.print_exc()
            
#     @sync_to_async
#     def send_notification(self, sender, receiver, message):
#         try:
#             ChatNotifications.objects.create(
#                 sender_content_type=ContentType.objects.get_for_model(sender),
#                 sender_object_id=sender.id,
#                 receiver_content_type=ContentType.objects.get_for_model(receiver),
#                 receiver_object_id=receiver.id,
#                 message=f"New message from {sender.username}: {message}",
#                 notification_type="chat",
#                 is_read=False
#             )
#         except Exception as e:
#             print(f"Notification error: {e}")

            

class ChatConsumer(AsyncWebsocketConsumer):

    def decode_base64_file(self, data):
        try:
            format, imgstr = data.split(';base64,')  
            ext = format.split('/')[-1]  
            filename = f"{uuid.uuid4()}.{ext}"
            return ContentFile(base64.b64decode(imgstr), name=filename)
        except Exception as e:
            print("Base64 decode error:", e)
            return None

    async def connect(self):
        query_string = self.scope["query_string"].decode()
        print("Query string:", query_string)
        self.token = query_string.split("=")[-1]

        decoded = decode_token(self.token)
        if not decoded or decoded["type"] not in ["users", "admin", "professional"]:
            await self.close()
            return

        self.user_type = decoded["type"]
        self.user_id = decoded["id"]

        try:
            if self.user_type == "users":
                self.user = await database_sync_to_async(Users.objects.get)(id=self.user_id)
                self.receiver = await database_sync_to_async(AdminUser.objects.first)()
                self.receiver_type = "admin"
                self.receiver_id = self.receiver.id
                self.chat = await self.get_or_create_chat()

            elif self.user_type == "admin":
                self.user = await database_sync_to_async(AdminUser.objects.get)(id=self.user_id)
                self.receiver_type = self.scope["url_route"]["kwargs"].get("receiver_type")
                receiver_id = self.scope["url_route"]["kwargs"].get("receiver_id")
                self.receiver = await database_sync_to_async(Users.objects.get)(id=receiver_id)
                self.receiver_id = self.receiver.id
                self.chat = await self.get_or_create_chat()

            elif self.user_type == "professional":
                self.user = await database_sync_to_async(ProfessionalUser.objects.get)(id=self.user_id)
                print("=======================================self.user", self.user)
                print(f"----[DEBUG] URL route kwargs: {self.scope['url_route']['kwargs']}")
                self.chat_id = self.scope["url_route"]["kwargs"].get("receiver_id")
                print(f"[DEBUG] Professional user connecting. chat_id={self.chat_id}")
                if not self.chat_id:
                    print("[ERROR] No chat_id provided in URL for professional connection.")
                    await self.close()
                    return {"error": "No chat_id provided in URL."}
                try:
                    self.chat = await database_sync_to_async(Chat.objects.get)(id=self.chat_id)
                except Chat.DoesNotExist:
                    print(f"[ERROR] Chat with id {self.chat_id} does not exist.")
                    await self.close()
                    return {"error": "Chat not found."}
                self.receiver = None  # professional can talk to all participants
                self.receiver_type = "group"
                self.receiver_id = None

            self.room_name = f"chat_{self.chat.id}"
            self.room_group_name = self.room_name
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()

            chat_history = await self.get_chat_history(page=1, page_size=20)
            await self.send(text_data=json.dumps({
                "chat_id": self.chat.id,
                "receiver_type": self.receiver_type,
                "receiver_id": self.receiver_id,
                "chat_history": chat_history
            }))

        except Exception as e:
            print(f"Error in connect: {e}")
            traceback.print_exc()
            await self.close()

    @database_sync_to_async
    def get_or_create_chat(self):
        sender_type = self.user_type
        sender_id = self.user_id
        receiver_type = self.receiver_type
        receiver_id = self.receiver_id

        chats = Chat.objects.filter(
            Q(userchat__user_id=sender_id) | 
            Q(userchat__admin_id=sender_id) | 
            Q(userchat__professional_id=sender_id)
        ).distinct()

        for chat in chats:
            participants = set()
            for uc in chat.userchat_set.all():
                if uc.user:
                    participants.add(("users", uc.user.id))
                if uc.admin:
                    participants.add(("admin", uc.admin.id))
                if uc.professional:
                    participants.add(("professional", uc.professional.id))
            # if participants == {(sender_type, sender_id), (receiver_type, receiver_id)}:
            #     return chat

          # FIX: Check if both sender and receiver are in this chat
            if (sender_type, sender_id) in participants and (receiver_type, receiver_id) in participants:
                print(f"[INFO] Found existing chat ID: {chat.id}")
                return chat
        
        chat = Chat.objects.create(receiver_type=receiver_type, receiver_id=receiver_id)
        entries = []

        if sender_type == "users":
            entries.append(UserChat(user=self.user, chat=chat))
        elif sender_type == "admin":
            entries.append(UserChat(admin=self.user, chat=chat))

        if receiver_type == "users":
            entries.append(UserChat(user=self.receiver, chat=chat))
        elif receiver_type == "admin":
            entries.append(UserChat(admin=self.receiver, chat=chat))

        UserChat.objects.bulk_create(entries)
        return chat

    @database_sync_to_async
    def get_chat_history(self, page=1, page_size=20):
        messages = Message.objects.filter(chat=self.chat).order_by("created_at").select_related("sender_content_type")
        paginator = Paginator(messages, page_size)
        page_obj = paginator.get_page(page)

        result = []
        for msg in page_obj:
            result.append({
                "message": msg.content,
                "sender_id": msg.sender_object_id,
                "receiver_type": self.receiver_type,
                "receiver_id": self.receiver_id,
                "chat_id": self.chat.id,
                "image": self.get_s3_url(msg.image) if msg.image else None,
                "video": self.get_s3_url(msg.video) if msg.video else None,
                "message_type": "image" if msg.image else "video" if msg.video else "message",
                "created_at": self.get_time_difference(msg.created_at)
            })

        return {
            "results": result[::-1],
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous()
        }

    def get_s3_url(self, file_field):
        return file_field.url if file_field else None

    def get_time_difference(self, created_at):
        if timezone.is_naive(created_at):
            created_at = timezone.make_aware(created_at)
        delta = timezone.now() - created_at
        minutes = int(delta.total_seconds() // 60)
        hours = minutes // 60
        days = hours // 24

        if minutes < 60:
            return f"{minutes} min ago"
        elif hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        return f"{days} day{'s' if days != 1 else ''} ago"

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    @database_sync_to_async
    def save_message(self, content, image=None, video=None):
        return Message.objects.create(
            chat=self.chat,
            sender_content_type=ContentType.objects.get_for_model(self.user),
            sender_object_id=self.user.id,
            content=content,
            image=image,
            video=video,
        )

    async def receive(self, text_data):
        try:
            
            if not text_data:
                return
            
            data = {}
            message, image, video = "", None, None
            try:
                data = json.loads(text_data)
                if isinstance(data, dict): 
                    if data.get("type") == "pagination":
                        page = int(data.get("page", 1))
                        page_size = int(data.get("page_size", 10))
                        chat_history = await self.get_chat_history(page=page, page_size=page_size)
                        await self.send(text_data=json.dumps({
                            "chat_history": chat_history
                        }))
                        return
                    else:
                        message = data.get("message", "")
                        image = data.get("image")
                        video = data.get("video")
                        image = self.decode_base64_file(image) if image else None
                        video = self.decode_base64_file(video) if video else None
                else:
                    message = str(data)
                    
            except json.JSONDecodeError:
                message, image, video = text_data, None, None

            msg = await self.save_message(message, image, video)

            # await self.send_notification(self.user, msg.content)

            response = {
                "message": msg.content,
                "sender_id": msg.sender_object_id,
                "receiver_type": self.receiver_type,
                "receiver_id": self.receiver_id,
                "chat_id": self.chat.id,
                "image": self.get_s3_url(msg.image) if msg.image else None,
                "video": self.get_s3_url(msg.video) if msg.video else None,
                "message_type": "image" if msg.image else "video" if msg.video else "message",
                "created_at": self.get_time_difference(msg.created_at)
            }

            await self.channel_layer.group_send(self.room_group_name, {
                "type": "chat_message",
                "message": response
            })

        except Exception as e:
            print(f"Error in receive: {e}")
            traceback.print_exc()
            await self.send(text_data=json.dumps({"error": "An error occurred while processing"}))

    async def chat_message(self, event):
        try:
            await self.send(text_data=json.dumps(event["message"]))
        except Exception as e:
            print(f"Error in chat_message: {e}")
            traceback.print_exc()

    @database_sync_to_async
    def send_notification(self, sender, message):
        try:
            participants = self.chat.userchat_set.all()
            for participant in participants:
                receiver = participant.user or participant.admin or participant.professional
                if receiver and receiver.id != sender.id:
                    ChatNotifications.objects.create(
                        sender_content_type=ContentType.objects.get_for_model(sender),
                        sender_object_id=sender.id,
                        receiver_content_type=ContentType.objects.get_for_model(receiver),
                        receiver_object_id=receiver.id,
                        message=f"New message from {sender.username}: {message}",
                        notification_type="chat",
                        is_read=False
                    )
        except Exception as e:
            print(f"Notification error: {e}") 
            
        
# class GroupChatConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         query_string = self.scope["query_string"].decode()
#         self.token = query_string.split("=")[-1]
        
       
#         self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']  
        
#         print("--------------------------------  Ticket ID:", self.ticket_id)
#         # ⭐️ **Validate required ticket_id**
#         if not self.ticket_id:
#             await self.close()
#             return
        
#         decoded = decode_token(self.token)

#         if not decoded or decoded["type"] not in ["users", "admin", "professional"]:
#             await self.close()
#             return

#         self.user_type = decoded["type"]
#         self.user_id = decoded["id"]

#         try:
#             if self.user_type == "users":
#                 self.user = await sync_to_async(Users.objects.get)(id=self.user_id)
#             elif self.user_type == "admin":
#                 self.user = await sync_to_async(AdminUser.objects.get)(id=self.user_id)
#             elif self.user_type == "professional":
#                 self.user = await sync_to_async(ProfessionalUser.objects.get)(id=self.user_id)
#         except Exception as e:
#             print("User fetch error:", e)
#             await self.close()
#             return
        
#         # ⭐️ **Group name is based on ticket**
#         self.room_group_name = f"ticket_{self.ticket_id}"

#         # ⭐️ **Ensure the ticket exists and get related users**
#         ticket = await self.get_ticket(self.ticket_id)
#         if not ticket:
#             await self.close()
#             return

#         # self.room_group_name = self.scope['url_route']['kwargs']['group_name']
#         # print("Group name:", self.room_group_name)

#         # chat = await self.get_or_create_group_chat_by_name(self.room_group_name)
#         # await self.add_user_to_chat(chat, self.user)

#         await self.channel_layer.group_add(self.room_group_name, self.channel_name)
#         await self.accept()

#         # ⭐️ **Create or fetch chat for ticket**
#         chat = await self.get_or_create_group_chat_by_name(ticket)

#         # ⭐️ **Add all three (user, professional, admin) to chat**
#         user = await database_sync_to_async(Users.objects.get)(id=ticket.created_by_user_id)
#         await self.add_user_to_chat(chat, user)
        
#         professional_user = await sync_to_async(lambda: ticket.order.professional_user)()
#         await self.add_user_to_chat(chat, professional_user)
        
#         admin = await sync_to_async(AdminUser.objects.first)()
        
#         if admin:
#             await self.add_user_to_chat(chat, admin)

        
#         chat_history = await self.get_chat_history(page=1, page_size=20)
#         await self.send(text_data=json.dumps({
#             "chat_id": chat.id,
#             "chat_history": chat_history
#             }))


#     # ⭐️ **Add this method to get ticket**
#     @sync_to_async
#     def get_ticket(self, ticket_id):
#         from Admin.models import SupportTicket  # ⚠️ **CHANGE THIS IF Ticket IS IN ANOTHER APP**
#         return SupportTicket.objects.filter(ticket_id=ticket_id).first()
    
    
#     async def disconnect(self, close_code):
#         # await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
#         if hasattr(self, "room_group_name"):
#             await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

#     async def receive(self, text_data):
#         try:
#             if not text_data:
#                 return f"No data received"

#             try:
#                 print("Received data:", text_data)
#                 data = json.loads(text_data)
#                 # message = data.get("message", "")
#                 # image = data.get("image")
#                 # video = data.get("video")
#                 if isinstance(data, dict): 
#                     if data.get("type") == "pagination":
#                         page = int(data.get("page", 1))
#                         page_size = int(data.get("page_size", 10))
#                         chat_history = await self.get_chat_history(page=page, page_size=page_size)
#                         await self.send(text_data=json.dumps({
#                             "chat_history": chat_history
#                         }))
#                         return
#                     else:
#                         message = data.get("message", "")
#                         image = data.get("image")
#                         video = data.get("video")
#                 else:
#                     message = str(data)
                    
#             except json.JSONDecodeError:
#                 message, image, video = text_data, None, None
                

#             print("Received message:", message)
#             msg = await self.save_message(message, image, video)
            
            
#             #----------------- notifications -----------------
            
#             # await self.send_group_notification(msg)
            
#             response = {
#                 "message": msg.content,
#                 "sender_id": msg.sender_object_id,
#                 "sender_type": self.user_type,
#                 "chat_id": msg.chat.id,
#                 "image": self.get_s3_url(msg.image) if msg.image else None,
#                 "video": self.get_s3_url(msg.video) if msg.video else None,
#                 "message_type": "image" if msg.image else "video" if msg.video else "message",
#                 "created_at": self.get_time_difference(msg.created_at)
#             }

#             await self.channel_layer.group_send(self.room_group_name, {
#                 "type": "chat_message",
#                 "message": response
#             })
#         except Exception as e:
#             print("Receive error:", e)
            
        
#     async def chat_message(self, event):
#         try:
#             await self.send(text_data=json.dumps(event["message"]))
#         except Exception as e:
#             print(f"Error in chat_message: {e}")
#             traceback.print_exc()

#     @sync_to_async
#     def get_or_create_group_chat_by_name(self, ticket):
        
#         group_name = f"ticket_{ticket.ticket_id}"
        
#         chat = Chat.objects.filter(is_group=True, name=group_name).first()
#         if chat:
#             return chat

#         chat = Chat.objects.create(is_group=True, name=group_name)
#         # Add current user to chat through UserChat
#         user_model_name = self.user.__class__.__name__.lower()

#         if user_model_name == 'users':
#             UserChat.objects.create(user=self.user, chat=chat)
#         elif user_model_name == 'adminuser':
#             UserChat.objects.create(admin=self.user, chat=chat)
#         elif user_model_name == 'professionaluser':
#             UserChat.objects.create(professional=self.user, chat=chat)
#         else:
#             UserChat.objects.create(user=self.user, chat=chat)

#         return chat

#     @sync_to_async
#     def add_user_to_chat(self, chat, user):
#         print(f"Adding user {user.id} to chat {chat.id}")
#         user_model_name = user.__class__.__name__.lower()

#         exists = False
#         if user_model_name == 'users':
#             exists = UserChat.objects.filter(chat=chat, user=user).exists()
#         elif user_model_name == 'adminuser':
#             exists = UserChat.objects.filter(chat=chat, admin=user).exists()
#         elif user_model_name == 'professionaluser':
#             exists = UserChat.objects.filter(chat=chat, professional=user).exists()

#         if not exists:
#             if user_model_name == 'users':
#                 UserChat.objects.create(chat=chat, user=user)
#             elif user_model_name == 'adminuser':
#                 UserChat.objects.create(chat=chat, admin=user)
#             elif user_model_name == 'professionaluser':
#                 UserChat.objects.create(chat=chat, professional=user)

#     @sync_to_async
#     def get_chat_history(self,page=1, page_size=20):
#         print(f"==============Fetching chat history for group: {self.room_group_name}")
#         chat = Chat.objects.filter(is_group=True, name=self.room_group_name).first()
        
#         if not chat:
#             return {"results": [], "total_pages": 0, "current_page": 1, "has_next": False, "has_previous": False}

#         messages = Message.objects.filter(chat=chat).order_by("created_at")
#         paginator = Paginator(messages, page_size)
#         page_obj = paginator.get_page(page)
        
#         result = []
#         for msg in messages:
#             result.append({
#                 "message": msg.content,
#                 "sender_id": msg.sender_object_id,
#                 "sender_type": msg.sender_content_type.model if msg.sender_content_type else None,
#                 "chat_id": msg.chat.id,
#                 "image": self.get_s3_url(msg.image) if msg.image else None,
#                 "video": self.get_s3_url(msg.video) if msg.video else None,
#                 "message_type": "image" if msg.image else "video" if msg.video else "message",
#                 "created_at": self.get_time_difference(msg.created_at)
#             })
#         return {
#             "results": result[::-1], 
#             "total_pages": paginator.num_pages,
#             "current_page": page_obj.number,
#             "has_next": page_obj.has_next(),
#             "has_previous": page_obj.has_previous()
#         }

#     @sync_to_async
#     def save_message(self, content, image=None, video=None):
#         print(f"===============================Saving message: {content}")
#         chat = Chat.objects.filter(is_group=True, name=self.room_group_name).first()
#         if not chat:
#             chat = Chat.objects.create(is_group=True, name=self.room_group_name)
#         return Message.objects.create(
#             chat=chat,
#             sender_content_type=ContentType.objects.get_for_model(self.user),
#             sender_object_id=self.user.id,
#             content=content,
#             image=image,
#             video=video,
#         )

#     # ---------------- notifications 
#     @sync_to_async
#     def send_group_notification(self, message_obj):
#         chat = message_obj.chat
#         user_chats = UserChat.objects.filter(chat=chat)

#         for user_chat in user_chats:
#             receiver = None
#             receiver_type = None

#             if user_chat.user and user_chat.user.id != self.user_id:
#                 receiver = user_chat.user
#                 receiver_type = "users"
#             elif user_chat.admin and user_chat.admin.id != self.user_id:
#                 receiver = user_chat.admin
#                 receiver_type = "admin"
#             elif user_chat.professional and user_chat.professional.id != self.user_id:
#                 receiver = user_chat.professional
#                 receiver_type = "professional"

#             if receiver:
#                 ChatNotifications.objects.create(
#                     receiver_content_type=ContentType.objects.get_for_model(receiver),
#                     receiver_object_id=receiver.id,
#                     sender_content_type=ContentType.objects.get_for_model(self.user),
#                     sender_object_id=self.user.id,
#                     message=f"New message in group: {chat.name}",
#                     notification_type="group_chat"
#                 )
                
#     def get_s3_url(self, file_field):
#         return file_field.url if file_field else None

#     def get_time_difference(self, created_at):
#         delta = timezone.now() - created_at
#         minutes = int(delta.total_seconds() // 60)
#         if minutes < 60:
#             return f"{minutes} min ago"
#         hours = minutes // 60
#         if hours < 24:
#             return f"{hours} hours ago"
#         days = hours // 24
#         return f"{days} days ago"


        
# class GroupChatConsumer(AsyncWebsocketConsumer):
    
#     def decode_base64_file(self, data):
#         try:
#             print("data", data)
#             format, imgstr = data.split(';base64,')  
#             ext = format.split('/')[-1]  
#             filename = f"{uuid.uuid4()}.{ext}"
#             return ContentFile(base64.b64decode(imgstr), name=filename)
#         except Exception as e:
#             print("Base64 decode error:", e)
#             return None
    
#     async def connect(self):
#         query_string = self.scope["query_string"].decode()
#         self.token = query_string.split("=")[-1]

#         self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']  
#         print("--------------------------------  Ticket ID:", self.ticket_id)

#         if not self.ticket_id:
#             await self.close()
#             return

#         decoded = decode_token(self.token)

#         if not decoded or decoded["type"] not in ["users", "admin", "professional"]:
#             await self.close()
#             return

#         self.user_type = decoded["type"]
#         self.user_id = decoded["id"]

#         try:
#             if self.user_type == "users":
#                 print("------------------------  User ID:", self.user_id)
#                 self.user = await sync_to_async(Users.objects.get)(id=self.user_id)
#             elif self.user_type == "admin":
#                 print("---=================================Admin ID:", self.user_id)
#                 self.user = await sync_to_async(AdminUser.objects.get)(id=self.user_id)
#             elif self.user_type == "professional":
#                 print("------------------------  Professional ID:", self.user_id)
#                 self.user = await sync_to_async(ProfessionalUser.objects.get)(id=self.user_id)
#         except Exception as e:
#             print("User fetch error:", e)
#             await self.close()
#             return

#         self.room_group_name = f"ticket_{self.ticket_id}"
#         print("Room group name:", self.room_group_name)

#         ticket = await self.get_ticket(self.ticket_id)
#         print("Ticket fetched:", ticket)
#         if not ticket:
#             await self.close()
#             return

#         #  Join WebSocket group
#         await self.channel_layer.group_add(self.room_group_name, self.channel_name)
#         await self.accept()

#         #  Create or get chat for this ticket
#         chat = await self.get_or_create_group_chat_by_name(ticket)
#         print("Chat fetched:", chat)

#         #  Get necessary users
#         user = await sync_to_async(Users.objects.get)(id=ticket.created_by_user_id)
#         print("User fetched:", user)
        
#         admin = await sync_to_async(AdminUser.objects.first)()
#         print("Admin fetched:", admin)
#         is_specific_order = await sync_to_async(lambda: ticket.specific_order)()
#         print("------------------------------specific_order:", is_specific_order)

#         #  Always add the current user to chat
#         await self.add_user_to_chat(chat, self.user)

#         if is_specific_order:
#         # ➤ If specific_order is TRUE → auto-add user, admin, professional
#             if user:
#                 await self.add_user_to_chat(chat, user)
#             if admin:
#                 await self.add_user_to_chat(chat, admin)
#             try:
#                 professional_user = await sync_to_async(lambda: ticket.order.professional_user)()
#                 if professional_user:
#                     await self.add_user_to_chat(chat, professional_user)
#             except Exception as e:
#                 print("Error fetching professional for specific order:", e)
#         else:
#             # ➤ If specific_order is FALSE → only auto-add user and admin
#             if self.user_type in ["users", "admin"]:
#                 if user:
#                     await self.add_user_to_chat(chat, user)
#                 if admin:
#                     await self.add_user_to_chat(chat, admin)

#         #  Send chat history
#         chat_history = await self.get_chat_history(page=1, page_size=20)
#         await self.send(text_data=json.dumps({
#             "chat_id": chat.id,
#             "chat_history": chat_history
#         }))


#     # ⭐️ **Add this method to get ticket**
#     @sync_to_async
#     def get_ticket(self, ticket_id):
#         from Admin.models import SupportTicket  # ⚠️ **CHANGE THIS IF Ticket IS IN ANOTHER APP**
#         return SupportTicket.objects.filter(ticket_id=ticket_id).first()
    
    
#     async def disconnect(self, close_code):
#         # await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
#         if hasattr(self, "room_group_name"):
#             await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

#     async def receive(self, text_data):
#         try:
#             if not text_data:
#                 return f"No data received"
            
#             print("receive() triggered ")
#             try:
#                 print("Received data:", text_data)
#                 data = json.loads(text_data)
#                 # message = data.get("message", "")
#                 # image = data.get("image")
#                 # video = data.get("video")
#                 if isinstance(data, dict): 
#                     if data.get("type") == "pagination":
#                         page = int(data.get("page", 1))
#                         page_size = int(data.get("page_size", 10))
#                         chat_history = await self.get_chat_history(page=page, page_size=page_size)
#                         await self.send(text_data=json.dumps({
#                             "chat_history": chat_history
#                         }))
#                         return
#                     else:
#                         message = data.get("message", "")
#                         image = data.get("image")
#                         print("---------11111111111111111---------------image:", image)
#                         video = data.get("video")
#                         print("---------22222222222222222---------------video:", video)
#                         image = self.decode_base64_file(image) if image else None
#                         print("------------------------image:", image)
#                         video = self.decode_base64_file(video) if video else None
#                         print("------------------------video:", video)
#                 else:
#                     message = str(data)
                    
#             except json.JSONDecodeError:
#                 message, image, video = text_data, None, None
                

#             print("Received message:", message)
#             msg = await self.save_message(message, image, video)
            
            
#             #----------------- notifications -----------------
            
#             # await self.send_group_notification(msg)
            
#             response = {
#                 "message": msg.content,
#                 "sender_id": msg.sender_object_id,
#                 "sender_type": self.user_type,
#                 "chat_id": msg.chat.id,
#                 "image": self.get_s3_url(msg.image) if msg.image else None,
#                 "video": self.get_s3_url(msg.video) if msg.video else None,
#                 "message_type": "image" if msg.image else "video" if msg.video else "message",
#                 "created_at": self.get_time_difference(msg.created_at)
#             }

#             await self.channel_layer.group_send(self.room_group_name, {
#                 "type": "chat_message",
#                 "message": response
#             })
#         except Exception as e:
#             print("Receive error:", e)
            
        
#     async def chat_message(self, event):
#         try:
#             await self.send(text_data=json.dumps(event["message"]))
#         except Exception as e:
#             print(f"Error in chat_message: {e}")
#             traceback.print_exc()

#     @sync_to_async
#     def get_or_create_group_chat_by_name(self, ticket):
        
#         group_name = f"ticket_{ticket.ticket_id}"
        
#         chat = Chat.objects.filter(is_group=True, name=group_name).first()
#         if chat:
#             return chat

#         chat = Chat.objects.create(is_group=True, name=group_name)
#         # Add current user to chat through UserChat
#         user_model_name = self.user.__class__.__name__.lower()

#         if user_model_name == 'users':
#             UserChat.objects.create(user=self.user, chat=chat)
#         elif user_model_name == 'adminuser':
#             UserChat.objects.create(admin=self.user, chat=chat)
#         elif user_model_name == 'professionaluser':
#             UserChat.objects.create(professional=self.user, chat=chat)
#         else:
#             UserChat.objects.create(user=self.user, chat=chat)

#         return chat

#     @sync_to_async
#     def add_user_to_chat(self, chat, user):
#         print(f"Adding user {user.id} to chat {chat.id}")
#         user_model_name = user.__class__.__name__.lower()

#         exists = False
#         if user_model_name == 'users':
#             exists = UserChat.objects.filter(chat=chat, user=user).exists()
#         elif user_model_name == 'adminuser':
#             exists = UserChat.objects.filter(chat=chat, admin=user).exists()
#         elif user_model_name == 'professionaluser':
#             exists = UserChat.objects.filter(chat=chat, professional=user).exists()

#         if not exists:
#             if user_model_name == 'users':
#                 UserChat.objects.create(chat=chat, user=user)
#             elif user_model_name == 'adminuser':
#                 UserChat.objects.create(chat=chat, admin=user)
#             elif user_model_name == 'professionaluser':
#                 UserChat.objects.create(chat=chat, professional=user)

#     @sync_to_async
#     def get_chat_history(self,page=1, page_size=20):
#         print(f"==============Fetching chat history for group: {self.room_group_name}")
#         chat = Chat.objects.filter(is_group=True, name=self.room_group_name).first()
        
#         if not chat:
#             return {"results": [], "total_pages": 0, "current_page": 1, "has_next": False, "has_previous": False}

#         messages = Message.objects.filter(chat=chat).order_by("created_at")
#         paginator = Paginator(messages, page_size)
#         page_obj = paginator.get_page(page)
        
#         result = []
#         for msg in messages:
#             result.append({
#                 "message": msg.content,
#                 "sender_id": msg.sender_object_id,
#                 "sender_type": msg.sender_content_type.model if msg.sender_content_type else None,
#                 "chat_id": msg.chat.id,
#                 "image": self.get_s3_url(msg.image) if msg.image else None,
#                 "video": self.get_s3_url(msg.video) if msg.video else None,
#                 "message_type": "image" if msg.image else "video" if msg.video else "message",
#                 "created_at": self.get_time_difference(msg.created_at)
#             })
#         return {
#             "results": result[::-1], 
#             "total_pages": paginator.num_pages,
#             "current_page": page_obj.number,
#             "has_next": page_obj.has_next(),
#             "has_previous": page_obj.has_previous()
#         }

#     @sync_to_async
#     def save_message(self, content, image=None, video=None):
#         print(f"===============================Saving message: {content}")
#         chat = Chat.objects.filter(is_group=True, name=self.room_group_name).first()
#         if not chat:
#             chat = Chat.objects.create(is_group=True, name=self.room_group_name)
#         return Message.objects.create(
#             chat=chat,
#             sender_content_type=ContentType.objects.get_for_model(self.user),
#             sender_object_id=self.user.id,
#             content=content,
#             image=image,
#             video=video,
#         )

#     # ---------------- notifications 
#     @sync_to_async
#     def send_group_notification(self, message_obj):
#         chat = message_obj.chat
#         user_chats = UserChat.objects.filter(chat=chat)

#         for user_chat in user_chats:
#             receiver = None
#             receiver_type = None

#             if user_chat.user and user_chat.user.id != self.user_id:
#                 receiver = user_chat.user
#                 receiver_type = "users"
#             elif user_chat.admin and user_chat.admin.id != self.user_id:
#                 receiver = user_chat.admin
#                 receiver_type = "admin"
#             elif user_chat.professional and user_chat.professional.id != self.user_id:
#                 receiver = user_chat.professional
#                 receiver_type = "professional"

#             if receiver:
#                 ChatNotifications.objects.create(
#                     receiver_content_type=ContentType.objects.get_for_model(receiver),
#                     receiver_object_id=receiver.id,
#                     sender_content_type=ContentType.objects.get_for_model(self.user),
#                     sender_object_id=self.user.id,
#                     message=f"New message in group: {chat.name}",
#                     notification_type="group_chat"
#                 )
                
#     def get_s3_url(self, file_field):
#         return file_field.url if file_field else None

#     def get_time_difference(self, created_at):
#         delta = timezone.now() - created_at
#         minutes = int(delta.total_seconds() // 60)
#         if minutes < 60:
#             return f"{minutes} min ago"
#         hours = minutes // 60
#         if hours < 24:
#             return f"{hours} hours ago"
#         days = hours // 24
#         return f"{days} days ago"


       
class GroupChatConsumer(AsyncWebsocketConsumer):
    
    def decode_base64_file(self, data):
        try:
            print("data", data)
            format, imgstr = data.split(';base64,')  
            ext = format.split('/')[-1]  
            filename = f"{uuid.uuid4()}.{ext}"
            return ContentFile(base64.b64decode(imgstr), name=filename)
        except Exception as e:
            print("Base64 decode error:", e)
            return None
    
    async def connect(self):
        query_string = self.scope["query_string"].decode()
        self.token = query_string.split("=")[-1]

        self.ticket_id = self.scope['url_route']['kwargs']['ticket_id']  
        print("--------------------------------  Ticket ID:", self.ticket_id)

        if not self.ticket_id:
            await self.close()
            return

        decoded = decode_token(self.token)

        if not decoded or decoded["type"] not in ["users", "admin", "professional"]:
            await self.close()
            return

        self.user_type = decoded["type"]
        self.user_id = decoded["id"]

        try:
            if self.user_type == "users":
                print("------------------------  User ID:", self.user_id)
                self.user = await sync_to_async(Users.objects.get)(id=self.user_id)
            elif self.user_type == "admin":
                print("---=================================Admin ID:", self.user_id)
                self.user = await sync_to_async(AdminUser.objects.get)(id=self.user_id)
            elif self.user_type == "professional":
                print("------------------------  Professional ID:", self.user_id)
                self.user = await sync_to_async(ProfessionalUser.objects.get)(id=self.user_id)
        except Exception as e:
            print("User fetch error:", e)
            await self.close()
            return

        self.room_group_name = f"ticket_{self.ticket_id}"
        print("Room group name:", self.room_group_name)

        ticket = await self.get_ticket(self.ticket_id)
        print("Ticket fetched:", ticket)
        if not ticket:
            await self.close()
            return

        #  Join WebSocket group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        #  Create or get chat for this ticket
        chat = await self.get_or_create_group_chat_by_name(ticket)
        print("Chat fetched:", chat)

        #  Get necessary users
        user = await sync_to_async(Users.objects.get)(id=ticket.created_by_user_id)
        print("User fetched:", user)
        
        admin = await sync_to_async(AdminUser.objects.first)()
        print("Admin fetched:", admin)
        is_specific_order = await sync_to_async(lambda: ticket.specific_order)()
        print("------------------------------specific_order:", is_specific_order)

        #  Always add the current user to chat
        await self.add_user_to_chat(chat, self.user)

        if is_specific_order:
        # ➤ If specific_order is TRUE → auto-add user, admin, professional
            if user:
                await self.add_user_to_chat(chat, user)
            if admin:
                await self.add_user_to_chat(chat, admin)
            try:
                professional_user = await sync_to_async(lambda: ticket.order.professional_user)()
                if professional_user:
                    await self.add_user_to_chat(chat, professional_user)
            except Exception as e:
                print("Error fetching professional for specific order:", e)
        else:
            # ➤ If specific_order is FALSE → only auto-add user and admin
            if self.user_type in ["users", "admin"]:
                if user:
                    await self.add_user_to_chat(chat, user)
                if admin:
                    await self.add_user_to_chat(chat, admin)

        #  Send chat history
        chat_history = await self.get_chat_history(page=1, page_size=20)
        await self.send(text_data=json.dumps({
            "chat_id": chat.id,
            "chat_history": chat_history
        }))


    # ⭐️ **Add this method to get ticket**
    @sync_to_async
    def get_ticket(self, ticket_id):
        from Admin.models import SupportTicket  # ⚠️ **CHANGE THIS IF Ticket IS IN ANOTHER APP**
        return SupportTicket.objects.filter(ticket_id=ticket_id).first()
    
    
    async def disconnect(self, close_code):
        # await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            if not text_data:
                return f"No data received"
            
            print("receive() triggered ")
            try:
                print("Received data:", text_data)
                data = json.loads(text_data)
                # message = data.get("message", "")
                # image = data.get("image")
                # video = data.get("video")
                if isinstance(data, dict): 
                    if data.get("type") == "pagination":
                        page = int(data.get("page", 1))
                        page_size = int(data.get("page_size", 10))
                        chat_history = await self.get_chat_history(page=page, page_size=page_size)
                        await self.send(text_data=json.dumps({
                            "chat_history": chat_history
                        }))
                        return
                    else:
                        message = data.get("message", "")
                        image = data.get("image")
                        print("---------11111111111111111---------------image:", image)
                        video = data.get("video")
                        print("---------22222222222222222---------------video:", video)
                        image = self.decode_base64_file(image) if image else None
                        print("------------------------image:", image)
                        video = self.decode_base64_file(video) if video else None
                        print("------------------------video:", video)
                else:
                    message = str(data)
                    
            except json.JSONDecodeError:
                message, image, video = text_data, None, None
                

            print("Received message:", message)
            msg = await self.save_message(message, image, video)
            
            
            sender_name = self.get_sender_name(
                ContentType.objects.get_for_model(self.user),
                self.user.id
            )
            print("===============jjjjjjjjjjjjjjj sender_name:", sender_name)  
            response = {
                "message": msg.content,
                "sender_id": msg.sender_object_id,
                "sender_name": sender_name,
                "sender_type": self.user_type,
                "chat_id": msg.chat.id,
                "image": self.get_s3_url(msg.image) if msg.image else None,
                "video": self.get_s3_url(msg.video) if msg.video else None,
                "message_type": "image" if msg.image else "video" if msg.video else "message",
                "created_at": self.get_time_difference(msg.created_at)
            }

            await self.channel_layer.group_send(self.room_group_name, {
                "type": "chat_message",
                "message": response
            })
        except Exception as e:
            print("Receive error:", e)
            
        
    async def chat_message(self, event):
        try:
            await self.send(text_data=json.dumps(event["message"]))
        except Exception as e:
            print(f"Error in chat_message: {e}")
            traceback.print_exc()

    @sync_to_async
    def get_or_create_group_chat_by_name(self, ticket):
        
        group_name = f"ticket_{ticket.ticket_id}"
        
        chat = Chat.objects.filter(is_group=True, name=group_name).first()
        if chat:
            return chat

        chat = Chat.objects.create(is_group=True, name=group_name)
        # Add current user to chat through UserChat
        user_model_name = self.user.__class__.__name__.lower()

        if user_model_name == 'users':
            UserChat.objects.create(user=self.user, chat=chat)
        elif user_model_name == 'adminuser':
            UserChat.objects.create(admin=self.user, chat=chat)
        elif user_model_name == 'professionaluser':
            UserChat.objects.create(professional=self.user, chat=chat)
        else:
            UserChat.objects.create(user=self.user, chat=chat)

        return chat

    @sync_to_async
    def add_user_to_chat(self, chat, user):
        print(f"Adding user {user.id} to chat {chat.id}")
        user_model_name = user.__class__.__name__.lower()

        exists = False
        if user_model_name == 'users':
            exists = UserChat.objects.filter(chat=chat, user=user).exists()
        elif user_model_name == 'adminuser':
            exists = UserChat.objects.filter(chat=chat, admin=user).exists()
        elif user_model_name == 'professionaluser':
            exists = UserChat.objects.filter(chat=chat, professional=user).exists()

        if not exists:
            if user_model_name == 'users':
                UserChat.objects.create(chat=chat, user=user)
            elif user_model_name == 'adminuser':
                UserChat.objects.create(chat=chat, admin=user)
            elif user_model_name == 'professionaluser':
                UserChat.objects.create(chat=chat, professional=user)

    def map_sender_type(self, model_name):
        if isinstance(model_name, str):
            model_name = model_name.lower()
        return {
            "users": "user",
            "adminuser": "admin",
            "professionaluser": "professional"
        }.get(model_name, model_name)

    @sync_to_async
    def get_chat_history(self,page=1, page_size=20):
        print(f"==============Fetching chat history for group: {self.room_group_name}")
        chat = Chat.objects.filter(is_group=True, name=self.room_group_name).first()
        
        if not chat:
            return {"results": [], "total_pages": 0, "current_page": 1, "has_next": False, "has_previous": False}

        messages = Message.objects.filter(chat=chat).order_by("created_at")
        paginator = Paginator(messages, page_size)
        page_obj = paginator.get_page(page)
        
        result = []
        for msg in messages:
            sender_name = self.get_sender_name(msg.sender_content_type, msg.sender_object_id)
            result.append({
                "message": msg.content,
                "sender_id": msg.sender_object_id,
                "sender_name": sender_name,
                "sender_type": self.map_sender_type(msg.sender_content_type.model) if msg.sender_content_type else None,
                "chat_id": msg.chat.id,
                "image": self.get_s3_url(msg.image) if msg.image else None,
                "video": self.get_s3_url(msg.video) if msg.video else None,
                "message_type": "image" if msg.image else "video" if msg.video else "message",
                "created_at": self.get_time_difference(msg.created_at)
            })
        return {
            "results": result[::-1], 
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous()
        }

    @sync_to_async
    def save_message(self, content, image=None, video=None):
        print(f"===============================Saving message: {content}")
        chat = Chat.objects.filter(is_group=True, name=self.room_group_name).first()
        if not chat:
            chat = Chat.objects.create(is_group=True, name=self.room_group_name)
        return Message.objects.create(
            chat=chat,
            sender_content_type=ContentType.objects.get_for_model(self.user),
            sender_object_id=self.user.id,
            content=content,
            image=image,
            video=video,
        )

    
    def get_sender_name(self, content_type, object_id):
        try:
            print("----------ooooooooooooooooo content_type:", content_type, "object_id:", object_id)
            model_class = content_type.model_class()
            model_name = model_class.__name__

            # Only use select_related if model has a relation to company
            if model_name == "ProfessionalUser":
                print("ProfessionalUser ---------")
                sender = model_class.objects.select_related('company').filter(id=object_id).first()
            else:
                print("Not ProfessionalUser ---------")
                sender = model_class.objects.filter(id=object_id).first()

            if not sender:
                return "Unknown"

            if model_name == "ProfessionalUser":
                print("ProfessionalUser ---------")
                # Return company name if it exists
                if sender.company and sender.company.companyName:
                    return sender.company.companyName
                return "Unknown"

            elif model_name == "AdminUser":
                print("AdminUser ---------")
                return sender.name or "Unknown"

            elif model_name == "Users":
                print("Users ---------")
                full_name = f"{sender.firstName} {sender.lastName}".strip()
                return full_name if full_name else "Unknown"

            return str(sender)

        except Exception as e:
            print("Error in get_sender_name:", e)
            return "Unknown"
   
                
    def get_s3_url(self, file_field):
        return file_field.url if file_field else None

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


