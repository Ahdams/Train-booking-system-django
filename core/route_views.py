"""Public station and destination endpoints backed by active routes."""
from django.http import JsonResponse
from .models import Route, Station


def origins(request):
    ids = Route.objects.filter(is_active=True, origin__is_active=True, destination__is_active=True).values_list("origin_id", flat=True)
    stations = Station.objects.filter(id__in=ids).order_by("city", "name")
    return JsonResponse({"stations": [{"id": s.id, "name": s.name, "city": s.city} for s in stations]})


def destinations(request):
    origin = request.GET.get("origin")
    if not origin or not origin.isdecimal():
        return JsonResponse({"stations": []})
    ids = Route.objects.filter(is_active=True, origin_id=int(origin), origin__is_active=True, destination__is_active=True).values_list("destination_id", flat=True)
    stations = Station.objects.filter(id__in=ids).order_by("city", "name")
    return JsonResponse({"stations": [{"id": s.id, "name": s.name, "city": s.city} for s in stations]})
