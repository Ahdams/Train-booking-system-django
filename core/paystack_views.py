"""Paystack hosted checkout, verified return and authenticated webhooks."""
import hashlib
import hmac
import json
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .models import PaymentTransaction
from .paystack_service import finalize_payment, start_checkout, verify_reference


@login_required
def paystack_checkout(request, booking_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        callback = request.build_absolute_uri(reverse("paystack_callback"))
        url = start_checkout(user=request.user, booking_id=booking_id, callback_url=callback)
        return redirect(url)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("my_bookings")


@login_required
def paystack_callback(request):
    reference = request.GET.get("reference", "")
    if not PaymentTransaction.objects.filter(reference=reference, booking__user=request.user).exists():
        messages.error(request, "Payment reference not found for your account.")
        return redirect("my_bookings")
    try:
        payment = finalize_payment(reference, verify_reference(reference))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("my_bookings")
    if payment.status == PaymentTransaction.Status.SUCCESS:
        messages.success(request, "Payment verified. Your ticket is confirmed.")
    elif payment.status == PaymentTransaction.Status.REVIEW:
        messages.warning(request, "Payment received but the seat could not be confirmed. Contact support with your payment reference.")
    else:
        messages.warning(request, "Payment is not confirmed yet. Check your bookings before trying again.")
    return redirect("my_bookings")


def _valid_signature(request):
    body = request.body
    new_secret = getattr(settings, "PAYSTACK_WEBHOOK_SECRET", "")
    header = request.headers.get("Paystack-Signature", "")
    if new_secret and header:
        fields = [x.strip() for x in header.split(",")]
        stamps = [x[2:] for x in fields if x.startswith("t=")]
        sigs = [x[3:].split(":", 1)[-1] for x in fields if x.startswith("v1=")]
        if len(stamps) != 1 or not stamps[0].isdigit() or abs(time.time() - int(stamps[0])) > 300:
            return False
        expected = hmac.new(new_secret.encode(), stamps[0].encode() + b"." + body, hashlib.sha512).hexdigest()
        return any(hmac.compare_digest(expected, sig) for sig in sigs)
    # Legacy signature while the account is migrating to webhook signing secrets.
    key = getattr(settings, "PAYSTACK_TEST_SECRET_KEY", "")
    legacy = request.headers.get("x-paystack-signature", "")
    if not key.startswith("sk_test_") or not legacy:
        return False
    expected = hmac.new(key.encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, legacy)


@csrf_exempt
def paystack_webhook(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not _valid_signature(request):
        return HttpResponse(status=401)
    try:
        event = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)
    if event.get("event") != "charge.success":
        return HttpResponse(status=200)
    reference = event.get("data", {}).get("reference", "")
    if not PaymentTransaction.objects.filter(reference=reference).exists():
        return HttpResponse(status=200)
    try:
        # Always query Paystack: a signed event alone never fulfils a seat.
        finalize_payment(reference, verify_reference(reference))
    except ValidationError:
        return HttpResponse(status=503)
    return HttpResponse(status=200)
