from celery import shared_task
from django.core.files.storage import default_storage
from celery import shared_task
import os, tempfile, shutil
from .models import StoreReel
from .reelupload import *
from ProfessionalUser.utils import get_presigned_url, convert_video_to_m3u8, generate_thumbnail, upload_to_s3
import logging

logger = logging.getLogger(__name__)

@shared_task
def delete_s3_file(file_path):
    if default_storage.exists(file_path):
        default_storage.delete(file_path)
        return f"Deleted file: {file_path}"
    else:
        return f"File not found: {file_path}"




def upload_m3u8_and_ts(output_dir, s3_folder):
    """Upload M3U8 and TS files to S3."""
    
    logger.info(f"Uploading M3U8 and TS files from {output_dir} to {s3_folder}")
    
    uploaded_files = []
    
    if not os.path.exists(output_dir):
        logger.error(f"Output directory does not exist: {output_dir}")
        return uploaded_files
    
    files_to_upload = os.listdir(output_dir)
    logger.info(f"Found {len(files_to_upload)} files to upload")
    
    for file in files_to_upload:
        local_path = os.path.join(output_dir, file)
        
        if not os.path.isfile(local_path):
            continue
            
        s3_key = os.path.join(s3_folder, file).replace("\\", "/")
        
        try:
            url = upload_to_s3(local_path, s3_key)
            if url:
                uploaded_files.append(url)
                logger.info(f"Uploaded: {file}")
            else:
                logger.error(f"Failed to upload: {file}")
        except Exception as e:
            logger.error(f"Error uploading {file}: {e}")
    
    logger.info(f"Successfully uploaded {len(uploaded_files)} files")
    return uploaded_files



@shared_task(bind=True)
def process_video_task(self, reel_id):
    logger.info(f"===> ==================== Celery Task Started for reel_id={reel_id}")
    try:
        instance = StoreReel.objects.get(id=reel_id)

        if instance.m3u8_url:
            logger.info(f"Video {reel_id} already processed")
            return "Already processed"

        if not instance.video:
            logger.error(f"No video file found for reel {reel_id}")
            return "No video file"

        video_key = instance.video.name
        presigned_url = get_presigned_url(video_key)

        if not presigned_url:
            logger.error(f"Failed to get pre-signed URL for reel {reel_id}")
            return "Failed to get presigned URL"

        output_s3_folder = f"reels/m3u8/{reel_id}"
        output_dir, m3u8_filename = convert_video_to_m3u8(presigned_url, output_s3_folder)

        if not output_dir:
            logger.error(f"FFmpeg conversion failed for reel {reel_id}")
            return "Conversion failed"

        uploaded_files = upload_m3u8_and_ts(output_dir, output_s3_folder)

        m3u8_url = next((url for url in uploaded_files if "video.m3u8" in url or "master.m3u8" in url), None)
        if not m3u8_url:
            logger.warning(f"M3U8 file not found for reel {reel_id}")

        thumbnail_url = None
        try:
            temp_thumbnail_path = os.path.join(tempfile.gettempdir(), f"thumbnail_{reel_id}.jpg")
            generated_thumbnail = generate_thumbnail(presigned_url, temp_thumbnail_path)
            if generated_thumbnail:
                s3_thumbnail_key = f"reels/thumbnails/{reel_id}_thumbnail.jpg"
                thumbnail_url = upload_to_s3(generated_thumbnail, s3_thumbnail_key)
                if os.path.exists(temp_thumbnail_path):
                    os.remove(temp_thumbnail_path)
        except Exception as e:
            logger.warning(f"Thumbnail generation failed for reel {reel_id}: {e}")

        instance.m3u8_url = m3u8_url
        if thumbnail_url:
            instance.thumbnail = thumbnail_url
        instance.save(update_fields=['m3u8_url', 'thumbnail'])

        if output_dir and os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

        logger.info(f"Successfully processed reel {reel_id}")
        return "Success"

    except StoreReel.DoesNotExist:
        logger.error(f"StoreReel with id {reel_id} does not exist")
        return "StoreReel not found"
    except Exception as e:
        logger.error(f"Error processing video {reel_id}: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)
