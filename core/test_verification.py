from datetime import timedelta, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Coach, Fare, Route, Schedule, Seat, Station, Train, Wallet
from .payment_service import confirm_with_wallet
from .reservation_service import reserve_seat


class VerificationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.passenger = User.objects.create_user(username="verifyrider", password="Password123!")
        self.staff = User.objects.create_user(username="verifystaff", password="Password123!", is_staff=True)
        Wallet.objects.create(user=self.passenger, balance=Decimal("5000"))
        a = Station.objects.create(code="VKA", name="Kaduna", city="Kaduna", state="Kaduna")
        b = Station.objects.create(code="VAB", name="Abuja", city="Abuja", state="FCT")
        route = Route.objects.create(origin=a, destination=b)
        train = Train.objects.create(code="VTR", name="Verification Express")
        coach = Coach.objects.create(train=train, code="A", travel_class="standard")
        seat = Seat.objects.create(coach=coach, label="1")
        schedule = Schedule.objects.create(route=route, train=train, departure_time=time(23, 59), arrival_time=time(1))
        Fare.objects.create(schedule=schedule, travel_class="standard", amount=Decimal("2000"))
        self.booking = reserve_seat(user=self.passenger, schedule_id=schedule.pk, seat_id=seat.pk, travel_date=timezone.localdate() + timedelta(days=2))
        self.url = reverse("verify_ticket")

    def test_only_staff_can_verify(self):
        self.client.force_login(self.passenger)
        response = self.client.get(self.url, {"reference": self.booking.reference})
        self.assertEqual(response.status_code, 302)

    def test_held_ticket_is_invalid(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.url, {"reference": self.booking.reference}), "not confirmed")

    def test_paid_confirmed_ticket_is_valid(self):
        confirm_with_wallet(user=self.passenger, booking_id=self.booking.pk)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.url, {"reference": self.booking.reference.lower()}), "Valid confirmed ticket")

    def test_unknown_reference_is_not_found(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.url, {"reference": "RF-NONEXISTENT"}), "Ticket not found")
