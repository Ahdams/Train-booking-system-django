from datetime import timedelta, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Booking, Coach, Fare, Route, Schedule, Seat, Station, Train, Wallet, WalletTransaction
from .reservation_service import reserve_seat
from .payment_service import confirm_with_wallet


class WalletCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="payer", password="Password123!")
        self.wallet = Wallet.objects.create(user=self.user, balance=Decimal("10000.00"))
        origin = Station.objects.create(code="PAYK", name="Rigasa", city="Kaduna", state="Kaduna")
        destination = Station.objects.create(code="PAYA", name="Idu", city="Abuja", state="FCT")
        route = Route.objects.create(origin=origin, destination=destination)
        train = Train.objects.create(code="PAYT", name="Payment Test Train")
        coach = Coach.objects.create(train=train, code="A", travel_class="standard")
        self.seat = Seat.objects.create(coach=coach, label="1")
        self.schedule = Schedule.objects.create(route=route, train=train, departure_time=time(23, 59), arrival_time=time(1))
        Fare.objects.create(schedule=self.schedule, travel_class="standard", amount=Decimal("3000.00"))
        self.day = timezone.localdate() + timedelta(days=2)

    def hold(self):
        return reserve_seat(user=self.user, schedule_id=self.schedule.id, seat_id=self.seat.id, travel_date=self.day)

    def test_successful_payment_debits_wallet_once(self):
        booking = self.hold()
        confirm_with_wallet(user=self.user, booking_id=booking.pk)
        booking.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(self.wallet.balance, Decimal("7000.00"))
        self.assertEqual(WalletTransaction.objects.filter(booking=booking, kind="debit").count(), 1)
        with self.assertRaises(ValidationError):
            confirm_with_wallet(user=self.user, booking_id=booking.pk)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("7000.00"))

    def test_insufficient_funds_do_not_confirm(self):
        booking = self.hold()
        self.wallet.balance = Decimal("500.00")
        self.wallet.save()
        with self.assertRaisesMessage(ValidationError, "Insufficient wallet balance"):
            confirm_with_wallet(user=self.user, booking_id=booking.pk)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.HELD)
        self.assertFalse(WalletTransaction.objects.filter(booking=booking, kind="debit").exists())

    def test_expired_hold_cannot_be_paid(self):
        booking = self.hold()
        Booking.objects.filter(pk=booking.pk).update(hold_expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(ValidationError):
            confirm_with_wallet(user=self.user, booking_id=booking.pk)

    def test_another_user_cannot_pay_for_booking(self):
        booking = self.hold()
        other = get_user_model().objects.create_user(username="otherpayer", password="Password123!")
        with self.assertRaises(ValidationError):
            confirm_with_wallet(user=other, booking_id=booking.pk)
