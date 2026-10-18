from datetime import date, time, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import IdentityReview, Station, Route, Train, Coach, Seat, Schedule, Booking


class AlertTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="alertsuser", password="SecurePassword123!")
        self.client.force_login(self.user)

    def test_identity_review_alert(self):
        staff = get_user_model().objects.create_user(username="reviewer", password="SecurePassword123!", is_staff=True)
        IdentityReview.objects.create(user=self.user, nin_digest="a" * 64, nin_last_four="1234",
            document="identity_documents/test.png", status=IdentityReview.Status.APPROVED,
            reviewed_by=staff, reviewed_at=timezone.now())
        response = self.client.get(reverse("notifications"))
        self.assertContains(response, "Identity document review update")
        self.assertContains(response, "View identity review")

    def test_upcoming_departure_alert(self):
        now = timezone.localtime(timezone.now()) + timedelta(minutes=15)
        origin = Station.objects.create(code="KAD-AL", name="Rigasa", city="Kaduna", state="Kaduna")
        destination = Station.objects.create(code="ABJ-AL", name="Idu", city="Abuja", state="FCT")
        route = Route.objects.create(origin=origin, destination=destination)
        train = Train.objects.create(code="ALERT-TRAIN", name="Alert Express")
        coach = Coach.objects.create(train=train, code="A", travel_class="standard")
        seat = Seat.objects.create(coach=coach, label="1")
        schedule = Schedule.objects.create(route=route, train=train, departure_time=now.time().replace(tzinfo=None), arrival_time=time(23, 59))
        Booking.objects.create(reference="ALERT-BOOK-1", user=self.user, schedule=schedule,
            seat=seat, travel_date=now.date(), passenger_name="Test", fare_paid=5000, status=Booking.Status.CONFIRMED)
        self.assertContains(self.client.get(reverse("notifications")), "Your train departs soon")
