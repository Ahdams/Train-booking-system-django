from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse

from .reservation_service import cancel_hold, reserve_seat


@login_required
def reserve(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        travel_date = date.fromisoformat(request.POST.get("date", ""))
        reserve_seat(user=request.user, schedule_id=int(request.POST["schedule_id"]),
                     seat_id=int(request.POST["seat_id"]), travel_date=travel_date)
        messages.success(request, "Seat reserved for 10 minutes. Cancel it before reserving another.")
    except (ValidationError, ValueError, KeyError) as exc:
        messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else "Invalid reservation details.")
    return redirect("my_bookings")


@login_required
def cancel_reservation(request, booking_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        cancel_hold(user=request.user, booking_id=booking_id)
        messages.success(request, "Reservation cancelled. You may reserve another seat.")
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    return redirect("my_bookings")
