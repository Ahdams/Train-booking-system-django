"""Populate local-only demonstration routes and a passenger wallet."""
from datetime import time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Coach, Fare, Route, Schedule, Seat, Station, Train, Wallet, WalletTransaction


class Command(BaseCommand):
    help = "Local demo only: create sample routes and credit a passenger wallet with fictitious NGN."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Existing passenger username")
        parser.add_argument("--amount", default="100000.00", help="Demo NGN credit")
        parser.add_argument("--no-credit", action="store_true", help="Refresh demo coaches and fares without adding wallet credit")

    def handle(self, *args, **options):
        if not settings.DEBUG or getattr(settings, "DJANGO_PRODUCTION", False):
            raise CommandError("Demo setup is disabled unless Django DEBUG is enabled.")
        if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Demo setup only supports local SQLite databases.")
        try:
            amount = Decimal(options["amount"])
        except Exception as exc:
            raise CommandError("Invalid amount.") from exc
        if not amount.is_finite() or amount < 0 or amount > Decimal("1000000") or (amount == 0 and not options["no_credit"]):
            raise CommandError("Amount must be between 0 and 1,000,000 NGN.")
        username = options["username"]
        with transaction.atomic():
            user = get_user_model().objects.filter(username=username).first()
            if user is None:
                raise CommandError("User does not exist. Register a passenger account first.")
            wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
            if not options["no_credit"]:
                wallet.balance += amount
                wallet.save(update_fields=["balance"])
                WalletTransaction.objects.create(wallet=wallet, kind=WalletTransaction.Kind.CREDIT, amount=amount, balance_after=wallet.balance)
            kaduna, _ = Station.objects.get_or_create(code="DEMO-KAD", defaults={"name": "Rigasa", "city": "Kaduna", "state": "Kaduna"})
            abuja, _ = Station.objects.get_or_create(code="DEMO-ABJ", defaults={"name": "Idu", "city": "Abuja", "state": "FCT"})
            route, _ = Route.objects.get_or_create(origin=kaduna, destination=abuja)
            train, _ = Train.objects.get_or_create(code="DEMO-EXP", defaults={"name": "RailFlow Demo Express"})
            coach, _ = Coach.objects.get_or_create(train=train, code="A", defaults={"travel_class": Coach.TravelClass.STANDARD})
            for n in range(1, 13):
                Seat.objects.get_or_create(coach=coach, label=str(n))
            # Premium demo inventory is fictional; no real private cabin is implied.
            for code, travel_class, count in (
                ("B", Coach.TravelClass.FIRST, 8),
                ("C", Coach.TravelClass.EXECUTIVE, 4),
            ):
                premium_coach, _ = Coach.objects.get_or_create(
                    train=train, code=code, defaults={"travel_class": travel_class}
                )
                for n in range(1, count + 1):
                    Seat.objects.get_or_create(coach=premium_coach, label=str(n))
            schedule, _ = Schedule.objects.get_or_create(route=route, train=train, departure_time=time(9, 0), arrival_time=time(11, 30))
            # Refresh all local demo-train departures, including previously seeded schedules.
            # Preserve existing prices where configured; only add missing fares.
            for demo_schedule in Schedule.objects.filter(train=train, route=route):
                for travel_class, price in (
                    (Coach.TravelClass.STANDARD, Decimal("5000.00")),
                    (Coach.TravelClass.FIRST, Decimal("8500.00")),
                    (Coach.TravelClass.EXECUTIVE, Decimal("12000.00")),
                ):
                    Fare.objects.get_or_create(
                        schedule=demo_schedule, travel_class=travel_class,
                        defaults={"amount": price},
                    )
        self.stdout.write(self.style.SUCCESS(f"Demo route and travel classes ready. Wallet balance: NGN {wallet.balance}."))
