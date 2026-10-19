"""End-to-end access checks for manual document approval and booking."""
from datetime import timedelta, time
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Booking, Coach, Fare, IdentityReview, Route, Schedule, Seat, Station, Train, Wallet

class ManualApprovalBookingTests(TestCase):
    def setUp(self):
        self.passenger = get_user_model().objects.create_user(username="journeypassenger", password="TestPassword123!")
        self.staff = get_user_model().objects.create_user(username="journeystaff", password="TestPassword123!", is_staff=True)
        Wallet.objects.create(user=self.passenger, balance=Decimal("10000"))
        a = Station.objects.create(code="JKA", name="Rigasa", city="Kaduna", state="Kaduna")
        b = Station.objects.create(code="JAB", name="Idu", city="Abuja", state="FCT")
        route = Route.objects.create(origin=a, destination=b)
        train = Train.objects.create(code="JTR", name="Journey Express")
        coach = Coach.objects.create(train=train, code="A", travel_class="standard")
        self.seat = Seat.objects.create(coach=coach, label="1")
        self.schedule = Schedule.objects.create(route=route, train=train, departure_time=time(23, 59), arrival_time=time(1))
        Fare.objects.create(schedule=self.schedule, travel_class="standard", amount=Decimal("3000"))
        self.day = timezone.localdate() + timedelta(days=2)

    def reserve(self):
        return self.client.post(reverse("reserve_seat"), {"schedule_id": self.schedule.pk, "seat_id": self.seat.pk, "date": self.day.isoformat()})

    def test_staff_approval_unlocks_reservation_and_wallet_checkout(self):
        self.client.force_login(self.passenger)
        self.assertRedirects(self.reserve(), reverse("identity_submit"))
        self.assertFalse(Booking.objects.exists())
        review = IdentityReview.objects.create(user=self.passenger, nin_digest="a" * 64, nin_last_four="8901", document="identity_documents/demo.png")
        self.client.force_login(self.staff)
        self.assertRedirects(self.client.post(reverse("identity_decision", args=[review.pk]), {"status": "approved"}), reverse("identity_reviews"))
        self.client.force_login(self.passenger)
        self.assertContains(self.client.get(reverse("notifications")), "Identity document review update")
        self.assertRedirects(self.reserve(), reverse("my_bookings"))
        booking = Booking.objects.get(user=self.passenger)
        self.assertEqual(booking.status, Booking.Status.HELD)
        self.assertEqual(self.client.post(reverse("wallet_checkout", args=[booking.pk])).status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(self.client.get(reverse("ticket", args=[booking.pk])).status_code, 200)
