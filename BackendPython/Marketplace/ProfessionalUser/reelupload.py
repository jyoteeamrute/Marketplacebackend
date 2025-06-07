import os
import tempfile
import subprocess
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ProfessionalUser.models import *
from ProfessionalUser.serializers import StoreReelSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from ProfessionalUser.tasks import process_video_task  
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile

logger = logging.getLogger(__name__)

class StoreReelCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def get_video_duration(self, video_path):
        """Extract video duration using FFmpeg."""
        try:
            result = subprocess.run(
                ["ffprobe", "-i", video_path, "-show_entries", "format=duration", "-v", "quiet", "-of", "csv=p=0"],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            return float(result.stdout.strip())
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"Error getting video duration: {e}")
            return None

    def post(self, request, *args, **kwargs):
        try:
            if "video" not in request.FILES:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "No video file provided"
                }, status=status.HTTP_400_BAD_REQUEST)

            video_file = request.FILES["video"]
            company_id = request.data.get("company_id")
            category_id = request.data.get("category_id")
            title = request.data.get("title", "").strip()

            if video_file.size > 100 * 1024 * 1024:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Video file too large. Maximum size is 100MB."
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                professional_user = ProfessionalUser.objects.get(email=request.user.email)
            except ProfessionalUser.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "ProfessionalUser not found"
                }, status=status.HTTP_404_NOT_FOUND)

            if not company_id:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Company ID is required"
                }, status=status.HTTP_400_BAD_REQUEST)

            try:
                company = CompanyDetails.objects.get(id=company_id, professionaluser__company_id=company_id)
            except CompanyDetails.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "Company not found"
                }, status=status.HTTP_404_NOT_FOUND)

            # Validate category_id
            category = None
            if category_id:
                try:
                    category = Category.objects.get(id=category_id)
                    if not professional_user.categories.filter(id=category_id).exists():
                        return Response({
                            "statusCode": 403,
                            "status": False,
                            "message": "You can only select categories assigned during registration."
                        }, status=status.HTTP_403_FORBIDDEN)
                except Category.DoesNotExist:
                    return Response({
                        "statusCode": 404,
                        "status": False,
                        "message": "Category not found"
                    }, status=status.HTTP_404_NOT_FOUND)

            temp_video_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                    for chunk in video_file.chunks():
                        temp_file.write(chunk)
                    temp_video_path = temp_file.name

                duration = self.get_video_duration(temp_video_path)
                
                if duration is None:
                    return Response({
                        "statusCode": 400,
                        "status": False,
                        "message": "Could not determine video duration. Please upload a valid video file."
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if duration > 60:
                    return Response({
                        "statusCode": 400,
                        "status": False,
                        "message": "Video duration must be 60 seconds or less."
                    }, status=status.HTTP_400_BAD_REQUEST)

                instance = StoreReel.objects.create(
                    company_id=company,
                    video=video_file,
                    category=category,
                    title=title
                )
                
            finally:
                if temp_video_path and os.path.exists(temp_video_path):
                    try:
                        os.remove(temp_video_path)
                    except OSError:
                        pass
            logger.info(f"Reel created successfully with ID: {instance.id}")
            # Enqueue the video processing task
            process_video_task.delay(instance.id)
            
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Reel uploaded successfully! Processing will begin shortly.",
                "data": StoreReelSerializer(instance, context={"request": request}).data
            }, status=status.HTTP_201_CREATED)

        

        except Exception as e:
            logger.error(f"Unexpected error in StoreReelCreateAPIView: {e}")
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An unexpected error occurred",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



 
#image compression function

def compress_image(image_file, quality=70, max_size=(1024, 1024)):
    try:
        print("Compressing image:", image_file.name)
        image = Image.open(image_file)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        image.thumbnail(max_size, Image.LANCZOS)
        # Use original file extension to determine format
        original_format = image.format or os.path.splitext(image_file.name)[1].replace('.', '').upper()
        format_mapping = {
            'JPG': 'JPEG',
            'JPEG': 'JPEG',
            'PNG': 'PNG',
            'WEBP': 'WEBP',
            'GIF': 'GIF'
        }
        save_format = format_mapping.get(original_format.upper(), 'JPEG')  
        if save_format in ['JPEG', 'JPG']:
            image = image.convert("RGB")

        image_io = BytesIO()
        image.save(image_io, format=save_format, optimize=True, quality=quality)

        # Get correct size
        image_io.seek(0)
        compressed_image = InMemoryUploadedFile(
            file=image_io,
            field_name=None,
            name=os.path.splitext(image_file.name)[0] + f".{save_format.lower()}",
            content_type=f'image/{save_format.lower()}',
            size=image_io.getbuffer().nbytes,
            charset=None
        )

        return compressed_image

    except UnidentifiedImageError:
        raise ValueError("Invalid image file provided.")
    except Exception as e:
        raise RuntimeError(f"Failed to compress image: {str(e)}")
