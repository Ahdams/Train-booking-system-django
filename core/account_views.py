from django.contrib.auth import login
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import PassengerRegistrationForm
from .models import Booking, PassengerReport, Wallet, WalletTransaction, IdentityReview
from .reservation_service import expire_holds


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
    expire_holds()
    bookings = Booking.objects.filter(user=request.user).select_related(
        "schedule__route__origin", "schedule__route__destination", "seat"
    ).order_by("-created_at")[:5]
    reports = PassengerReport.objects.filter(user=request.user).order_by("-created_at")[:5]
    wallet = Wallet.objects.filter(user=request.user).first()
    return render(request, "core/dashboard.html", {
        "bookings": bookings,
        "reports": reports,
        "wallet_balance": wallet.balance if wallet else 0,
        "identity_review": IdentityReview.objects.filter(user=request.user).first(),
    })


@login_required
def my_bookings(request):
    expire_holds()
    bookings = Booking.objects.filter(user=request.user).select_related(
        "schedule__route__origin", "schedule__route__destination", "seat"
    ).order_by("-created_at")
    wallet = Wallet.objects.filter(user=request.user).first()
    transactions = WalletTransaction.objects.filter(wallet=wallet).select_related("booking").order_by("-created_at")[:20] if wallet else []
    return render(request, "core/bookings.html", {"bookings": bookings, "wallet_balance": wallet.balance if wallet else 0, "transactions": transactions})


from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth import get_user_model
from django.http import HttpResponseNotAllowed


class ProfileEmailForm(forms.Form):
    email = forms.EmailField(max_length=254)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("That email address is already used.")
        return email

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)


@login_required
def profile(request):
    form = ProfileEmailForm(request.POST or None, user=request.user, initial={"email": request.user.email})
    if request.method == "POST" and form.is_valid():
        request.user.email = form.cleaned_data["email"]
        request.user.save(update_fields=["email"])
        messages.success(request, "Your email address was updated.")
        return redirect("profile")
    return render(request, "core/profile.html", {"form": form})


@login_required
def close_account(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if request.user.is_staff:
        messages.error(request, "Staff accounts must be closed by an administrator.")
        return redirect("profile")
    if not request.user.check_password(request.POST.get("password", "")):
        messages.error(request, "Incorrect password. Your account was not closed.")
        return redirect("profile")
    from django.utils.crypto import get_random_string
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
        user.is_active = False
        user.email = ""
        user.save(update_fields=["is_active", "email"])
    logout(request)
    messages.success(request, "Your account is closed and sign-in is disabled. Booking and transaction records are retained for recordkeeping.")
    return redirect("home")
