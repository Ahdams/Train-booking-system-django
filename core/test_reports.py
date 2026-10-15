from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import PassengerReport


class ReportWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.passenger = User.objects.create_user(username="reporter", password="Password123!")
        self.other = User.objects.create_user(username="otherreporter", password="Password123!")
        self.staff = User.objects.create_user(username="reportstaff", password="Password123!", is_staff=True)

    def test_passenger_can_submit_and_view_own_report(self):
        self.client.force_login(self.passenger)
        response = self.client.post(reverse("reports"), {
            "subject": "Train delay", "description": "Departure time was changed.",
        })
        self.assertRedirects(response, reverse("reports"))
        self.assertContains(self.client.get(reverse("reports")), "Train delay")
        self.assertEqual(PassengerReport.objects.get().user, self.passenger)

    def test_other_passenger_cannot_see_report(self):
        PassengerReport.objects.create(user=self.passenger, subject="Private issue", description="My journey")
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("reports")), "Private issue")
        self.assertEqual(self.client.get(reverse("staff_reports")).status_code, 302)

    def test_staff_can_resolve_with_response(self):
        report = PassengerReport.objects.create(user=self.passenger, subject="Refund query", description="Please review")
        self.client.force_login(self.staff)
        url = reverse("staff_report_detail", args=[report.pk])
        response = self.client.post(url, {"status": "resolved", "admin_response": "Refund reviewed."})
        self.assertRedirects(response, reverse("staff_reports"))
        report.refresh_from_db()
        self.assertEqual(report.status, PassengerReport.Status.RESOLVED)
        self.client.force_login(self.passenger)
        self.assertContains(self.client.get(reverse("reports")), "Refund reviewed.")

    def test_staff_cannot_resolve_without_response(self):
        report = PassengerReport.objects.create(user=self.passenger, subject="Delay", description="Delayed")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("staff_report_detail", args=[report.pk]), {
            "status": "resolved", "admin_response": "",
        })
        self.assertEqual(response.status_code, 200)
        report.refresh_from_db()
        self.assertEqual(report.status, PassengerReport.Status.OPEN)
