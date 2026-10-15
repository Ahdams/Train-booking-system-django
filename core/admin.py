"""Inventory management and read-only financial records."""
from django.contrib import admin
from .models import Station, Route, Train, Coach, Seat, Schedule, Fare, Booking, Wallet, WalletTransaction, PassengerReport

for model in (Station, Route, Train, Coach, Seat, Schedule, Fare, PassengerReport):
    admin.site.register(model)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "schedule", "travel_date", "seat", "status", "fare_paid")
    list_filter = ("status", "travel_date")
    search_fields = ("reference", "user__username", "passenger_name")
    readonly_fields = ("reference", "user", "schedule", "travel_date", "seat", "passenger_name", "fare_paid", "status", "hold_expires_at", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance")
    search_fields = ("user__username",)
    readonly_fields = ("user", "balance")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "booking", "kind", "amount", "balance_after", "created_at")
    list_filter = ("kind",)
    readonly_fields = ("wallet", "booking", "kind", "amount", "balance_after", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
