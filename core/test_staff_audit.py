from datetime import timedelta, time
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import JourneyDisruption, PassengerReport, Route, Schedule, StaffAuditEvent, Station, Train


class StaffAuditTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(username="auditstaff", password="Pass12345!", is_staff=True)
        self.passenger = User.objects.create_user(username="auditpassenger", password="Pass12345!")

    def test_staff_report_resolution_records_actor(self):
        report = PassengerReport.objects.create(user=self.passenger, subject="Seat issue", description="Broken seat")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("staff_report_detail", args=[report.pk]), {
            "status": PassengerReport.Status.RESOLVED, "admin_response": "Issue resolved.",
        })
        self.assertEqual(response.status_code, 302)
        event = StaffAuditEvent.objects.get(target_type="passenger_report", target_id=report.pk)
        self.assertEqual(event.actor, self.staff)
        self.assertEqual(event.action, "report_updated")

    def test_invalid_report_update_does_not_create_audit_event(self):
        report = PassengerReport.objects.create(user=self.passenger, subject="Seat issue", description="Broken seat")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("staff_report_detail", args=[report.pk]), {
            "status": PassengerReport.Status.RESOLVED, "admin_response": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(StaffAuditEvent.objects.exists())

    def test_staff_disruption_records_actor(self):
        a = Station.objects.create(code="AUK", name="Alpha", city="Kaduna", state="Kaduna")
        b = Station.objects.create(code="AUA", name="Beta", city="Abuja", state="FCT")
        route = Route.objects.create(origin=a, destination=b)
        train = Train.objects.create(code="AUT", name="Audit Train")
        schedule = Schedule.objects.create(route=route, train=train, departure_time=time(12), arrival_time=time(14))
        self.client.force_login(self.staff)
        response = self.client.post(reverse("manage_disruptions"), {
            "schedule": schedule.pk, "travel_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
            "status": JourneyDisruption.Status.CANCELLED, "reason": "Track repair", "revised_departure_time": "",
        })
        self.assertEqual(response.status_code, 302)
        event = StaffAuditEvent.objects.get(target_type="journey_disruption")
        self.assertEqual(event.actor, self.staff)
