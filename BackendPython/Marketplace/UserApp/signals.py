from django.db.models.signals import post_save
from django.dispatch import receiver
from ProfessionalUser.models import *



@receiver(post_save, sender=RoomBooking)
@receiver(post_save, sender=eventBooking)
@receiver(post_save, sender=experienceBooking)
@receiver(post_save, sender=slotBooking)
@receiver(post_save, sender=aestheticsBooking)
@receiver(post_save, sender=relaxationBooking)
@receiver(post_save, sender=artandcultureBooking)
def award_loyalty_points(sender, instance, **kwargs):
    status = getattr(instance, "status", None) or getattr(instance, "booking_status", None)
    if status in ["completed", "confirmed", "fulfilled"] and instance.is_paid:
        user = instance.user
        company = instance.company
        total_amount = float(getattr(instance, "price", 0) or getattr(instance, "total_price", 0))
        points_to_award = int(total_amount / 100) * 10

        if user and company:
            loyalty_obj, _ = LoyaltyPoint.objects.get_or_create(
                user=user, company=company,
                defaults={"total_points": 0}
            )
            loyalty_obj.total_points += points_to_award
            loyalty_obj.save()