from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ProfileTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="profileuser", email="old@example.com", password="StrongPassword456!")
        self.client.force_login(self.user)

    def test_profile_renders(self):
        self.assertContains(self.client.get(reverse("profile")), "My profile")

    def test_email_update(self):
        self.assertRedirects(self.client.post(reverse("profile"), {"email": "new@example.com"}), reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "new@example.com")

    def test_duplicate_email_rejected(self):
        get_user_model().objects.create_user(username="other", email="taken@example.com", password="StrongPassword456!")
        self.client.post(reverse("profile"), {"email": "TAKEN@example.com"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "old@example.com")

    def test_closure_requires_password(self):
        self.client.post(reverse("close_account"), {"password": "wrong"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_closure_deactivates_and_clears_email(self):
        self.assertRedirects(self.client.post(reverse("close_account"), {"password": "StrongPassword456!"}), reverse("home"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.user.email, "")

    def test_get_cannot_close_account(self):
        self.assertEqual(self.client.get(reverse("close_account")).status_code, 405)
