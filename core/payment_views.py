from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect

from .payment_service import confirm_with_wallet


@login_required
def wallet_checkout(request, booking_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        booking = confirm_with_wallet(user=request.user, booking_id=booking_id)
        messages.success(request, f"Payment successful. Ticket {booking.reference} is confirmed.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("my_bookings")
