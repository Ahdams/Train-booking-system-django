from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Booking, Coach, JourneyDisruption, Route, Schedule, Seat, Station, Train, PassengerReport


class NotificationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alertuser", password="Pass12345!")
        self.other = User.objects.create_user(username="alertother", password="Pass12345!")
        origin = Station.objects.create(code="AL1", name="Alpha", city="Alpha", state="FCT")
        destination = Station.objects.create(code="AL2", name="Beta", city="Beta", state="FCT")
        route = Route.objects.create(origin=origin, destination=destination)
        train = Train.objects.create(code="ALERT1", name="Alert Express")
        self.schedule = Schedule.objects.create(route=route, train=train, departure_time="23:59", arrival_time="23:59")
        coach = Coach.objects.create(train=train, code="A", travel_class=Coach.TravelClass.STANDARD)
        self.seat = Seat.objects.create(coach=coach, label="1")
        self.day = timezone.localdate() + timedelta(days=2)
        self.url = reverse("notifications")

    def booking(self, user, status=Booking.Status.CONFIRMED, label="A"):
        return Booking.objects.create(reference="ALERT-" + label, user=user, schedule=self.schedule,
            travel_date=self.day, seat=self.seat, passenger_name=user.username,
            fare_paid=0, status=status)

    def test_login_required(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_no_alerts_for_unaffected_user(self):
        self.booking(self.other)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "No active journey or dispute alerts")
        self.assertNotContains(response, "ALERT-A")

    def test_delayed_journey_alert(self):
        self.booking(self.user)
        JourneyDisruption.objects.create(schedule=self.schedule, travel_date=self.day,
            status=JourneyDisruption.Status.DELAYED, revised_departure_time="23:59",
            reason="Track maintenance")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Departure time changed")
        self.assertContains(response, "Track maintenance")
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_cancelled_journey_alert(self):
        self.booking(self.user, status=Booking.Status.CANCELLED)
        JourneyDisruption.objects.create(schedule=self.schedule, travel_date=self.day,
            status=JourneyDisruption.Status.CANCELLED, reason="Safety inspection")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Journey cancelled")
        self.assertContains(response, "Safety inspection")

    def test_dispute_resolution_and_staff_response_visible_to_owner(self):
        PassengerReport.objects.create(user=self.user, subject="Refund enquiry",
            description="Refund missing", status=PassengerReport.Status.RESOLVED,
            admin_response="Refund processed to your wallet.")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertContains(response, "Dispute update")
        self.assertContains(response, "Refund processed to your wallet.")
        self.assertContains(response, "View my dispute")

    def test_other_passengers_disputes_remain_private(self):
        PassengerReport.objects.create(user=self.other, subject="Private dispute",
            description="Confidential issue", status=PassengerReport.Status.IN_PROGRESS,
            admin_response="Private staff reply")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Private dispute")
        self.assertNotContains(response, "Private staff reply")

    def test_open_dispute_does_not_create_update_alert(self):
        PassengerReport.objects.create(user=self.user, subject="New report",
            description="Awaiting review", status=PassengerReport.Status.OPEN)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertNotContains(response, "Dispute update")

    def test_read_receipt_for_dispute(self):
        report = PassengerReport.objects.create(user=self.user, subject="Refund", description="Question", status=PassengerReport.Status.RESOLVED)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.context["unread_count"], 1)
        key = response.context["alerts"][0]["key"]
        self.assertEqual(self.client.post(self.url, {"alert_key": key}).status_code, 302)
        self.assertEqual(self.client.get(self.url).context["unread_count"], 0)
