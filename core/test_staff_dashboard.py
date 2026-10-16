from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from .models import Booking, Wallet, WalletTransaction


class StaffDashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(username="opsstaff", password="Pass12345!", is_staff=True)
        self.passenger = User.objects.create_user(username="opsrider", password="Pass12345!")
        self.url = reverse("staff_dashboard")

    def test_anonymous_user_redirected_to_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_passenger_cannot_view_dashboard(self):
        self.client.force_login(self.passenger)
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_staff_sees_operational_metrics(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operations dashboard")
        self.assertEqual(response.context["total_bookings"], 0)
        self.assertEqual(response.context["wallet_debits_30d"], Decimal("0.00"))
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_recent_wallet_debit_and_refund_totals(self):
        wallet = Wallet.objects.create(user=self.passenger, balance=Decimal("100"))
        WalletTransaction.objects.create(wallet=wallet, kind=WalletTransaction.Kind.DEBIT, amount=Decimal("20"), balance_after=Decimal("80"))
        WalletTransaction.objects.create(wallet=wallet, kind=WalletTransaction.Kind.REFUND, amount=Decimal("10"), balance_after=Decimal("90"))
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.context["wallet_debits_30d"], Decimal("20"))
        self.assertEqual(response.context["wallet_refunds_30d"], Decimal("10"))
