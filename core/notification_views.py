"""Passenger-facing alerts derived from current booking and disruption state.

No external notification provider or extra database table is required.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from .models import Booking, JourneyDisruption


@login_required
def notifications(request):
    today = timezone.localdate()
    bookings = list(Booking.objects.filter(user=request.user, travel_date__gte=today)
        .select_related("schedule__route__origin", "schedule__route__destination")
        .order_by("travel_date", "schedule__departure_time"))
    keys = {(booking.schedule_id, booking.travel_date) for booking in bookings}
    disruptions = {
        (item.schedule_id, item.travel_date): item
        for item in JourneyDisruption.objects.filter(
            schedule_id__in={key[0] for key in keys}, travel_date__gte=today
        )
    }
    alerts = []
    for booking in bookings:
        disruption = disruptions.get((booking.schedule_id, booking.travel_date))
        route = f"{booking.schedule.route.origin.city} → {booking.schedule.route.destination.city}"
        if disruption and disruption.status == JourneyDisruption.Status.CANCELLED:
            alerts.append({
                "level": "urgent", "title": "Journey cancelled",
                "message": f"{route} on {booking.travel_date}: {disruption.reason}. Confirmed wallet payments are refunded in full by the operator.",
                "booking": booking,
            })
        elif disruption and disruption.status == JourneyDisruption.Status.DELAYED and booking.status in (Booking.Status.HELD, Booking.Status.CONFIRMED):
            alerts.append({
                "level": "warning", "title": "Departure time changed",
                "message": f"{route} on {booking.travel_date} now departs at {disruption.revised_departure_time.strftime('%H:%M')} (Nigeria time). {disruption.reason}",
                "booking": booking,
            })
        elif booking.status == Booking.Status.HELD and booking.hold_expires_at and booking.hold_expires_at > timezone.now():
            alerts.append({
                "level": "info", "title": "Seat reservation awaiting payment",
                "message": f"{route} on {booking.travel_date}: complete wallet checkout before your hold expires.",
                "booking": booking,
            })
    response = render(request, "core/notifications.html", {"alerts": alerts})
    response["Cache-Control"] = "private, no-store"
    return response
