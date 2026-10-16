"""Apply operator disruptions and wallet refunds in one transaction."""
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Booking, JourneyDisruption, Schedule, Wallet, WalletTransaction


@transaction.atomic
def apply_disruption(*, schedule, travel_date, status, reason, revised_departure_time=None):
    Schedule.objects.select_for_update().get(pk=schedule.pk)
    disruption, _ = JourneyDisruption.objects.update_or_create(
        schedule=schedule, travel_date=travel_date,
        defaults={"status": status, "reason": reason, "revised_departure_time": revised_departure_time},
    )
    if status != JourneyDisruption.Status.CANCELLED:
        return disruption
    bookings = list(Booking.objects.select_for_update().filter(
        schedule=schedule, travel_date=travel_date,
        status__in=[Booking.Status.HELD, Booking.Status.CONFIRMED],
    ).order_by("pk"))
    for booking in bookings:
        if booking.status == Booking.Status.CONFIRMED:
            if booking.fare_paid > 0 and not WalletTransaction.objects.filter(
                booking=booking, kind=WalletTransaction.Kind.DEBIT, amount=booking.fare_paid
            ).exists():
                raise ValidationError("Cannot cancel journey: confirmed booking lacks verified payment.")
            if WalletTransaction.objects.filter(
                booking=booking, kind=WalletTransaction.Kind.REFUND
            ).exists():
                raise ValidationError("Cannot cancel journey: active booking already has a refund.")
            if booking.fare_paid > 0:
                wallet, _ = Wallet.objects.select_for_update().get_or_create(user=booking.user)
                wallet.balance += booking.fare_paid
                wallet.save(update_fields=["balance"])
                WalletTransaction.objects.create(
                    wallet=wallet, booking=booking, kind=WalletTransaction.Kind.REFUND,
                    amount=booking.fare_paid, balance_after=wallet.balance,
                )
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
    return disruption
