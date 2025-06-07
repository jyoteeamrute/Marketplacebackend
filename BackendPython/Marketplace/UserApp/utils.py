import json
import math
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.utils import timezone


def haversine_distance(lat1, lon1, lat2, lon2):
    try:
        if None in (lat1, lon1, lat2, lon2):
            return None

        lat1 = float(lat1)
        lon1 = float(lon1)
        lat2 = float(lat2)
        lon2 = float(lon2)

        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        return round(distance)
    except (TypeError, ValueError):
        return None


def get_company_status(company):
    now = timezone.localtime()
    current_day = now.strftime("%A").lower()
    current_time = now.time()

    hours = getattr(company, 'opening_hours', None)
    if not hours:
        return "closed"

    if isinstance(hours, str):
        try:
            hours = json.loads(hours)
        except json.JSONDecodeError:
            return "closed"

    if not isinstance(hours, dict):
        return "closed"

    day_hours = hours.get(current_day)
    if not day_hours:
        return "closed"

    start_str = day_hours.get("start_time")
    end_str = day_hours.get("end_time")

    if not start_str or not end_str:
        return "closed"

    try:
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
    except ValueError:
        return "closed"
    today = now.date()
    start_dt = timezone.make_aware(datetime.combine(today, start_time))
    end_dt = timezone.make_aware(datetime.combine(today, end_time))
    current_dt = now
    CLOSING_SOON_THRESHOLD = timedelta(minutes=45) 
  
    if start_dt <= current_dt <= end_dt:
        if (end_dt - current_dt) <= CLOSING_SOON_THRESHOLD:
            return "closing soon"
        return "open"
    elif current_dt < start_dt:
        return "opening soon"

    return "closed"

def calculate_discount(product):
    try:
        if not product.promotionalPrice or not product.vatRate:
            return None
        
        original_price = float(product.vatRate)
        discounted_price = float(product.promotionalPrice)

        if original_price == 0:
            return None  # avoid division by zero

        discount = ((original_price - discounted_price) / original_price) * 100
        return int(discount)  # Return as whole number (e.g., 50)
    
    except Exception:
        return None


def calculate_discountService(service):
    try:
        if not service.priceOnsite or not service.vatRate:
            return None
        
        original_price = float(service.vatRate)
        discounted_price = float(service.priceOnsite)

        if original_price == 0:
            return None  # avoid division by zero

        discount = ((original_price - discounted_price) / original_price) * 100
        return int(discount)  # Return as whole number (e.g., 50)
    
    except Exception:
        return None



def format_opening_hours(opening_hours):
    if not opening_hours or not isinstance(opening_hours, dict):  # Check if None or not a dict
        return []

    day_mapping = {
        "monday": "Mon",
        "tuesday": "Tues",
        "wednesday": "Wed",
        "thursday": "Thur",
        "friday": "Fri",
        "saturday": "Sat",
        "sunday": "Sun"
    }

    formatted_hours = []

    for day, hours in opening_hours.items():
        if not isinstance(hours, dict):  # Ensure `hours` is a dictionary
            continue

        start_time = hours.get('start_time')
        end_time = hours.get('end_time')

        if start_time and end_time:
            if hasattr(start_time, 'strftime') and hasattr(end_time, 'strftime'):
                formatted_hours.append({
                    "day": day_mapping.get(day.lower(), day.capitalize()),
                    "hours": f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"
                })
            else:
                formatted_hours.append({
                    "day": day_mapping.get(day.lower(), day.capitalize()),
                    "hours": f"{start_time} - {end_time}"  # fallback if strings
                })
    day_order = ["Mon", "Tues", "Wed", "Thur", "Fri", "Sat", "Sun"]
    formatted_hours.sort(key=lambda x: day_order.index(x["day"]) if x["day"] in day_order else len(day_order))

    return formatted_hours





def default_image_url(folder_name):
    return f"https://markerplacemobileapp.s3.us-east-1.amazonaws.com/product_images/1_Food__Drink.jpg"




def get_date_range(start_datetime, end_datetime):
    if start_datetime and end_datetime:
        start_date = start_datetime.date()
        end_date = end_datetime.date()
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        delta = end_date - start_date
        return [{"date": (start_date + timedelta(days=i)).strftime("%d %b")} for i in range(delta.days + 1)]
    return []


from django.core.management.base import BaseCommand

from ProfessionalUser.models import eventBooking


class Command(BaseCommand):
    help = 'Delete unpaid event bookings after 5 minutes'

    def handle(self, *args, **kwargs):
        five_minutes_ago = timezone.now() - timedelta(minutes=5)
        expired = eventBooking.objects.filter(is_paid=False, created_at__lt=five_minutes_ago)
        count = expired.count()
        expired.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} unpaid bookings older than 5 minutes."))


def get_slot_start_times(start_time, end_time, duration_minutes):
                if not all([start_time, end_time, duration_minutes]):
                    return []
                dummy_date = datetime.today().date()
                current = datetime.combine(dummy_date, start_time)
                end = datetime.combine(dummy_date, end_time)

                slots = []
                while current + timedelta(hours=duration_minutes) <= end:
                    slots.append(current.strftime('%I:%M %p'))  # Format: 09:00 AM
                    current += timedelta(hours=duration_minutes)

                return slots


def format_date(dt):
        return dt.strftime("%d %b %Y") if dt else None

def format_time(dt):
        return dt.strftime("%I:%M %p") if dt else None



import requests


def send_push_to_user_tag(matched_player_ids, content):

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






def get_player_ids_by_user_id(user_id,content):
    url = "https://onesignal.com/api/v1/players"
    headers = {
        "Authorization": f"Basic {settings.ONESIGNAL_USER_API_KEY}"  
    }
    params = {
        "app_id": settings.ONESIGNAL_USER_APP_ID,
        "limit": 500  
    }

    matched_player_ids = []

    while True:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            break

        data = response.json()
        for player in data.get("players", []):
            tags = player.get("tags", {})
            if tags.get("userID") == str(user_id):
                matched_player_ids.append(player["id"])

        if not data.get("players") or not data.get("offset"):
            break  # No more data
        params["offset"] = data["offset"]

    if matched_player_ids:
        return send_push_to_user_tag(matched_player_ids, content)
    else:
        print("No matching player IDs found.")
    
    return 

