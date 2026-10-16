"""Private, printable tickets for confirmed bookings."""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import Booking, WalletTransaction, JourneyDisruption


@login_required
def ticket(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related(
            "schedule__route__origin", "schedule__route__destination",
            "schedule__train", "seat__coach",
        ),
        pk=booking_id, user=request.user, status=Booking.Status.CONFIRMED,
    )
    if booking.fare_paid > 0 and not WalletTransaction.objects.filter(
        booking=booking, kind=WalletTransaction.Kind.DEBIT
    ).exists():
        raise Http404("No verified payment was recorded for this ticket.")
    disruption = JourneyDisruption.objects.filter(schedule_id=booking.schedule_id, travel_date=booking.travel_date).first()
    response = render(request, "core/ticket.html", {"booking": booking, "disruption": disruption})
    response["Cache-Control"] = "private, no-store"
    return response
