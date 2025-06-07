from django.core.management.base import BaseCommand
from django.utils import timezone
from ProfessionalUser.models import ProfessionalUser  # Adjust if your model is elsewhere

class Command(BaseCommand):
    help = 'Deactivate free trial if 3 months have passed'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        expired_users = ProfessionalUser.objects.filter(
            is_free_trial_active=True,
            trial_end_date__lt=today
        )

        count = expired_users.count()
        expired_users.update(is_free_trial_active=False)#,subscription_status="inactive")
        self.stdout.write(self.style.SUCCESS(f'{count} user(s) trial deactivated.'))
