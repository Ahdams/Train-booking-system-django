"""Atomic, one-active-hold-per-user reservations."""
from datetime import timedelta, datetime
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Booking, Fare, Schedule, Seat

HOLD_MINUTES = 10


def expire_holds(now=None):
    now = now or timezone.now()
    return Booking.objects.filter(
        status=Booking.Status.HELD, hold_expires_at__lte=now
    ).update(status=Booking.Status.EXPIRED)


def departure_at(booking):
    return timezone.make_aware(
        datetime.combine(booking.travel_date, booking.schedule.departure_time),
        timezone.get_current_timezone(),
    )


def has_upcoming_confirmed_booking(user, now):
    for booking in Booking.objects.filter(
        user=user, status=Booking.Status.CONFIRMED,
        travel_date__gte=timezone.localdate(now),
    ).select_related("schedule"):
        if departure_at(booking) > now:
            return True
    return False


def reserve_seat(*, user, schedule_id, seat_id, travel_date):
    """Serialize reservations for a user; database constraints guard competing seats."""
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        now = timezone.now()
        expire_holds(now)
        if has_upcoming_confirmed_booking(user, now):
            raise ValidationError("Your confirmed journey has not departed. Cancel it before booking another seat.")
        if Booking.objects.filter(user=user, status=Booking.Status.HELD).exists():
            raise ValidationError("Cancel your current reservation before reserving another seat.")
        schedule = Schedule.objects.select_related("route", "train").get(pk=schedule_id)
        seat = Seat.objects.select_related("coach").get(pk=seat_id)
        if not (schedule.is_active and schedule.train.is_active and schedule.route.is_active
                and schedule.route.origin.is_active and schedule.route.destination.is_active and seat.is_active):
            raise ValidationError("This journey or seat is unavailable.")
        if seat.coach.train_id != schedule.train_id:
            raise ValidationError("This seat belongs to a different train.")
        if travel_date < timezone.localdate():
            raise ValidationError("Cannot reserve a past journey.")
        if travel_date == timezone.localdate() and schedule.departure_time <= timezone.localtime().time():
            raise ValidationError("This train has already departed.")
        weekday = ("operates_monday", "operates_tuesday", "operates_wednesday",
                   "operates_thursday", "operates_friday", "operates_saturday", "operates_sunday")[travel_date.weekday()]
        if not getattr(schedule, weekday):
            raise ValidationError("This train does not operate on that day.")
        fare = Fare.objects.filter(schedule=schedule, travel_class=seat.coach.travel_class).first()
        if fare is None:
            raise ValidationError("No fare is configured for this seat.")
        try:
            with transaction.atomic():
                return Booking.objects.create(
                    reference="RF-" + uuid4().hex[:20].upper(),
                    user=user, schedule=schedule, travel_date=travel_date,
                    seat=seat, passenger_name=user.get_full_name() or user.username,
                    fare_paid=fare.amount, status=Booking.Status.HELD,
                    hold_expires_at=now + timedelta(minutes=HOLD_MINUTES),
                )
        except IntegrityError:
            raise ValidationError("This seat has just been reserved. Please select another.")


def cancel_hold(*, user, booking_id):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        expire_holds()
        booking = Booking.objects.select_for_update().filter(
            pk=booking_id, user=user, status=Booking.Status.HELD
        ).first()
        if booking is None:
            raise ValidationError("No active reservation was found.")
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        return booking
