from django.contrib import admin
from django.urls import path
from core.views import home
from core.report_views import reports, staff_reports, staff_report_detail
from core.ticket_views import ticket
from core.payment_views import wallet_checkout
from core.reservation_views import reserve, cancel_reservation
from core.journey_views import search_journeys, available_seats
from core.route_views import origins, destinations
from core.account_views import register, dashboard, my_bookings, PassengerLoginView, PassengerLogoutView

urlpatterns = [path('account/reports/', reports, name='reports'), path('staff/reports/', staff_reports, name='staff_reports'), path('staff/reports/<int:report_id>/', staff_report_detail, name='staff_report_detail'), path('bookings/<int:booking_id>/ticket/', ticket, name='ticket'), path('bookings/<int:booking_id>/pay/', wallet_checkout, name='wallet_checkout'), path('reservations/hold/', reserve, name='reserve_seat'), path('reservations/<int:booking_id>/cancel/', cancel_reservation, name='cancel_reservation'), path('journeys/', search_journeys, name='search_journeys'), path('journeys/<int:schedule_id>/seats/', available_seats, name='available_seats'), path('accounts/register/', register, name='register'), path('accounts/login/', PassengerLoginView.as_view(), name='login'), path('accounts/logout/', PassengerLogoutView.as_view(), name='logout'), path('account/', dashboard, name='dashboard'), path('account/bookings/', my_bookings, name='my_bookings'), path('routes/origins/', origins, name='origins'), path('routes/destinations/', destinations, name='destinations'), path('admin/', admin.site.urls), path('', home, name='home')]
