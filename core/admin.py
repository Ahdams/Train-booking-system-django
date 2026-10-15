from django.contrib import admin
from .models import Station, Route, Train, Coach, Seat, Schedule, Fare, Booking, Wallet, WalletTransaction, PassengerReport

for model in (Station, Route, Train, Coach, Seat, Schedule, Fare, Booking, Wallet, WalletTransaction, PassengerReport):
    admin.site.register(model)
