"""Paystack test-mode regression coverage. Provider calls are mocked; no money moves."""
import hashlib
import hmac
import json
from datetime import timedelta, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .cancellation_service import cancel_booking
from .models import Booking, Coach, Fare, PaymentTransaction, Route, Schedule, Seat, Station, Train, Wallet, WalletTransaction
from .paystack_service import finalize_payment, start_checkout
from .reservation_service import reserve_seat


@override_settings(PAYSTACK_TEST_SECRET_KEY="sk_test_example_not_real", PAYSTACK_WEBHOOK_SECRET="")
class PaystackCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="paystackuser", email="test@example.com", password="Password123!",
        )
        a = Station.objects.create(code="PSKA", name="Rigasa", city="Kaduna", state="Kaduna")
        b = Station.objects.create(code="PSAB", name="Idu", city="Abuja", state="FCT")
        route = Route.objects.create(origin=a, destination=b)
        train = Train.objects.create(code="PST", name="Paystack Train")
        coach = Coach.objects.create(train=train, code="A", travel_class="standard")
        seat = Seat.objects.create(coach=coach, label="1")
        schedule = Schedule.objects.create(route=route, train=train, departure_time=time(23, 59), arrival_time=time(1))
        Fare.objects.create(schedule=schedule, travel_class="standard", amount=Decimal("3000.00"))
        self.booking = reserve_seat(
            user=self.user, schedule_id=schedule.id, seat_id=seat.id,
            travel_date=timezone.localdate() + timedelta(days=3),
        )
        self.client.force_login(self.user)

    def provider_initialize(self, method, path, payload):
        self.assertEqual(payload["amount"], "300000")
        self.assertEqual(payload["currency"], "NGN")
        return {"reference": payload["reference"], "authorization_url": "https://checkout.paystack.com/abc"}

    def payload(self, **changes):
        data = {
            "reference": self.payment.reference, "amount": 300000,
            "currency": "NGN", "domain": "test", "status": "success",
        }
        data.update(changes)
        return data

    def start(self):
        with patch("core.paystack_service._request", side_effect=self.provider_initialize):
            response = self.client.post(reverse("paystack_checkout", args=[self.booking.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://checkout.paystack.com/abc")
        self.payment = PaymentTransaction.objects.get(booking=self.booking)
        self.assertEqual(self.payment.status, PaymentTransaction.Status.PENDING)

    def test_checkout_and_verified_callback_confirm_ticket_once(self):
        self.start()
        with patch("core.paystack_views.verify_reference", return_value=self.payload()):
            self.client.get(reverse("paystack_callback"), {"reference": self.payment.reference})
            self.client.get(reverse("paystack_callback"), {"reference": self.payment.reference})
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(PaymentTransaction.objects.filter(booking=self.booking, status="success").count(), 1)
        self.assertFalse(WalletTransaction.objects.filter(booking=self.booking).exists())

    def test_invalid_amount_does_not_confirm(self):
        self.start()
        payment = finalize_payment(self.payment.reference, self.payload(amount=1))
        self.booking.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.REVIEW)
        self.assertEqual(self.booking.status, Booking.Status.HELD)

    def test_expired_hold_is_never_confirmed_even_after_success(self):
        self.start()
        Booking.objects.filter(pk=self.booking.pk).update(hold_expires_at=timezone.now() - timedelta(seconds=1))
        payment = finalize_payment(self.payment.reference, self.payload())
        self.booking.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.REVIEW)
        self.assertNotEqual(self.booking.status, Booking.Status.CONFIRMED)

    def test_signed_webhook_retries_are_idempotent(self):
        self.start()
        body = json.dumps({"event": "charge.success", "data": {"reference": self.payment.reference}}).encode()
        sig = hmac.new(b"sk_test_example_not_real", body, hashlib.sha512).hexdigest()
        with patch("core.paystack_views.verify_reference", return_value=self.payload()):
            for _ in range(2):
                response = self.client.post(
                    reverse("paystack_webhook"), data=body, content_type="application/json",
                    HTTP_X_PAYSTACK_SIGNATURE=sig,
                )
                self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CONFIRMED)

    def test_unsigned_webhook_is_rejected(self):
        response = self.client.post(
            reverse("paystack_webhook"), data=b'{"event":"charge.success"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

    def test_cancellation_records_refund_review_without_wallet_credit(self):
        self.start()
        finalize_payment(self.payment.reference, self.payload())
        refund = cancel_booking(user=self.user, booking_id=self.booking.pk)
        self.payment.refresh_from_db()
        self.assertEqual(refund, Decimal("2700.00"))
        self.assertEqual(self.payment.status, PaymentTransaction.Status.REFUND_PENDING)
        self.assertEqual(self.payment.refund_amount, Decimal("2700.00"))
        self.assertFalse(WalletTransaction.objects.filter(booking=self.booking).exists())

    def test_wallet_cannot_charge_while_paystack_pending(self):
        self.start()
        from .payment_service import confirm_with_wallet
        from django.core.exceptions import ValidationError
        Wallet.objects.create(user=self.user, balance=Decimal("10000"))
        with self.assertRaisesMessage(ValidationError, "Paystack transaction"):
            confirm_with_wallet(user=self.user, booking_id=self.booking.pk)

    def test_checkout_without_configured_secret_fails_closed(self):
        with override_settings(PAYSTACK_TEST_SECRET_KEY=""):
            response = self.client.post(reverse("paystack_checkout", args=[self.booking.pk]), follow=True)
        self.assertContains(response, "not configured")
        self.assertFalse(PaymentTransaction.objects.exists())
