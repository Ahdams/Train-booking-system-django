"""Full booking lifecycle regression tests: reservation, wallet, cancellation, and disruption."""
from datetime import timedelta, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .cancellation_service import cancel_booking
from .disruption_service import apply_disruption
from .models import Booking, Coach, Fare, Route, Schedule, Seat, Station, Train, Wallet, WalletTransaction
from .payment_service import confirm_with_wallet
from .reservation_service import reserve_seat


class BookingLifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="lifecycle", password="Pass12345!")
        self.wallet = Wallet.objects.create(user=self.user, balance=Decimal("10000.00"))
        origin = Station.objects.create(code="LCK", name="Rigasa", city="Kaduna", state="Kaduna")
        destination = Station.objects.create(code="LCA", name="Idu", city="Abuja", state="FCT")
        route = Route.objects.create(origin=origin, destination=destination)
        train = Train.objects.create(code="LCT", name="Lifecycle Express")
        coach = Coach.objects.create(train=train, code="A", travel_class="standard")
        self.seat = Seat.objects.create(coach=coach, label="1")
        self.schedule = Schedule.objects.create(route=route, train=train, departure_time=time(23, 59), arrival_time=time(1))
        Fare.objects.create(schedule=self.schedule, travel_class="standard", amount=Decimal("3000.00"))
        self.day = timezone.localdate() + timedelta(days=3)

    def book_and_pay(self):
        booking = reserve_seat(user=self.user, schedule_id=self.schedule.pk, seat_id=self.seat.pk, travel_date=self.day)
        confirm_with_wallet(user=self.user, booking_id=booking.pk)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        return booking

    def test_passenger_cancellation_refunds_90_percent_once(self):
        booking = self.book_and_pay()
        refund = cancel_booking(user=self.user, booking_id=booking.pk)
        self.assertEqual(refund, Decimal("2700.00"))
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("9700.00"))
        self.assertEqual(WalletTransaction.objects.filter(booking=booking, kind=WalletTransaction.Kind.DEBIT).count(), 1)
        self.assertEqual(WalletTransaction.objects.filter(booking=booking, kind=WalletTransaction.Kind.REFUND).count(), 1)
        with self.assertRaises(ValidationError):
            cancel_booking(user=self.user, booking_id=booking.pk)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("9700.00"))

    def test_operator_cancellation_refunds_full_wallet_amount(self):
        booking = self.book_and_pay()
        apply_disruption(schedule=self.schedule, travel_date=self.day, status="cancelled", reason="Track closed")
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("10000.00"))
        self.assertEqual(WalletTransaction.objects.filter(booking=booking, kind=WalletTransaction.Kind.REFUND).count(), 1)
        with self.assertRaises(ValidationError):
            cancel_booking(user=self.user, booking_id=booking.pk)

    def test_second_reservation_blocked_until_first_cancelled(self):
        booking = self.book_and_pay()
        with self.assertRaisesMessage(ValidationError, "confirmed journey"):
            reserve_seat(user=self.user, schedule_id=self.schedule.pk, seat_id=self.seat.pk, travel_date=self.day + timedelta(days=1))
        cancel_booking(user=self.user, booking_id=booking.pk)
        second = reserve_seat(user=self.user, schedule_id=self.schedule.pk, seat_id=self.seat.pk, travel_date=self.day + timedelta(days=1))
        self.assertEqual(second.status, Booking.Status.HELD)

    def test_unpaid_hold_cancellation_does_not_touch_wallet(self):
        booking = reserve_seat(user=self.user, schedule_id=self.schedule.pk, seat_id=self.seat.pk, travel_date=self.day)
        refund = cancel_booking(user=self.user, booking_id=booking.pk)
        self.assertEqual(refund, Decimal("0.00"))
        self.assertEqual(Wallet.objects.get(user=self.user).balance, Decimal("10000.00"))
        self.assertFalse(WalletTransaction.objects.filter(booking=booking).exists())
