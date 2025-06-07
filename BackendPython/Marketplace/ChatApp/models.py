from django.db import models
from UserApp.models import Users
from Admin.models import AdminUser
from ProfessionalUser.models import ProfessionalUser,StoreReel
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

# Create your models here.


class Chat(models.Model):
    
    ticket_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True)
    is_group = models.BooleanField(default=False)
    users = models.ManyToManyField(Users, through='UserChat')  # Many-to-many relationship through UserChat
    professional_user = models.ForeignKey(ProfessionalUser, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    receiver_type = models.CharField(max_length=20, null=True, blank=True)  # e.g., 'user' or 'professional'
    receiver_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Chat #{self.id} ({self.name})"

class UserChat(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE,null=True, blank=True)  # the regular user
    professional = models.ForeignKey(ProfessionalUser, null=True, blank=True, on_delete=models.CASCADE)
    admin = models.ForeignKey(AdminUser, on_delete=models.CASCADE, null=True, blank=True)  # the admin user
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)  # the chat room
    joined_at = models.DateTimeField(auto_now_add=True)

    # class Meta:
    #     unique_together = ('user', 'admin', 'chat')  # you can also expand this to ('user', 'chat', 'admin') if needed
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['chat', 'user'], name='unique_user_per_chat'),
            models.UniqueConstraint(fields=['chat', 'professional'], name='unique_professional_per_chat'),
            models.UniqueConstraint(fields=['chat', 'admin'], name='unique_admin_per_chat'),
        ]

    def __str__(self):
        return f"{self.user} in {self.chat.name}"


# models.py
class Message(models.Model):
    chat = models.ForeignKey(Chat, related_name="messages", on_delete=models.CASCADE)
    # sender = models.ForeignKey(Users, on_delete=models.CASCADE)
    sender_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    sender_object_id = models.PositiveIntegerField(null=True, blank=True)
    sender = GenericForeignKey('sender_content_type', 'sender_object_id')
    content = models.TextField(blank=True)  # Optional for media-only messages
    image = models.ImageField(upload_to='chat_images/', blank=True, null=True)
    video = models.FileField(upload_to='chat_videos/', blank=True, null=True)
    reels = models.ForeignKey(StoreReel, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def sender_display_name(self):
        # Return a safe display name for the sender regardless of type
        if not self.sender:
            return "Unknown sender"
        if hasattr(self.sender, 'username'):
            return self.sender.username
        elif hasattr(self.sender, 'name'):
            return self.sender.name
        else:
            return str(self.sender)

    def __str__(self):
        return f"Message from {self.sender_display_name()} at {self.created_at}"

    class Meta:
        ordering = ['created_at']  # Ensures messages ordered oldest to newest by default




#models for Professional User - Admin

class ProChat(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

class ProUserChat(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, null=True, blank=True)
    professional_user = models.ForeignKey(ProfessionalUser, on_delete=models.CASCADE, null=True, blank=True)
    chat = models.ForeignKey(ProChat, on_delete=models.CASCADE, null=True,blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'professional_user', 'chat')

class ProMessage(models.Model):
    chat = models.ForeignKey(ProChat, on_delete=models.CASCADE)
    sender_user = models.ForeignKey(Users, null=True, blank=True, on_delete=models.CASCADE)  # Sender could be UserApp user
    sender_professional = models.ForeignKey(ProfessionalUser, null=True, blank=True, on_delete=models.CASCADE)  # Or ProfessionalUser
    content = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='pro_chat_images/', blank=True, null=True)
    video = models.FileField(upload_to='pro_chat_videos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    
class BlockedUser(models.Model):
    blocked_by = models.ForeignKey(Users, related_name='blocked_users', on_delete=models.CASCADE, null=True, blank=True)
    blocked_by_professional = models.ForeignKey(ProfessionalUser, related_name='blocked_professionals', on_delete=models.CASCADE, null=True, blank=True)
    blocked_user = models.ForeignKey(Users, related_name='blocked_by_users', on_delete=models.CASCADE, null=True, blank=True)
    blocked_user_professional = models.ForeignKey(ProfessionalUser, related_name='blocked_by_professionals', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (
            ('blocked_by', 'blocked_user'),
            ('blocked_by_professional', 'blocked_user_professional'),
        )

    def __str__(self):
        return f"{self.blocked_by} blocked {self.blocked_user}"


class ReportedUser(models.Model):
    report_by_user = models.ForeignKey(Users,related_name='report_user', null=True, blank=True, on_delete=models.CASCADE)
    report_by_professional = models.ForeignKey(ProfessionalUser,related_name='report_professional', null=True, blank=True, on_delete=models.CASCADE)
    reported_user = models.ForeignKey(Users,related_name='report_by_user', null=True, blank=True, on_delete=models.CASCADE)
    reported_professional = models.ForeignKey(ProfessionalUser, null=True, related_name='report_by_professional', blank=True, on_delete=models.CASCADE)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report by {self.report_by_user or self.report_by_professional} → {self.reported_user or self.reported_professional}"

class ChatHistoryHide(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, null=True, blank=True)
    professional = models.ForeignKey(ProfessionalUser, on_delete=models.CASCADE, null=True, blank=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    hidden_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'professional')
        



class ChatNotifications(models.Model):
    receiver_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="notification_receiver_type")
    receiver_object_id = models.PositiveIntegerField()
    receiver = GenericForeignKey('receiver_content_type', 'receiver_object_id')

    sender_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, related_name="notification_sender_type")
    sender_object_id = models.PositiveIntegerField()
    sender = GenericForeignKey('sender_content_type', 'sender_object_id')

    message = models.TextField()
    notification_type = models.CharField(max_length=50)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
