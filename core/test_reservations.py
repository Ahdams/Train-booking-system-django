from datetime import timedelta, time, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Booking, Coach, Fare, Route, Schedule, Seat, Station, Train
from .reservation_service import reserve_seat, cancel_hold
from .cancellation_service import refund_percentage, cancel_booking
from .models import Wallet, WalletTransaction


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

    def test_confirmed_booking_blocks_new_hold(self):
        first = self.hold(self.seat1)
        first.status = Booking.Status.CONFIRMED
        first.save(update_fields=["status"])
        with self.assertRaisesMessage(ValidationError, "confirmed journey has not departed"):
            self.hold(self.seat2)

    def test_departed_confirmed_booking_does_not_block(self):
        first = self.hold(self.seat1)
        first.status = Booking.Status.CONFIRMED
        first.travel_date = timezone.localdate() - timedelta(days=1)
        first.save(update_fields=["status", "travel_date"])
        self.assertEqual(self.hold(self.seat2).status, Booking.Status.HELD)

    def test_cancelling_confirmed_booking_refunds_wallet_once(self):
        first = self.hold(self.seat1)
        first.status = Booking.Status.CONFIRMED
        first.save(update_fields=["status"])
        wallet, _ = Wallet.objects.get_or_create(user=self.user)
        WalletTransaction.objects.create(
            wallet=wallet, booking=first, kind="debit",
            amount=first.fare_paid, balance_after=wallet.balance,
        )
        departure = timezone.make_aware(datetime.combine(self.day, self.schedule.departure_time))
        amount = cancel_booking(user=self.user, booking_id=first.id, now=departure - timedelta(minutes=25))
        self.assertEqual(amount, Decimal("1200.00"))
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("1200.00"))
        self.assertEqual(WalletTransaction.objects.filter(booking=first, kind="refund").count(), 1)
        with self.assertRaises(ValidationError):
            cancel_booking(user=self.user, booking_id=first.id, now=departure - timedelta(minutes=20))
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("1200.00"))

    def test_refund_percentage_boundaries(self):
        now = timezone.now()
        self.assertEqual(refund_percentage(now + timedelta(days=2), now), Decimal("0.90"))
        self.assertEqual(refund_percentage(now + timedelta(hours=24), now), Decimal("0.75"))
        self.assertEqual(refund_percentage(now + timedelta(hours=2), now), Decimal("0.50"))
        self.assertEqual(refund_percentage(now + timedelta(minutes=30), now), Decimal("0.50"))
        self.assertEqual(refund_percentage(now + timedelta(minutes=25), now), Decimal("0.40"))
        self.assertEqual(refund_percentage(now, now), Decimal("0"))
