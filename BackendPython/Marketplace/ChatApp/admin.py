from django.contrib import admin

from django.contrib import admin
from ChatApp.models import *


@admin.register(UserChat)
class UserChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'user', 'professional', 'admin', 'joined_at')
    search_fields = ('chat__name', 'user__username', 'professional__name', 'admin__name')
    list_filter = ('joined_at',)    


class UserChatInline(admin.TabularInline):
    model = UserChat
    extra = 0

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'get_participants', 'created_at')
    inlines = [UserChatInline]

    def get_participants(self, obj):
        participants = []
        for uc in obj.userchat_set.all():
            if uc.user:
                participants.append(f'User: {uc.user.username}')
            if uc.professional:
                participants.append(f'Professional: {uc.professional.email}')
            if uc.admin:
                participants.append(f'Admin: {uc.admin.name}')
        return ", ".join(participants)

    get_participants.short_description = "Participants"

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'sender_display_name', 'content', 'created_at', 'is_read')
    search_fields = ('content',)
    list_filter = ('created_at', 'is_read')
    readonly_fields = ('sender_display_name',)

    def sender_display_name(self, obj):
        return obj.sender_display_name()

    sender_display_name.short_description = 'Sender'
  

@admin.register(BlockedUser)
class BlockedUserAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'get_blocked_by', 'get_blocked_by_id',
        'get_blocked_user', 'get_blocked_user_id',
        'created_at'
    )
    list_filter = ('created_at',)
    search_fields = (
        'blocked_by__username', 'blocked_user__username',
        'blocked_by_professional__username', 'blocked_user_professional__username'
    )

    def get_blocked_by(self, obj):
        return obj.blocked_by or obj.blocked_by_professional
    get_blocked_by.short_description = 'Blocked By'

    def get_blocked_by_id(self, obj):
        user = obj.blocked_by or obj.blocked_by_professional
        return user.id if user else None
    get_blocked_by_id.short_description = 'Blocked By ID'

    def get_blocked_user(self, obj):
        return obj.blocked_user or obj.blocked_user_professional
    get_blocked_user.short_description = 'Blocked User'

    def get_blocked_user_id(self, obj):
        user = obj.blocked_user or obj.blocked_user_professional
        return user.id if user else None
    get_blocked_user_id.short_description = 'Blocked User ID'
    
@admin.register(ReportedUser)
class ReportedUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_reported_by', 'get_reported_user', 'reason', 'created_at')
    list_filter = ('created_at',)
    search_fields = (
        'report_by_user__username',
        'report_by_professional__company_name',
        'reported_user__username',
        'reported_professional__company_name',
        'reason',
    )

    def get_reported_by(self, obj):
        return obj.report_by_user or obj.report_by_professional
    get_reported_by.short_description = 'Reported By'

    def get_reported_user(self, obj):
        return obj.reported_user or obj.reported_professional
    get_reported_user.short_description = 'Reported User'
    
@admin.register(ChatHistoryHide)
class ChatHistoryHideAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_user_or_professional', 'message', 'hidden_at')
    list_filter = ('hidden_at',)
    search_fields = (
        'user__username',
        'professional__company_name',
        'message__message',  
    )

    def get_user_or_professional(self, obj):
        return obj.user or obj.professional
    get_user_or_professional.short_description = 'Hidden By'
    
    
@admin.register(ChatNotifications)
class ChatNotificationsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "receiver",
        "sender",
        "message",
        "notification_type",
        "is_read",
        "created_at",
    )
    list_filter = ("is_read", "notification_type", "created_at")
    search_fields = ("message", "notification_type")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    fieldsets = (
        (None, {
            "fields": (
                "receiver_content_type",
                "receiver_object_id",
                "sender_content_type",
                "sender_object_id",
                "message",
                "notification_type",
                "is_read",
                "created_at",
            )
        }),
    )