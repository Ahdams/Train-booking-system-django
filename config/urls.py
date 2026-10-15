from django.contrib import admin
from django.urls import path
from core.views import home
from core.reservation_views import reserve, cancel_reservation
from core.journey_views import search_journeys, available_seats
from core.route_views import origins, destinations
from core.account_views import register, dashboard, my_bookings, PassengerLoginView, PassengerLogoutView

urlpatterns = [path('reservations/hold/', reserve, name='reserve_seat'), path('reservations/<int:booking_id>/cancel/', cancel_reservation, name='cancel_reservation'), path('journeys/', search_journeys, name='search_journeys'), path('journeys/<int:schedule_id>/seats/', available_seats, name='available_seats'), path('accounts/register/', register, name='register'), path('accounts/login/', PassengerLoginView.as_view(), name='login'), path('accounts/logout/', PassengerLogoutView.as_view(), name='logout'), path('account/', dashboard, name='dashboard'), path('account/bookings/', my_bookings, name='my_bookings'), path('routes/origins/', origins, name='origins'), path('routes/destinations/', destinations, name='destinations'), path('admin/', admin.site.urls), path('', home, name='home')]
