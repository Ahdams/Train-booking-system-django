"""Paystack test-mode checkout and server-side payment verification.

Only test secret keys are accepted. Never trust a browser redirect as payment proof.
"""
import json
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Booking, JourneyDisruption, PaymentTransaction, Schedule, WalletTransaction
from .reservation_service import departure_at, expire_holds, has_upcoming_confirmed_booking

API = "https://api.paystack.co"


def _secret():
    key = getattr(settings, "PAYSTACK_TEST_SECRET_KEY", "")
    if not key.startswith("sk_test_"):
        raise ValidationError("Paystack test checkout is not configured.")
    return key


def _request(method, path, payload=None):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        API + path, data=body, method=method,
        headers={"Authorization": "Bearer " + _secret(), "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            data = json.loads(response.read(1048576))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise ValidationError("Payment provider is temporarily unavailable. Please retry.") from exc
    if not isinstance(data, dict) or data.get("status") is not True or not isinstance(data.get("data"), dict):
        raise ValidationError("Payment provider could not complete the request.")
    return data["data"]


def _kobo(amount):
    amount = Decimal(amount)
    if amount <= 0 or amount != amount.quantize(Decimal("0.01")):
        raise ValidationError("Invalid ticket fare for online checkout.")
    return int(amount * 100)


def start_checkout(*, user, booking_id, callback_url):
    """Create one active attempt per booking; never initialize a different amount."""
    _secret()
    if not user.email:
        raise ValidationError("Add your email address in My profile before paying.")
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        expire_holds()
        initial = Booking.objects.filter(pk=booking_id, user=user).only("schedule_id").first()
        if initial is None:
            raise ValidationError("Reservation not found.")
        Schedule.objects.select_for_update().get(pk=initial.schedule_id)
        booking = Booking.objects.select_for_update().get(pk=booking_id, user=user)
        if booking.status != Booking.Status.HELD or not booking.hold_expires_at or booking.hold_expires_at <= timezone.now():
            raise ValidationError("Your seat hold has expired. Please reserve again.")
        if departure_at(booking) <= timezone.now() or JourneyDisruption.objects.filter(
            schedule=booking.schedule, travel_date=booking.travel_date,
            status=JourneyDisruption.Status.CANCELLED,
        ).exists():
            raise ValidationError("This journey is no longer available.")
        if WalletTransaction.objects.filter(booking=booking, kind=WalletTransaction.Kind.DEBIT).exists():
            raise ValidationError("This reservation has already been paid.")
        attempt = PaymentTransaction.objects.select_for_update().filter(
            booking=booking, status__in=[PaymentTransaction.Status.INITIATED, PaymentTransaction.Status.PENDING],
        ).first()
        if attempt:
            if attempt.authorization_url:
                return attempt.authorization_url
            raise ValidationError("Payment setup is in progress. Please retry shortly.")
        attempt = PaymentTransaction.objects.create(
            booking=booking, reference="RFP-" + uuid4().hex.upper(),
            amount=booking.fare_paid, currency="NGN",
            status=PaymentTransaction.Status.INITIATED,
        )
    try:
        data = _request("POST", "/transaction/initialize", {
            "email": user.email,
            "amount": str(_kobo(attempt.amount)),
            "currency": "NGN",
            "reference": attempt.reference,
            "callback_url": callback_url,
            "metadata": {"booking_reference": booking.reference},
        })
        url = data.get("authorization_url", "")
        parsed = urlparse(url)
        if data.get("reference") != attempt.reference or parsed.scheme != "https" or parsed.hostname != "checkout.paystack.com":
            raise ValidationError("Invalid payment checkout response.")
    except ValidationError:
        PaymentTransaction.objects.filter(pk=attempt.pk, status=PaymentTransaction.Status.INITIATED).update(
            status=PaymentTransaction.Status.FAILED,
        )
        raise
    PaymentTransaction.objects.filter(pk=attempt.pk, status=PaymentTransaction.Status.INITIATED).update(
        authorization_url=url, status=PaymentTransaction.Status.PENDING,
    )
    return url


def verify_reference(reference):
    if not reference or len(reference) > 70:
        raise ValidationError("Invalid payment reference.")
    return _request("GET", "/transaction/verify/" + quote(reference, safe=""))


def finalize_payment(reference, data):
    """Idempotent fulfilment. Late or mismatched charges go to manual review."""
    initial = PaymentTransaction.objects.select_related("booking").filter(reference=reference).first()
    if initial is None:
        raise ValidationError("Unknown payment reference.")
    with transaction.atomic():
        Schedule.objects.select_for_update().get(pk=initial.booking.schedule_id)
        booking = Booking.objects.select_for_update().select_related("schedule").get(pk=initial.booking_id)
        payment = PaymentTransaction.objects.select_for_update().get(pk=initial.pk)
        if payment.status in (
            PaymentTransaction.Status.SUCCESS, PaymentTransaction.Status.REVIEW,
            PaymentTransaction.Status.REFUND_PENDING, PaymentTransaction.Status.REFUNDED,
        ):
            return payment
        if not isinstance(data, dict) or data.get("reference") != reference:
            payment.status = PaymentTransaction.Status.REVIEW
        elif data.get("status") == "success":
            try:
                amount_valid = int(data.get("amount")) == _kobo(payment.amount)
            except (ValueError, TypeError, ValidationError):
                amount_valid = False
            if not (amount_valid and data.get("currency") == payment.currency and data.get("domain") == "test"):
                payment.status = PaymentTransaction.Status.REVIEW
            else:
                now = timezone.now()
                valid_hold = (
                    booking.status == Booking.Status.HELD
                    and booking.hold_expires_at is not None and booking.hold_expires_at > now
                    and departure_at(booking) > now
                    and not JourneyDisruption.objects.filter(
                        schedule=booking.schedule, travel_date=booking.travel_date,
                        status=JourneyDisruption.Status.CANCELLED,
                    ).exists()
                    and not has_upcoming_confirmed_booking(booking.user, now)
                    and not WalletTransaction.objects.filter(
                        booking=booking, kind=WalletTransaction.Kind.DEBIT,
                    ).exists()
                    and not PaymentTransaction.objects.filter(
                        booking=booking, status=PaymentTransaction.Status.SUCCESS,
                    ).exclude(pk=payment.pk).exists()
                )
                if valid_hold:
                    booking.status = Booking.Status.CONFIRMED
                    booking.save(update_fields=["status"])
                    payment.status = PaymentTransaction.Status.SUCCESS
                else:
                    payment.status = PaymentTransaction.Status.REVIEW
        elif data.get("status") in ("failed", "abandoned", "reversed"):
            payment.status = PaymentTransaction.Status.FAILED
        else:
            payment.status = PaymentTransaction.Status.PENDING
        payment.gateway_status = str(data.get("status", ""))[:32] if isinstance(data, dict) else ""
        payment.save(update_fields=["status", "gateway_status", "updated_at"])
        return payment
