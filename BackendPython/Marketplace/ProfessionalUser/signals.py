from django.db.models.signals import post_save
from django.dispatch import receiver

from Marketplace import settings

from .models import Inventory, Product


@receiver(post_save, sender=Product)
def create_inventory(sender, instance, created, **kwargs):
    """Automatically creates an inventory when a new product is created."""
    
    if created:  #  This runs only when a new product is created
        Inventory.objects.create(
            product=instance,
            company=instance.company, 
            stock_quantity=instance.quantity,  
            medium_stock_threshold=10,  
            low_stock_threshold=5
        )
        
@receiver(post_save, sender=Inventory)
def update_product_stock(sender, instance, **kwargs):
    """Update the Product quantity when Inventory stock_quantity changes."""
    if instance.product:
        instance.product.quantity = instance.stock_quantity
        instance.product.save()
import re

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework import status
from rest_framework.response import Response

from UserApp.models import Users

from .models import Notification, ReelComment


@receiver(post_save, sender=ReelComment)
def send_notification(sender, instance, created, **kwargs):
    if not created:
        return

    mentioned_usernames = re.findall(r'@(\w+)', instance.comment)


    for username in mentioned_usernames:
        try:
            mentioned_user = Users.objects.get(username=username)
      

            message = f"{instance.user.username} mentioned you in a comment on a reel."
            notification = Notification.objects.create(
                user=mentioned_user,
                sender=instance.user,
                message=message,
                notification_type="comment"
            )

            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                f"user_{mentioned_user.id}_notifications",  # Group name
                {
                    "type": "send_notification",  # Method name to handle the data in the consumer
                    "notification": {
                        "id": notification.id,
                        "message": notification.message,
                        "timestamp": str(notification.created_at),
                        "sender": notification.sender.username,
                        "notification_type": notification.notification_type,
                    }
                }
            )

        except Users.DoesNotExist:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": f"User {username} not found for notification."
            }, status=status.HTTP_200_OK)



import requests


def send_push_to_professional_tag(matched_player_ids, content):

    url = "https://api.onesignal.com/notifications?c=push"

    payload = {
        "app_id": settings.ONESIGNAL_USER_APP_ID,
        "contents": { "en": content },
        "include_player_ids": matched_player_ids
    }
   
    headers = {
        "accept": "application/json",
        "Authorization": settings.ONESIGNAL_USER_API_KEY,
        "content-type": "application/json"
    }

    
    response = requests.post(url, json=payload, headers=headers)

 






def get_player_ids_by_professional_id(pro_user_id,content):
    url = "https://onesignal.com/api/v1/players"
    headers = {
        "Authorization": f"Basic {settings.ONESIGNAL_PRO_API_KEY}"  # Use REST API Key (not user auth key)
    }
    params = {
        "app_id": settings.ONESIGNAL_PRO_APP_ID,
        "limit": 400  
    }
 
    matched_player_ids = []
 
    while True:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            break
 
        data = response.json()
        for player in data.get("players", []):
            tags = player.get("tags", {})
            if tags.get("userID") == str(pro_user_id):
                matched_player_ids.append(player["id"])
 
        if not data.get("players") or not data.get("offset"):
            break  # No more data
        params["offset"] = data["offset"]

    print("=======================",matched_player_ids)    
    if matched_player_ids:
        return send_push_to_professional_tag(matched_player_ids, content)
    else:
        print("No matching player IDs found.")
        
    return




# -------------------------Admin-Notifications-------------------------------

from Admin.models import AdminNotification  # Ensure correct path
from ProfessionalUser.models import ProfessionalUser
from UserApp.models import Users


def send_admin_notification(content, title="Admin Alert", notification_type="custom", user=None, professional_user=None):
    player_ids = get_admin_player_ids()
    
    # Save to DB
    AdminNotification.objects.create(
        title=title,
        message=content,
        notification_type=notification_type,
        user=user,
        professional_user=professional_user
    )

    if not player_ids:
        print("No admin player IDs found.")
        return

    payload = {
        "app_id": settings.ONESIGNAL_USER_APP_ID,
        "contents": { "en": content },
        "headings": { "en": title },
        "include_player_ids": player_ids
    }

    headers = {
        "accept": "application/json",
        "Authorization": settings.ONESIGNAL_USER_API_KEY,
        "content-type": "application/json"
    }

    response = requests.post("https://api.onesignal.com/notifications?c=push", json=payload, headers=headers)
    print(f"Push sent to admin(s): {response.status_code} {response.text}")


def get_admin_player_ids():
    url = "https://onesignal.com/api/v1/players"
    headers = {
        "Authorization": f"Basic {settings.ONESIGNAL_PRO_API_KEY}"  # Use REST API Key
    }
    params = {
        "app_id": settings.ONESIGNAL_PRO_APP_ID,
        "limit": 400
    }

    matched_player_ids = []
    while True:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            break

        data = response.json()
        for player in data.get("players", []):
            tags = player.get("tags", {})
            if tags.get("admin") == "true":  # Assumes admin users are tagged in OneSignal
                matched_player_ids.append(player["id"])

        if not data.get("players") or not data.get("offset"):
            break
        params["offset"] = data["offset"]

    return matched_player_ids





def on_support_ticket_created(ticket):
    username = ""
    user_instance = None
    professional_user_instance = None

    if ticket.type_of_user == "user" and ticket.created_by_user_id:
        user_instance = Users.objects.filter(id=ticket.created_by_user_id).first()
        if user_instance:
            username = user_instance.username

    elif ticket.type_of_user == "professionaluser" and ticket.created_by_user_id:
        professional_user_instance = ProfessionalUser.objects.filter(id=ticket.created_by_user_id).first()
        if professional_user_instance:
            username = professional_user_instance.userName

    content = f"New support ticket raised by {username or 'Unknown User'}: {ticket.subject}"
    
    send_admin_notification(
        content,
        title="Support Ticket",
        user=user_instance,
        professional_user=professional_user_instance,
        notification_type="support_ticket"
    )

# When a new professional registers
def on_new_professional_registered(pro_user):
    content = f"New professional registered: {pro_user.company.companyName}."
    send_admin_notification(
        content,
        title="New Professional Registration",
        notification_type="registration_pro",
        professional_user=pro_user
    )




# When a user uploads verification document
def on_document_uploaded(user):
    content = f"{user.username} uploaded a new document for verification."
    send_admin_notification(
        content,
        title="Document Upload",
        notification_type="document_upload",
        user=user
    )

# When a reel is reported
def on_reel_reported(reel_report):
    content = f"Reel reported by {reel_report.user.username}: {reel_report.reason}"
    send_admin_notification(
        content,
        title="Reel Report",
        notification_type="reel_report",
        user=reel_report.user
    )

# When a new regular user registers
def on_new_user_registered(user):
    content = f"New user registered: {user.username}."
    send_admin_notification(
        content,
        title="New User Registration",
        notification_type="registration_user",
        user=user
    )


