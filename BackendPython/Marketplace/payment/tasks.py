# tasks.py
from celery import shared_task
from django.utils import timezone

from ProfessionalUser.models import ProfessionalUser
from utils.email import send_custom_email

# @shared_task
# def send_trial_activation_email(user_id, trial_end_date_str):
#     try:
#         user = ProfessionalUser.objects.get(id=user_id)
#         subject = "🎉 Your Free Trial is Active"
#         message = (
#             f"Hi {user.userName},\n\n"
#             f"Your free trial is now active and will expire on {trial_end_date_str}.\n"
#             "Enjoy your Premium features!"
#         )
#         send_custom_email(subject, message, [user.email])
#     except ProfessionalUser.DoesNotExist:
#         pass

@shared_task
def send_trial_expiry_email():

    now = timezone.now()

    users = ProfessionalUser.objects.filter(
        is_free_trial_active=True,
        trial_end_date__lte=now
    )

    for user in users:
        user.is_free_trial_active = False
        user.subscription_active = False
        user.save()

        subject = "🚨 Your Free Trial Has Expired"
        print("messages",subject)
        message = f"Hi {user.userName},\n\nYour free trial has now expired. To continue using Premium features, please subscribe."
        send_custom_email(subject, message, [user.email])
