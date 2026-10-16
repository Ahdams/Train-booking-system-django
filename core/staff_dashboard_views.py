"""Read-only operations dashboard for authorized staff."""
from datetime import timedelta
from decimal import Decimal
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone
from .models import Booking, JourneyDisruption, PassengerReport, Schedule, WalletTransaction


@staff_member_required
def staff_dashboard(request):
    today = timezone.localdate()
    recent = timezone.now() - timedelta(days=30)
    bookings = Booking.objects.all()
    transactions = WalletTransaction.objects.all()
    context = {
        "total_bookings": bookings.count(),
        "confirmed_bookings": bookings.filter(status=Booking.Status.CONFIRMED).count(),
        "active_holds": bookings.filter(status=Booking.Status.HELD, hold_expires_at__gt=timezone.now()).count(),
        "upcoming_confirmed": bookings.filter(status=Booking.Status.CONFIRMED, travel_date__gte=today).count(),
        "open_reports": PassengerReport.objects.filter(status=PassengerReport.Status.OPEN).count(),
        "in_progress_reports": PassengerReport.objects.filter(status=PassengerReport.Status.IN_PROGRESS).count(),
        "upcoming_disruptions": JourneyDisruption.objects.filter(travel_date__gte=today).count(),
        "active_schedules": Schedule.objects.filter(is_active=True).count(),
        "wallet_debits_30d": transactions.filter(kind=WalletTransaction.Kind.DEBIT, created_at__gte=recent).aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
        "wallet_refunds_30d": transactions.filter(kind=WalletTransaction.Kind.REFUND, created_at__gte=recent).aggregate(total=Sum("amount"))["total"] or Decimal("0.00"),
        "recent_bookings": bookings.select_related("user", "schedule__route__origin", "schedule__route__destination").order_by("-created_at")[:10],
        "recent_transactions": transactions.select_related("wallet__user", "booking").order_by("-created_at")[:8],
        "recent_reports": PassengerReport.objects.select_related("user").order_by("-created_at")[:8],
        "recent_disruptions": JourneyDisruption.objects.select_related("schedule__train").order_by("-updated_at")[:8],
    }
    response = render(request, "core/staff_dashboard.html", context)
    response["Cache-Control"] = "private, no-store"
    return response
