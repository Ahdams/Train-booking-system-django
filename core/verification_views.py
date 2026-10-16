"""Staff-only ticket verification. Never expose passenger details to the public."""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone

from .models import Booking, WalletTransaction, JourneyDisruption
from .reservation_service import departure_at


@staff_member_required
def verify_ticket(request):
    reference = request.GET.get("reference", "").strip().upper()
    booking = None
    verdict = None
    if reference:
        if len(reference) > 32:
            verdict = "Invalid reference."
        else:
            booking = Booking.objects.select_related(
                "user", "schedule__route__origin", "schedule__route__destination",
                "schedule__train", "seat__coach",
            ).filter(reference=reference).first()
            if booking is None:
                verdict = "Ticket not found."
            elif booking.status != Booking.Status.CONFIRMED:
                verdict = "Ticket is not valid: booking is not confirmed."
            elif booking.fare_paid > 0 and not WalletTransaction.objects.filter(
                booking=booking, kind=WalletTransaction.Kind.DEBIT,
                amount=booking.fare_paid,
            ).exists():
                verdict = "Ticket is not valid: payment is unverified."
            elif JourneyDisruption.objects.filter(schedule_id=booking.schedule_id, travel_date=booking.travel_date, status=JourneyDisruption.Status.CANCELLED).exists():
                verdict = "Ticket is not valid: journey cancelled by operator."
            elif departure_at(booking) <= timezone.now():
                verdict = "Ticket is for a departed journey."
            else:
                verdict = "Valid confirmed ticket."
    response = render(request, "core/verify_ticket.html", {
        "reference": reference, "booking": booking, "verdict": verdict,
    })
    response["Cache-Control"] = "private, no-store"
    return response
