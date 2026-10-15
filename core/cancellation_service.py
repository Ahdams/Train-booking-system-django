"""Cancellation rules and atomic wallet refunds for confirmed tickets."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Booking, Wallet, WalletTransaction
from .reservation_service import departure_at, expire_holds


def refund_percentage(departure, now):
    remaining = departure - now
    if remaining <= timedelta(0):
        return Decimal("0")
    if remaining > timedelta(hours=24):
        return Decimal("0.90")
    if remaining > timedelta(hours=2):
        return Decimal("0.75")
    if remaining >= timedelta(minutes=30):
        return Decimal("0.50")
    return Decimal("0.40")


def cancel_booking(*, user, booking_id, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        expire_holds(now)
        booking = Booking.objects.select_for_update().select_related("schedule").filter(
            pk=booking_id, user=user,
        ).first()
        if booking is None or booking.status not in (Booking.Status.HELD, Booking.Status.CONFIRMED):
            raise ValidationError("No cancellable booking was found.")
        if booking.status == Booking.Status.HELD:
            booking.status = Booking.Status.CANCELLED
            booking.save(update_fields=["status"])
            return Decimal("0.00")
        percentage = refund_percentage(departure_at(booking), now)
        if percentage == 0:
            raise ValidationError("This train has departed. Cancellation is no longer available.")
        amount = (booking.fare_paid * percentage).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if booking.fare_paid > 0 and not WalletTransaction.objects.filter(
            booking=booking, kind=WalletTransaction.Kind.DEBIT, amount=booking.fare_paid,\n        ).exists():\n            raise ValidationError("No verified wallet payment exists for this booking.")\n        wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
        if WalletTransaction.objects.filter(booking=booking, kind=WalletTransaction.Kind.REFUND).exists():
            raise ValidationError("This ticket has already been refunded.")
        wallet.balance += amount
        wallet.save(update_fields=["balance"])
        if amount > 0:
            WalletTransaction.objects.create(
                wallet=wallet, booking=booking, kind=WalletTransaction.Kind.REFUND,
                amount=amount, balance_after=wallet.balance,
            )
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        return amount
