"""Atomic wallet checkout; wallet funding must be handled by a verified payment provider."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Booking, Wallet, WalletTransaction, JourneyDisruption
from .reservation_service import departure_at, expire_holds


def confirm_with_wallet(*, user, booking_id):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        now = timezone.now()
        expire_holds(now)
        # Match the schedule lock taken by operator cancellations and reservations.
        initial = Booking.objects.only('schedule_id').filter(pk=booking_id, user=user).first()
        if initial is None:
            raise ValidationError("This temporary reservation is no longer available.")
        from .models import Schedule
        Schedule.objects.select_for_update().get(pk=initial.schedule_id)
        booking = Booking.objects.select_for_update().select_related("schedule").filter(
            pk=booking_id, user=user
        ).first()
        if booking is None or booking.status != Booking.Status.HELD:
            raise ValidationError("This temporary reservation is no longer available.")
        if booking.hold_expires_at is None or booking.hold_expires_at <= now:
            raise ValidationError("Your reservation has expired.")
        if JourneyDisruption.objects.filter(schedule=booking.schedule, travel_date=booking.travel_date, status=JourneyDisruption.Status.CANCELLED).exists():
            raise ValidationError("This journey has been cancelled by the operator.")
        if departure_at(booking) <= now:
            raise ValidationError("The train has already departed.")
        if Booking.objects.filter(
            user=user, status=Booking.Status.CONFIRMED,
            travel_date__gte=timezone.localdate(now),
        ).exclude(pk=booking.pk).select_related("schedule").exists():
            from .reservation_service import has_upcoming_confirmed_booking
            if has_upcoming_confirmed_booking(user, now):
                raise ValidationError("Cancel your existing upcoming ticket before paying for another.")
        wallet = Wallet.objects.select_for_update().filter(user=user).first()
        if wallet is None or wallet.balance < booking.fare_paid:
            raise ValidationError("Insufficient wallet balance. No payment was taken.")
        if WalletTransaction.objects.filter(booking=booking, kind=WalletTransaction.Kind.DEBIT).exists():
            raise ValidationError("This reservation has already been paid.")
        wallet.balance -= booking.fare_paid
        wallet.save(update_fields=["balance"])
        if booking.fare_paid > 0:
            WalletTransaction.objects.create(
                wallet=wallet, booking=booking, kind=WalletTransaction.Kind.DEBIT,
                amount=booking.fare_paid, balance_after=wallet.balance,
            )
        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=["status"])
        return booking
