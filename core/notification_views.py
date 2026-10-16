"""Passenger-facing alerts derived from current booking and disruption state.

No external notification provider or extra database table is required.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import Booking, JourneyDisruption, PassengerReport, NotificationRead


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
                "booking": booking, "key": f"hold:{booking.pk}", "key": f"delay:{booking.pk}:{disruption.updated_at.isoformat()}", "key": f"cancel:{booking.pk}:{disruption.updated_at.isoformat()}",
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
    for report in PassengerReport.objects.filter(user=request.user).exclude(status=PassengerReport.Status.OPEN).order_by("-updated_at")[:20]:
        message = f"Your report '{report.subject}' is {report.get_status_display().lower()}."
        if report.admin_response:
            message += f" Staff response: {report.admin_response}"
        alerts.append({
            "level": "info", "title": "Dispute update", "message": message,
            "report": report, "key": f"report:{report.pk}:{report.updated_at.isoformat()}",
        })
    keys = {alert["key"] for alert in alerts}
    if request.method == "POST":
        key = request.POST.get("alert_key", "")
        if key in keys:
            NotificationRead.objects.get_or_create(user=request.user, alert_key=key)
        return redirect("notifications")
    read_keys = set(NotificationRead.objects.filter(user=request.user, alert_key__in=keys).values_list("alert_key", flat=True))
    for alert in alerts:
        alert["is_read"] = alert["key"] in read_keys
    response = render(request, "core/notifications.html", {"alerts": alerts, "unread_count": len(keys - read_keys)})
    response["Cache-Control"] = "private, no-store"
    return response
