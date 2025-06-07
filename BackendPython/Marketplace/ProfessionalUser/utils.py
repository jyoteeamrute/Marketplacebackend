import math
import random
from datetime import datetime, timedelta, timezone
import os, tempfile, shutil
import logging
import json
import pytz
from babel.numbers import get_currency_symbol
from django.utils.timezone import now
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def generate_otp():
    return str(random.randint(1000, 9999))


def send_email(email, data):
    print(f"Mock Email Sent to {email}: Your OTP is {data['otp']}")
    return True 

def send_sms(phone, otp):
    print(f"Mock SMS Sent to {phone}: Your OTP is {otp}")
    return True, "mock-sms-id"
import subprocess

import boto3
from django.conf import settings

s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_S3_REGION_NAME
)


def get_presigned_url(s3_key):
    """Generate a pre-signed URL to download the video."""
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=3600
        )
        return url
    except Exception as e:
        return None

def get_video_resolution(video_url):
    """Use ffprobe to get width and height of the input video."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json", video_url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    width = info['streams'][0]['width']
    height = info['streams'][0]['height']
    return width, height

def calculate_scaled_resolution(orig_width, orig_height, target_height):
    aspect_ratio = orig_width / orig_height
    new_width = int(round(target_height * aspect_ratio / 2) * 2)  # make even
    return new_width, target_height

def convert_video_to_m3u8(video_url, output_s3_folder):
    
    logger.info(f"Converting video {video_url} to HLS format")
    
    temp_dir = tempfile.mkdtemp()

    try:
        orig_width, orig_height = get_video_resolution(video_url)
    except Exception as e:
        logger.error(f"Error getting video resolution: {e}")
        return None, None

    resolutions = [360, 480, 720]
    renditions = []
    for h in resolutions:
        w, h = calculate_scaled_resolution(orig_width, orig_height, h)
        renditions.append({
            "name": f"{h}p",
            "scale": f"{w}:{h}",
            "bitrate": f"{int(h*2)}k",
            "maxrate": f"{int(h*2.14)}k",
            "bufsize": f"{int(h*3)}k"
        })

    master_playlist_path = os.path.join(temp_dir, "master.m3u8")
    variant_playlists = []

    for r in renditions:
        m3u8_filename = f"{r['name']}.m3u8"
        ts_pattern = os.path.join(temp_dir, f"{r['name']}_%03d.ts")
        m3u8_path = os.path.join(temp_dir, m3u8_filename)

        ffmpeg_cmd = [
            "ffmpeg", "-i", video_url,
            "-vf", f"scale={r['scale']}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", r["bitrate"],
            "-maxrate", r["maxrate"],
            "-bufsize", r["bufsize"],
            "-g", "48",
            "-keyint_min", "48",
            "-sc_threshold", "0",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "44100",
            "-ac", "2",
            "-hls_time", "4",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", ts_pattern,
            "-f", "hls",
            m3u8_path,
            "-y"
        ]

        try:
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True, text=True, timeout=180)
            variant_playlists.append((m3u8_filename, r["bitrate"].replace('k', ''), r["scale"]))
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed for {r['name']}: {e.stderr}")
            return None, None

    # Create master.m3u8
    try:
        with open(master_playlist_path, "w") as master:
            master.write("#EXTM3U\n")
            for filename, bandwidth, scale in variant_playlists:
                resolution = scale.replace(':', 'x')
                master.write(f"#EXT-X-STREAM-INF:BANDWIDTH={int(bandwidth)*1000},RESOLUTION={resolution}\n")
                master.write(f"{filename}\n")
    except Exception as e:
        logger.error(f"Failed to create master playlist: {e}")
        return None, None

    return temp_dir, "master.m3u8"



# def upload_m3u8_and_ts(output_dir, s3_folder):
#     """Upload M3U8 and TS files to S3."""
#     uploaded_files = []
    
#     if not os.path.exists(output_dir):
#         logger.error(f"Output directory does not exist: {output_dir}")
#         return uploaded_files
    
#     files_to_upload = os.listdir(output_dir)
#     logger.info(f"Found {len(files_to_upload)} files to upload")
    
#     for file in files_to_upload:
#         local_path = os.path.join(output_dir, file)
        
#         if not os.path.isfile(local_path):
#             continue
            
#         s3_key = os.path.join(s3_folder, file).replace("\\", "/")
        
#         try:
#             url = upload_to_s3(local_path, s3_key)
#             if url:
#                 uploaded_files.append(url)
#                 logger.info(f"Uploaded: {file}")
#             else:
#                 logger.error(f"Failed to upload: {file}")
#         except Exception as e:
#             logger.error(f"Error uploading {file}: {e}")
    
#     logger.info(f"Successfully uploaded {len(uploaded_files)} files")
#     return uploaded_files



def upload_to_s3(local_path, s3_key):
    """Upload a file to S3 and return the correct URL."""
    try:
        s3_client.upload_file(local_path, settings.AWS_STORAGE_BUCKET_NAME, s3_key, ExtraArgs={'ACL': 'public-read'})
        base_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
        return f"{base_url}/{s3_key}"
    
    except Exception as e:
        return None




def generate_thumbnail(video_url, output_path):
    """Extract a thumbnail from the video at 5 seconds."""
    ffmpeg_cmd = ["ffmpeg", "-y", "-i", video_url, "-ss", "00:00:05", "-vframes", "1", output_path]
    try:
        subprocess.run(ffmpeg_cmd, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        return None



def get_file_url(file_field):
    return file_field.url if file_field and hasattr(file_field, 'url') else None

def generate_user_response(user, refresh, access_token, message):
    if user.subscription_status.lower() == "trial" and not user.is_free_trial_active :
        subscription_message="your free trial has expired"
    elif user.subscription_status.lower() == "trial" and user.is_free_trial_active:
        subscription_message="your 3 month free trial is still active"
    elif user.subscription_status.lower() == "paid" and user.is_paid_subscription_active:
        subscription_message="your paid subscription is still active"
    elif user.subscription_status.lower() == "paid" and not user.is_paid_subscription_active:
        subscription_message="your paid subscription has expired please renew it or buy new one..."  
    else:
        subscription_message="your subscription is not active choose any subcription"
    if user.stripe_customer_id:
        customerId= user.stripe_customer_id
    else:
        customerId=""
                
    return Response({
                "statusCode": 200,
                "status": True,
                "message": message,
                "refresh_token": str(refresh),
                "access_token": access_token,
                "user": {
                    "email": user.email,
                    "phone": user.phone,
                    "id":user.id,
                    "customerId":customerId,
                    "subscription_status":user.subscription_status,
                    "is_subscription_active": user.subscription_active,
                    "subscription_message":subscription_message,
                    "is_free_trial_active":user.is_free_trial_active,
                    "is_paid_subscription_active":user.is_paid_subscription_active,
                    "role": str(user.role),
                    "is_verified": user.is_verified,
                    "finalDocument_status":user.finalDocument_status,
                    "Subscription": user.subscriptionplan.name if user.subscriptionplan else None,
                    "company": {
                        "companyID":user.company.id if user.company else None,
                        "companyName": user.company.companyName if user.company else None,
                        "managerFullName": user.company.managerFullName if user.company else None,
                        "phoneNumber": user.company.phoneNumber if user.company else None,
                        "email": user.company.email if user.company else None,
                        "siret": user.company.siret if user.company else None,
                        "sectorofActivity": user.company.sectorofActivity if user.company else None,
                        "vatNumber": user.company.vatNumber if user.company else None,
                        "iban": get_file_url(user.company.iban),
                        "kbiss": get_file_url(user.company.kbiss),
                        "identityCardFront": get_file_url(user.company.identityCardFront),
                        "identityCardBack": get_file_url(user.company.identityCardBack),
                        "proofOfAddress": get_file_url(user.company.proofOfAddress),
                        "profilePhoto": get_file_url(user.company.profilePhoto),
                        "coverPhotos": get_file_url(user.company.coverPhotos),
                    } if user.company else None,
                      "categoryID": [
                            {
                                "id": category.id,
                                "name": category.name
                            }
                            for category in user.categories.all()
                        ],
                        "subcategoriesID": [
                            {
                                "id": subcategory.id,
                                "name": subcategory.name,
                                "category_id": subcategory.parentCategoryId.id if subcategory.parentCategoryId else None
                            }
                            for subcategory in user.subcategories.all()
                        ],
                    "category":{
                        "subscriptionPlan":user.subscriptionplan.name if user.subscriptionplan else None,
                        "limit":user.subscriptionplan.category_limit if user.subscriptionplan else None,
                    },
                    "Subcategory":{
                        "limit":user.subscriptionplan.subcategory_limit if user.subscriptionplan else None,
                    },
                    "manual_address": {
                        "address1": user.manual_address.address1 if user.manual_address else None,
                        "address2": user.manual_address.address2 if user.manual_address else None,
                        "postalCode": user.manual_address.postalCode if user.manual_address else None,
                        "lat": user.manual_address.lat if user.manual_address else None,
                        "lang": user.manual_address.lang if user.manual_address else None,
                        "city": user.manual_address.city if user.manual_address else None,
                        "country": user.manual_address.country if user.manual_address else None
                    } if user.manual_address else None,
                    "automatic_address": {
                        "address1": user.automatic_address.address1 if user.automatic_address else None,
                        "address2": user.automatic_address.address2 if user.automatic_address else None,
                        "postalCode": user.automatic_address.postalCode if user.automatic_address else None,
                        "lat": user.automatic_address.lat if user.automatic_address else None,
                        "lang": user.automatic_address.lang if user.automatic_address else None,
                        "city": user.automatic_address.city if user.automatic_address else None,
                        "country": user.automatic_address.country if user.automatic_address else None
                    } if user.automatic_address else None
                }
            })


def get_company_status(company):
    """
    Determines whether the company is 'Open', 'Closing Soon', or 'Closed' based on France's timezone.
    """
    france_tz = pytz.timezone('Europe/Paris')  # France timezone
    current_time = now().astimezone(france_tz).time()  # Convert UTC to France local time
    current_day = now().astimezone(france_tz).strftime('%A').lower()  # Get today's day in lowercase

    opening_hours = company.opening_hours  # Fetch opening hours JSON field
    
    if not opening_hours or current_day not in opening_hours:
        return "Closed"

    day_hours = opening_hours.get(current_day)
    if not day_hours or "start" not in day_hours or "end" not in day_hours:
        return "Closed"

    start_time = datetime.strptime(day_hours["start"], "%H:%M").time()
    end_time = datetime.strptime(day_hours["end"], "%H:%M").time()

    if start_time <= current_time < end_time:
        one_hour_before_close = (datetime.combine(datetime.today(), end_time) - timedelta(hours=1)).time()
        if current_time >= one_hour_before_close:
            return "Closing Soon"
        return "Open"

    return "Closed"

def get_percentage(part, total):
    try:
        return round((float(part) / float(total)) * 100, 2) if total > 0 else 0.0
    except (ZeroDivisionError, ValueError, TypeError):
        return 0.0


def make_naive_aware(dt):
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt

def calculate_distance(lat1, lon1, lat2, lon2):
    if not all([lat1, lon1, lat2, lon2]):
        return None
    lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    radius = 6371  # km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(radius * c, 2)


def get_percentage(part, total):
    try:
        return round((float(part) / float(total)) * 100, 2) if total > 0 else 0.0
    except (ZeroDivisionError, ValueError, TypeError):
        return 0.0


def make_naive_aware(dt):
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt

def get_currency_symbol_safe(code, locale="en"):
    """
    Given a currency code like 'USD', returns the symbol like '$'.
    """
    try:
        return get_currency_symbol(code.upper(), locale=locale)
    except:
        return code.upper()  # Fallback to code if symbol not found
    

from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys

def compress_image(image_file, quality=70):
    image = Image.open(image_file)
    image_io = BytesIO()
    
    # Convert image to RGB if it's in palette mode (e.g., PNG)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    
    image.save(image_io, format='JPEG', quality=quality)
    compressed_image = InMemoryUploadedFile(
        image_io, None, image_file.name, 'image/jpeg',
        sys.getsizeof(image_io), None
    )
    return compressed_image