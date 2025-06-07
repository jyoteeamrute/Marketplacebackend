import uuid

from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from UserApp.models import Users


@shared_task
def upload_profile_image_to_s3(file_content_bytes, folder_name, user_id=None, field_name=None):
    """
    Uploads image to S3 and updates the user model.
    :param file_content_bytes: Raw bytes of the uploaded file
    :param folder_name: S3 folder like "profile_images" or "identity_cards"
    :param user_id: ID of the user (as string or int)
    :param field_name: Field to update ('profileImage' or 'identityCardImage')
    """
    try:
        file_extension = "jpg"  # You can make this dynamic based on MIME later
        filename = f"{folder_name}/{user_id}_{uuid.uuid4()}.{file_extension}"
        path = default_storage.save(filename, ContentFile(file_content_bytes))
        file_url = default_storage.url(path)
        if user_id and field_name in ["profileImage", "identityCardImage"]:
            user = Users.objects.filter(id=user_id).first()
            if user:
                setattr(user, field_name, path)  # Or use file_url if you're storing full S3 URL
                user.save(update_fields=[field_name])

        return {"status": "success", "file_path": path}

    except Exception as e:
        return {"status": "error", "message": str(e)}
