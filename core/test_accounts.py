from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Booking, Wallet, PassengerReport, Station, Route, Train, Coach, Seat, Schedule
from datetime import date, time
from decimal import Decimal


class AccountTests(TestCase):
    def test_register_creates_non_staff_user_and_signs_in(self):
        response = self.client.post(reverse("register"), {
            "username": "newpassenger", "email": "passenger@example.com",
            "password1": "SecureExamplePassword456!", "password2": "SecureExamplePassword456!",
        })
        self.assertRedirects(response, reverse("dashboard"))
        user = get_user_model().objects.get(username="newpassenger")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.email, "passenger@example.com")

    def test_duplicate_email_rejected_case_insensitively(self):
        get_user_model().objects.create_user(username="existing", email="passenger@example.com", password="SomePassword456!")
        response = self.client.post(reverse("register"), {
            "username": "newpassenger", "email": "PASSENGER@example.com",
            "password1": "SecureExamplePassword456!", "password2": "SecureExamplePassword456!",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="newpassenger").exists())

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("login") + "?next=" + reverse("dashboard"))

    def test_logout_requires_post(self):
        user = get_user_model().objects.create_user(username="passenger", password="SecureExamplePassword456!")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))

    def test_passenger_cannot_see_other_users_bookings_or_reports(self):
        user1 = get_user_model().objects.create_user(username="passenger1", password="SecureExamplePassword456!")
        user2 = get_user_model().objects.create_user(username="passenger2", password="SecureExamplePassword456!")
        origin = Station.objects.create(code="KAD", name="Rigasa", city="Kaduna", state="Kaduna")
        destination = Station.objects.create(code="ABJ", name="Idu", city="Abuja", state="FCT")
        route = Route.objects.create(origin=origin, destination=destination)
        train = Train.objects.create(code="TRAIN1", name="Express")
        coach = Coach.objects.create(train=train, code="C1", travel_class="standard")
        seat = Seat.objects.create(coach=coach, label="A1")
        schedule = Schedule.objects.create(route=route, train=train, departure_time=time(8), arrival_time=time(11))
        Booking.objects.create(reference="PRIVATE-BOOKING-123", user=user2, schedule=schedule, travel_date=date(2026, 12, 1), seat=seat, passenger_name="Private", fare_paid=Decimal("5000"), status="confirmed")
        PassengerReport.objects.create(user=user2, subject="PRIVATE REPORT", description="Sensitive report")
        Wallet.objects.create(user=user2, balance=Decimal("123456.00"))
        self.client.force_login(user1)
        dashboard = self.client.get(reverse("dashboard"))
        bookings = self.client.get(reverse("my_bookings"))
        self.assertNotContains(dashboard, "PRIVATE-BOOKING-123")
        self.assertNotContains(dashboard, "PRIVATE REPORT")
        self.assertNotContains(dashboard, "123456.00")
        self.assertNotContains(bookings, "PRIVATE-BOOKING-123")
