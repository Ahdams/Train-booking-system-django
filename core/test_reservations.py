from datetime import timedelta, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Booking, Coach, Fare, Route, Schedule, Seat, Station, Train
from .reservation_service import reserve_seat, cancel_hold


class SingleHoldTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="rider", password="Password123!")
        a = Station.objects.create(code="RKA", name="Rigasa", city="Kaduna", state="Kaduna")
        b = Station.objects.create(code="RAB", name="Idu", city="Abuja", state="FCT")
        route = Route.objects.create(origin=a, destination=b)
        train = Train.objects.create(code="RT1", name="Test Train")
        coach = Coach.objects.create(train=train, code="A", travel_class="standard")
        self.seat1 = Seat.objects.create(coach=coach, label="1")
        self.seat2 = Seat.objects.create(coach=coach, label="2")
        self.schedule = Schedule.objects.create(route=route, train=train, departure_time=time(23, 59), arrival_time=time(1))
        Fare.objects.create(schedule=self.schedule, travel_class="standard", amount=Decimal("3000"))
        self.day = timezone.localdate() + timedelta(days=2)

    def hold(self, seat):
        return reserve_seat(user=self.user, schedule_id=self.schedule.id, seat_id=seat.id, travel_date=self.day)

    def test_second_hold_is_rejected_until_first_cancelled(self):
        first = self.hold(self.seat1)
        with self.assertRaisesMessage(ValidationError, "Cancel your current reservation"):
            self.hold(self.seat2)
        cancel_hold(user=self.user, booking_id=first.id)
        second = self.hold(self.seat2)
        self.assertEqual(second.status, Booking.Status.HELD)

    def test_expired_hold_frees_account_and_seat(self):
        first = self.hold(self.seat1)
        Booking.objects.filter(pk=first.pk).update(hold_expires_at=timezone.now() - timedelta(seconds=1))
        second = self.hold(self.seat1)
        first.refresh_from_db()
        self.assertEqual(first.status, Booking.Status.EXPIRED)
        self.assertEqual(second.status, Booking.Status.HELD)

    def test_cannot_cancel_another_passengers_hold(self):
        first = self.hold(self.seat1)
        stranger = get_user_model().objects.create_user(username="stranger", password="Password123!")
        with self.assertRaises(ValidationError):
            cancel_hold(user=stranger, booking_id=first.id)
        first.refresh_from_db()
        self.assertEqual(first.status, Booking.Status.HELD)

    def test_confirmed_booking_does_not_block_new_hold(self):
        first = self.hold(self.seat1)
        first.status = Booking.Status.CONFIRMED
        first.save(update_fields=["status"])
        self.assertEqual(self.hold(self.seat2).status, Booking.Status.HELD)
