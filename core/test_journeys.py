from datetime import timedelta, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Coach, Fare, Route, Schedule, Seat, Station, Train


class JourneyTests(TestCase):
    def setUp(self):
        self.kaduna = Station.objects.create(code="KAD", name="Rigasa", city="Kaduna", state="Kaduna")
        self.abuja = Station.objects.create(code="ABJ", name="Idu", city="Abuja", state="FCT")
        self.lagos = Station.objects.create(code="LOS", name="Lagos", city="Lagos", state="Lagos")
        self.ibadan = Station.objects.create(code="IBD", name="Ibadan", city="Ibadan", state="Oyo")
        self.route = Route.objects.create(origin=self.kaduna, destination=self.abuja)
        self.other_route = Route.objects.create(origin=self.lagos, destination=self.ibadan)
        self.train = Train.objects.create(code="KAD-ABJ", name="Kaduna Express")
        self.other_train = Train.objects.create(code="LOS-IBD", name="Lagos Express")
        self.schedule = Schedule.objects.create(route=self.route, train=self.train, departure_time=time(23, 59), arrival_time=time(1))
        Schedule.objects.create(route=self.other_route, train=self.other_train, departure_time=time(23, 59), arrival_time=time(1))
        coach = Coach.objects.create(train=self.train, code="A", travel_class="standard")
        self.seat = Seat.objects.create(coach=coach, label="1")
        Fare.objects.create(schedule=self.schedule, travel_class="standard", amount=Decimal("2500.00"))
        self.day = timezone.localdate() + timedelta(days=3)

    def search(self, **kwargs):
        params = {"from": str(self.kaduna.pk), "to": str(self.abuja.pk)}
        params.update(kwargs)
        return self.client.get(reverse("search_journeys"), params)

    def test_only_route_specific_train_is_shown(self):
        response = self.search()
        self.assertContains(response, "Kaduna Express")
        self.assertNotContains(response, "Lagos Express")

    def test_wrong_direction_has_no_train(self):
        response = self.search(**{"from": str(self.abuja.pk), "to": str(self.kaduna.pk)})
        self.assertNotContains(response, "Kaduna Express")

    def test_invalid_origin_rejected(self):
        response = self.search(**{"from": "bad"})
        self.assertContains(response, "Choose valid departure")

    def test_past_date_rejected(self):
        response = self.search(date="2020-01-01")
        self.assertContains(response, "not in the past")

    def test_inactive_route_is_hidden(self):
        self.route.is_active = False
        self.route.save()
        self.assertNotContains(self.search(), "Kaduna Express")

    def test_inactive_train_is_hidden(self):
        self.train.is_active = False
        self.train.save()
        self.assertNotContains(self.search(), "Kaduna Express")

    def test_schedule_weekday_filter(self):
        field = ("operates_monday", "operates_tuesday", "operates_wednesday", "operates_thursday", "operates_friday", "operates_saturday", "operates_sunday")[self.day.weekday()]
        setattr(self.schedule, field, False)
        self.schedule.save()
        self.assertNotContains(self.search(date=self.day.isoformat()), "Kaduna Express")

    def test_seat_availability_and_expired_hold(self):
        user = get_user_model().objects.create_user(username="seatuser", password="StrongPassword123!")
        Booking.objects.create(reference="TEST-HELD", user=user, schedule=self.schedule,
            travel_date=self.day, seat=self.seat, passenger_name="Seat User",
            fare_paid=Decimal("2500"), status="held",
            hold_expires_at=timezone.now() + timedelta(minutes=10))
        url = reverse("available_seats", args=[self.schedule.pk]) + "?date=" + self.day.isoformat()
        self.assertContains(self.client.get(url), "seat-unavailable")
        Booking.objects.filter(reference="TEST-HELD").update(hold_expires_at=timezone.now() - timedelta(minutes=1))
        self.assertContains(self.client.get(url), "seat-choice")
        self.assertNotContains(self.client.get(url), "seat-unavailable")

    def test_numeric_seats_render_in_natural_order(self):
        coach = self.seat.coach
        for label in ("2", "10", "11", "3"):
            Seat.objects.create(coach=coach, label=label)
        url = reverse("available_seats", args=[self.schedule.pk]) + "?date=" + self.day.isoformat()
        html = self.client.get(url).content.decode()
        positions = [html.index('data-label="' + label + '"') for label in ("1", "2", "3", "10", "11")]
        self.assertEqual(positions, sorted(positions))

    def test_premium_coaches_show_class_selectors_and_fares(self):
        coach = Coach.objects.create(train=self.train, code="B", travel_class=Coach.TravelClass.FIRST)
        Seat.objects.create(coach=coach, label="1")
        Fare.objects.create(schedule=self.schedule, travel_class=Coach.TravelClass.FIRST, amount=Decimal("8500.00"))
        url = reverse("available_seats", args=[self.schedule.pk]) + "?date=" + self.day.isoformat()
        response = self.client.get(url)
        self.assertContains(response, 'data-class-filter="first"')
        self.assertContains(response, 'data-coach-class="first"')
        self.assertContains(response, 'data-fare="8500.00"')
