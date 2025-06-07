from UserApp.serializers import UserSerializer
from rest_framework import serializers
from .models import *


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "chat", "sender", "content", "image", "video", "created_at"]
        read_only_fields = ['sender', 'created_at']

class ChatSerializer(serializers.ModelSerializer):
    users = UserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = ["id", "users", "created_at", "last_message"]

    def get_last_message(self, obj):
        last = obj.messages.order_by("-created_at").first()
        return MessageSerializer(last).data if last else None

class UserChatSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    chat = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = UserChat
        fields = ["id", "user", "chat", "joined_at"]


class ChatGroupSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = ['id', 'participants', 'created_at']

    def get_participants(self, obj):
        participants = []

        # From UserChat table
        user_chats = UserChat.objects.filter(chat=obj)

        for entry in user_chats:
            if entry.user:
                participants.append({
                    "id": entry.user.id,
                    "username": entry.user.username,
                    "type": "user"
                })
            if entry.admin:
                participants.append({
                    "id": entry.admin.id,
                    "username": entry.admin.username,
                    "type": "admin"
                })

        # From receiver_type / receiver_id on the Chat model (e.g. professional user)
        if obj.receiver_type == "professional":
            try:
                prof = ProfessionalUser.objects.get(id=obj.receiver_id)
                participants.append({
                    "id": prof.id,
                    "username": prof.username,  # or prof.name or prof.full_name
                    "type": "professional"
                })
            except ProfessionalUser.DoesNotExist:
                pass

        return participants
    
    
    
class ChatNotificationsSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    receiver = serializers.SerializerMethodField()

    class Meta:
        model = ChatNotifications
        fields = [
            "id",
            "message",
            "notification_type",
            "is_read",
            "created_at",
            "sender",
            "receiver",
        ]

    def get_sender(self, obj):
        # Return a simple representation of sender (e.g. id and type)
        return {
            "id": obj.sender_object_id,
            "type": obj.sender_content_type.model
        }

    def get_receiver(self, obj):
        return {
            "id": obj.receiver_object_id,
            "type": obj.receiver_content_type.model
        }