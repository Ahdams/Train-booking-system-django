from datetime import timedelta, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Coach, Fare, Route, Schedule, Seat, Station, Train, Wallet, WalletTransaction
from .reservation_service import reserve_seat
from .payment_service import confirm_with_wallet


class TicketTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ticketuser", password="Password123!")
        self.other = get_user_model().objects.create_user(username="otherticket", password="Password123!")
        Wallet.objects.create(user=self.user, balance=Decimal("9000"))
        origin = Station.objects.create(code="TKTK", name="Rigasa", city="Kaduna", state="Kaduna")
        destination = Station.objects.create(code="TKTA", name="Idu", city="Abuja", state="FCT")
        route = Route.objects.create(origin=origin, destination=destination)
        train = Train.objects.create(code="TKTR", name="RailFlow Express")
        coach = Coach.objects.create(train=train, code="A", travel_class="standard")
        seat = Seat.objects.create(coach=coach, label="1")
        schedule = Schedule.objects.create(route=route, train=train, departure_time=time(23, 59), arrival_time=time(1))
        Fare.objects.create(schedule=schedule, travel_class="standard", amount=Decimal("3000"))
        self.booking = reserve_seat(user=self.user, schedule_id=schedule.pk, seat_id=seat.pk, travel_date=timezone.localdate() + timedelta(days=2))
        self.url = reverse("ticket", args=[self.booking.pk])

    def test_hold_is_not_a_ticket(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_paid_ticket_is_private_and_printable(self):
        confirm_with_wallet(user=self.user, booking_id=self.booking.pk)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "RailFlow Express")
        self.assertContains(response, self.booking.reference)
        self.assertContains(response, "Print / Save as PDF")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_confirmed_without_payment_proof_is_not_downloadable(self):
        self.booking.status = Booking.Status.CONFIRMED
        self.booking.save(update_fields=["status"])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 404)
