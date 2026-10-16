"""Smoke tests for page rendering, navigation and role boundaries."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class NavigationAndAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.passenger = User.objects.create_user(username="navpassenger", password="Pass12345!")
        self.staff = User.objects.create_user(username="navstaff", password="Pass12345!", is_staff=True)

    def test_public_pages_render_without_nested_homepage(self):
        for name in ("home", "login", "register", "search_journeys"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "<html", html=False)
                self.assertEqual(response.content.decode().lower().count("<main"), 1)

    def test_passenger_pages_render_separately(self):
        self.client.force_login(self.passenger)
        for name in ("dashboard", "my_bookings", "notifications", "reports"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content.decode().lower().count("<main"), 1)

    def test_passenger_cannot_open_staff_pages(self):
        self.client.force_login(self.passenger)
        for name in ("staff_dashboard", "staff_reports", "manage_disruptions", "verify_ticket"):
            with self.subTest(page=name):
                self.assertNotEqual(self.client.get(reverse(name)).status_code, 200)

    def test_staff_can_open_staff_pages(self):
        self.client.force_login(self.staff)
        for name in ("staff_dashboard", "staff_reports", "manage_disruptions", "verify_ticket"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content.decode().lower().count("<main"), 1)

    def test_admin_login_page_available(self):
        self.assertEqual(self.client.get(reverse("admin:login")).status_code, 200)
