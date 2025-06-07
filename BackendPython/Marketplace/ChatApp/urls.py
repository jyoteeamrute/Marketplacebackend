from django.urls import path
from .views import *

urlpatterns = [
    # path('register/', RegisterView.as_view(), name='user-register')
    path('chatapp-upload-media/', UploadMediaAPIView.as_view(), name='upload-media'),
    # path('chatapp-get-chat-history/', ChatMessageAPIView.as_view(), name='get-chat-history'),
    path('chatapp-block-unblock-users/', ToggleBlockUserByChatIDAPIView.as_view(), name='bloack-user'),    
    path('chatapp-report-users/', ReportUserByChatIDAPIView.as_view(), name='report-user'),
    path('chatapp-clear-chats-per-users/', ClearChatAPIView.as_view(), name='clear-chats-per-users'),
    path('chatapp-get-group-chats/', GroupChatMessageAPIView.as_view(), name='get-group-all-chats'),
    path('chatapp-get-notifications/', NotificationsListAPIView.as_view(), name='notifications-list'),
    path('chatapp-add-professional-to-chat/', AddProfessionalToChatAPIView.as_view(), name='add-professional-chat'),
    path('chatapp-share-reels-in-chats/', ShareReelAPIView.as_view(), name='get-share-reels-chats'),
    path('chatapp-share-profile/', ShareProfileAPIView.as_view(), name='get-share-profile-chat'),
    
]