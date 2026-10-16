"""Core rail inventory and reservation data model.

Inventory belongs to a train; reservations belong to a dated schedule.
Prices are stored as NGN amounts, never floating point.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F


class Station(models.Model):
    code = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Route(models.Model):
    origin = models.ForeignKey(Station, on_delete=models.PROTECT, related_name="departing_routes")
    destination = models.ForeignKey(Station, on_delete=models.PROTECT, related_name="arriving_routes")
    name = models.CharField(max_length=160, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["origin", "destination"], name="unique_route_direction"),
            models.CheckConstraint(condition=~Q(origin=F("destination")), name="different_route_stations"),
        ]

    def clean(self):
        if self.origin_id and self.destination_id and self.origin_id == self.destination_id:
            raise ValidationError("Origin and destination must be different.")

    def __str__(self):
        return self.name or f"{self.origin} → {self.destination}"


class Train(models.Model):
    code = models.CharField(max_length=24, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Coach(models.Model):
    class TravelClass(models.TextChoices):
        STANDARD = "standard", "Standard"
        FIRST = "first", "First Class"
        EXECUTIVE = "executive", "Executive"

    train = models.ForeignKey(Train, on_delete=models.PROTECT, related_name="coaches")
    code = models.CharField(max_length=12)
    travel_class = models.CharField(max_length=16, choices=TravelClass.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["train", "code"], name="unique_coach_per_train")]

    def __str__(self):
        return f"{self.train.code} / {self.code}"


class Seat(models.Model):
    coach = models.ForeignKey(Coach, on_delete=models.PROTECT, related_name="seats")
    label = models.CharField(max_length=12)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["coach", "label"], name="unique_seat_per_coach")]

    def __str__(self):
        return f"{self.coach.code}-{self.label}"


class Schedule(models.Model):
    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="schedules")
    train = models.ForeignKey(Train, on_delete=models.PROTECT, related_name="schedules")
    departure_time = models.TimeField()
    arrival_time = models.TimeField()
    operates_monday = models.BooleanField(default=True)
    operates_tuesday = models.BooleanField(default=True)
    operates_wednesday = models.BooleanField(default=True)
    operates_thursday = models.BooleanField(default=True)
    operates_friday = models.BooleanField(default=True)
    operates_saturday = models.BooleanField(default=True)
    operates_sunday = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.route} at {self.departure_time}"


class Fare(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.PROTECT, related_name="fares")
    travel_class = models.CharField(max_length=16, choices=Coach.TravelClass.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["schedule", "travel_class"], name="unique_fare_class_schedule"),
            models.CheckConstraint(condition=Q(amount__gte=0), name="fare_nonnegative"),
        ]


class Booking(models.Model):
    class Status(models.TextChoices):
        HELD = "held", "Held"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    reference = models.CharField(max_length=32, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rail_bookings")
    schedule = models.ForeignKey(Schedule, on_delete=models.PROTECT, related_name="bookings")
    travel_date = models.DateField()
    seat = models.ForeignKey(Seat, on_delete=models.PROTECT, related_name="bookings")
    passenger_name = models.CharField(max_length=150)
    fare_paid = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.HELD)
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "travel_date", "seat"],
                condition=Q(status__in=["held", "confirmed"]),
                name="one_active_booking_per_departure_seat",
            ),
            models.CheckConstraint(condition=Q(fare_paid__gte=0), name="booking_fare_nonnegative"),
        ]

    def clean(self):
        if self.seat_id and self.schedule_id and self.seat.coach.train_id != self.schedule.train_id:
            raise ValidationError("Seat must belong to the scheduled train.")

    def __str__(self):
        return self.reference


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rail_wallet")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(balance__gte=0), name="wallet_balance_nonnegative")]


class WalletTransaction(models.Model):
    class Kind(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"
        REFUND = "refund", "Refund"

    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="transactions")
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="wallet_transactions", null=True, blank=True)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="wallet_transaction_positive")]


class PassengerReport(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rail_reports")
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True)
    subject = models.CharField(max_length=160)
    description = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    admin_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class JourneyDisruption(models.Model):
    """A dated schedule exception; never alters other days of the timetable."""
    class Status(models.TextChoices):
        DELAYED = "delayed", "Delayed"
        CANCELLED = "cancelled", "Cancelled"

    schedule = models.ForeignKey(Schedule, on_delete=models.PROTECT, related_name="disruptions")
    travel_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices)
    reason = models.TextField()
    revised_departure_time = models.TimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["schedule", "travel_date"], name="unique_dated_disruption"),
        ]

    def clean(self):
        if self.status == self.Status.DELAYED and self.revised_departure_time is None:
            raise ValidationError("A delayed journey needs a revised departure time.")
        if self.status == self.Status.CANCELLED and self.revised_departure_time is not None:
            raise ValidationError("Cancelled journeys cannot have a revised departure time.")
        if not self.reason.strip():
            raise ValidationError("Provide a reason for the disruption.")


class NotificationRead(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    alert_key = models.CharField(max_length=180)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "alert_key"),)


class StaffAuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    target_type = models.CharField(max_length=40)
    target_id = models.PositiveBigIntegerField()
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
