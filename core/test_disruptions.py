from datetime import timedelta, time
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Coach, Fare, JourneyDisruption, Route, Schedule, Seat, Station, Train
from .reservation_service import reserve_seat


class DisruptionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="disruptionrider", password="Password123!")
        self.staff = User.objects.create_user(username="disruptionstaff", password="Password123!", is_staff=True)
        a = Station.objects.create(code="DKA", name="Rigasa", city="Kaduna", state="Kaduna")
        b = Station.objects.create(code="DAB", name="Idu", city="Abuja", state="FCT")
        route = Route.objects.create(origin=a, destination=b)
        train = Train.objects.create(code="DTR", name="Disruption Express")
        coach = Coach.objects.create(train=train, code="A", travel_class="standard")
        self.seat = Seat.objects.create(coach=coach, label="1")
        self.schedule = Schedule.objects.create(route=route, train=train, departure_time=time(23, 59), arrival_time=time(1))
        Fare.objects.create(schedule=self.schedule, travel_class="standard", amount=Decimal("2000"))
        self.day = timezone.localdate() + timedelta(days=2)
        self.url = reverse("manage_disruptions")

    def test_only_staff_can_manage_disruptions(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_staff_can_cancel_dated_journey(self):
        self.client.force_login(self.staff)
        response = self.client.post(self.url, {
            "schedule": self.schedule.pk, "travel_date": self.day.isoformat(),
            "status": "cancelled", "reason": "Track maintenance",
            "revised_departure_time": "",
        })
        self.assertRedirects(response, self.url)
        self.assertTrue(JourneyDisruption.objects.filter(schedule=self.schedule, travel_date=self.day, status="cancelled").exists())

    def test_cancelled_journey_cannot_be_reserved(self):
        JourneyDisruption.objects.create(schedule=self.schedule, travel_date=self.day, status="cancelled", reason="Maintenance")
        with self.assertRaisesMessage(ValidationError, "cancelled"):
            reserve_seat(user=self.user, schedule_id=self.schedule.pk, seat_id=self.seat.pk, travel_date=self.day)

    def test_cancelled_date_does_not_affect_other_dates(self):
        JourneyDisruption.objects.create(schedule=self.schedule, travel_date=self.day, status="cancelled", reason="Maintenance")
        booking = reserve_seat(user=self.user, schedule_id=self.schedule.pk, seat_id=self.seat.pk, travel_date=self.day + timedelta(days=1))
        self.assertEqual(booking.status, "held")
