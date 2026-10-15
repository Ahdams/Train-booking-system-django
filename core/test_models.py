from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Station, Route, Train, Coach, Seat, Schedule, Booking


class RailInventoryTests(TestCase):
    def setUp(self):
        self.lagos = Station.objects.create(code="LOS", name="Mobolaji Johnson", city="Lagos", state="Lagos")
        self.ibadan = Station.objects.create(code="IBD", name="Moniya", city="Ibadan", state="Oyo")
        self.route = Route.objects.create(origin=self.lagos, destination=self.ibadan)
        self.train = Train.objects.create(code="TR-001", name="Express")
        self.coach = Coach.objects.create(train=self.train, code="C1", travel_class="standard")
        self.seat = Seat.objects.create(coach=self.coach, label="A1")
        self.schedule = Schedule.objects.create(route=self.route, train=self.train, departure_time=time(9), arrival_time=time(12))
        self.user1 = get_user_model().objects.create_user(username="passenger1", password="secure-password-123")
        self.user2 = get_user_model().objects.create_user(username="passenger2", password="secure-password-123")

    def book(self, user, reference, status="confirmed"):
        return Booking.objects.create(
            reference=reference, user=user, schedule=self.schedule,
            travel_date=date(2026, 12, 1), seat=self.seat,
            passenger_name=user.username, fare_paid=Decimal("5000.00"), status=status,
        )

    def test_different_users_cannot_book_same_seat_for_same_departure(self):
        self.book(self.user1, "RF-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.book(self.user2, "RF-002")

    def test_cancelled_seat_can_be_rebooked(self):
        self.book(self.user1, "RF-003", status="cancelled")
        second = self.book(self.user2, "RF-004")
        self.assertEqual(second.status, "confirmed")

    def test_same_seat_on_another_date_is_allowed(self):
        self.book(self.user1, "RF-005")
        booking = self.book(self.user2, "RF-006", status="cancelled")
        booking.travel_date = date(2026, 12, 2)
        booking.status = "confirmed"
        booking.save()
        self.assertEqual(Booking.objects.filter(status="confirmed").count(), 2)

    def test_duplicate_coach_seat_label_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Seat.objects.create(coach=self.coach, label="A1")

    def test_route_cannot_start_and_end_at_same_station(self):
        from django.core.exceptions import ValidationError
        route = Route(origin=self.lagos, destination=self.lagos)
        with self.assertRaises(ValidationError):
            route.full_clean()

    def test_booking_seat_must_belong_to_scheduled_train(self):
        from django.core.exceptions import ValidationError
        other_train = Train.objects.create(code="TR-002", name="Another train")
        other_coach = Coach.objects.create(train=other_train, code="C1", travel_class="standard")
        other_seat = Seat.objects.create(coach=other_coach, label="A1")
        booking = Booking(
            reference="RF-WRONG-TRAIN", user=self.user1, schedule=self.schedule,
            travel_date=date(2026, 12, 1), seat=other_seat,
            passenger_name="Passenger One", fare_paid=Decimal("5000.00"),
            status="confirmed",
        )
        with self.assertRaises(ValidationError):
            booking.full_clean()

    def test_held_booking_blocks_confirmed_booking(self):
        self.book(self.user1, "RF-HELD", status="held")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.book(self.user2, "RF-CONFIRMED")

    def test_expired_booking_frees_seat(self):
        self.book(self.user1, "RF-EXPIRED", status="expired")
        booking = self.book(self.user2, "RF-NEW")
        self.assertEqual(booking.status, "confirmed")
