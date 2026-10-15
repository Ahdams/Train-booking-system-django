from django.contrib.auth import login
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import PassengerRegistrationForm
from .models import Booking, PassengerReport, Wallet


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = PassengerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            Wallet.objects.create(user=user)
        login(request, user)
        return redirect("dashboard")
    return render(request, "core/register.html", {"form": form})


class PassengerLoginView(LoginView):
    template_name = "core/login.html"
    redirect_authenticated_user = True


class PassengerLogoutView(LogoutView):
    next_page = reverse_lazy("home")


@login_required
def dashboard(request):
    bookings = Booking.objects.filter(user=request.user).select_related(
        "schedule__route__origin", "schedule__route__destination", "seat"
    ).order_by("-created_at")[:5]
    reports = PassengerReport.objects.filter(user=request.user).order_by("-created_at")[:5]
    wallet = Wallet.objects.filter(user=request.user).first()
    return render(request, "core/dashboard.html", {
        "bookings": bookings,
        "reports": reports,
        "wallet_balance": wallet.balance if wallet else 0,
    })


@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).select_related(
        "schedule__route__origin", "schedule__route__destination", "seat"
    ).order_by("-created_at")
    return render(request, "core/bookings.html", {"bookings": bookings})
