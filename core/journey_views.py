"""Route-specific train discovery and dated seat availability."""
from datetime import date
import re

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Booking, Route, Schedule, Seat, JourneyDisruption


WEEKDAY_FIELDS = (
    "operates_monday", "operates_tuesday", "operates_wednesday",
    "operates_thursday", "operates_friday", "operates_saturday",
    "operates_sunday",
)


def _date(value):
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    return parsed if parsed >= timezone.localdate() else None


def search_journeys(request):
    origin = request.GET.get("from", "")
    destination = request.GET.get("to", "")
    travel_date = _date(request.GET.get("date"))
    errors = []
    if not origin.isdecimal() or not destination.isdecimal():
        errors.append("Choose valid departure and arrival stations.")
    if origin == destination:
        errors.append("Departure and arrival must be different.")
    if request.GET.get("date") and not travel_date:
        errors.append("Choose a valid travel date that is not in the past.")

    schedules = Schedule.objects.none()
    if not errors:
        routes = Route.objects.filter(
            origin_id=int(origin), destination_id=int(destination),
            is_active=True, origin__is_active=True, destination__is_active=True,
        )
        schedules = Schedule.objects.filter(
            route__in=routes, is_active=True, train__is_active=True
        ).select_related("route__origin", "route__destination", "train").order_by("departure_time")
        if travel_date:
            schedules = schedules.filter(**{WEEKDAY_FIELDS[travel_date.weekday()]: True})
            cancelled = JourneyDisruption.objects.filter(travel_date=travel_date, status=JourneyDisruption.Status.CANCELLED).values_list('schedule_id', flat=True)
            schedules = schedules.exclude(pk__in=cancelled)
            if travel_date == timezone.localdate():
                # Delays may keep a journey bookable after its original departure.
                now_time = timezone.localtime().time()
                delayed_ids = JourneyDisruption.objects.filter(
                    travel_date=travel_date, status=JourneyDisruption.Status.DELAYED,
                    revised_departure_time__gt=now_time,
                ).values_list('schedule_id', flat=True)
                schedules = schedules.filter(Q(departure_time__gt=now_time) | Q(pk__in=delayed_ids))

    return render(request, "core/journey_results.html", {
        "schedules": schedules,
        "travel_date": travel_date,
        "errors": errors,
        "origin": origin,
        "destination": destination,
    })


def available_seats(request, schedule_id):
    travel_date = _date(request.GET.get("date"))
    if not travel_date:
        raise Http404("A valid future travel date is required.")
    schedule = get_object_or_404(
        Schedule.objects.select_related("route__origin", "route__destination", "train"),
        pk=schedule_id, is_active=True, train__is_active=True,
        route__is_active=True, route__origin__is_active=True, route__destination__is_active=True,
    )
    if JourneyDisruption.objects.filter(schedule=schedule, travel_date=travel_date, status=JourneyDisruption.Status.CANCELLED).exists():
        raise Http404("This journey has been cancelled.")
    if not getattr(schedule, WEEKDAY_FIELDS[travel_date.weekday()]):
        raise Http404("This train does not run on the selected date.")
    disruption = JourneyDisruption.objects.filter(schedule=schedule, travel_date=travel_date).first()
    effective_departure = disruption.revised_departure_time if disruption and disruption.status == JourneyDisruption.Status.DELAYED else schedule.departure_time
    if travel_date == timezone.localdate() and effective_departure <= timezone.localtime().time():
        raise Http404("This train has already departed.")
    reserved_ids = Booking.objects.filter(
        schedule=schedule, travel_date=travel_date,
    ).filter(
        Q(status=Booking.Status.CONFIRMED) |
        Q(status=Booking.Status.HELD, hold_expires_at__gt=timezone.now())
    ).values_list("seat_id", flat=True)
    seats = Seat.objects.filter(
        coach__train=schedule.train, coach__train__is_active=True, is_active=True
    ).select_related("coach").order_by("coach__code", "label")
    # Natural order keeps numeric labels 1, 2, 3 ... 12 rather than 1, 10, 11, 12, 2.
    seats = sorted(seats, key=lambda seat: (
        seat.coach.code.casefold(),
        [(0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.split(r"(\\d+)", seat.label)],
    ))
    reserved_ids = set(reserved_ids)
    seat_rows = [{"seat": seat, "available": seat.id not in reserved_ids} for seat in seats]
    fares = {fare.travel_class: fare.amount for fare in schedule.fares.all()}
    for row in seat_rows:
        row["fare"] = fares.get(row["seat"].coach.travel_class)
        if row["fare"] is None:
            row["available"] = False
    return render(request, "core/available_seats.html", {
        "schedule": schedule, "travel_date": travel_date, "seat_rows": seat_rows,
        "disruption": disruption, "effective_departure": effective_departure,
    })
