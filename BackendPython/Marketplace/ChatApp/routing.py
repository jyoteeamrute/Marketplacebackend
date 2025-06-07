from django.urls import re_path
from ChatApp.consumers import *

websocket_urlpatterns = [
    re_path(r'ws/flexchat/(?P<receiver_id>\d+)/(?P<receiver_type>\w+)/$', FlexibleChatConsumer.as_asgi()),
    re_path(r"ws/chat/group-list/$", ChatGroupListConsumer.as_asgi()),
    re_path(r"^ws/chat/(?P<receiver_type>\w+)/(?P<receiver_id>\d+)/$", ChatConsumer.as_asgi()),
    re_path(r"^ws/chat/(?P<receiver_type>\w+)/$", ChatConsumer.as_asgi()),
    re_path(r"^ws/chat/group/(?P<chat_id>\d+)/$", ChatConsumer.as_asgi()),
    re_path(r"ws/groupchat/ticket/(?P<ticket_id>[\w\-]+)/$", GroupChatConsumer.as_asgi())

    
]
