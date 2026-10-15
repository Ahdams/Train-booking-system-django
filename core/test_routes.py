from django.test import TestCase
from django.urls import reverse
from .models import Route, Station


class DependentDestinationTests(TestCase):
    def setUp(self):
        self.kaduna = Station.objects.create(code="KAD", name="Rigasa", city="Kaduna", state="Kaduna")
        self.abuja = Station.objects.create(code="ABJ", name="Idu", city="Abuja", state="FCT")
        self.lagos = Station.objects.create(code="LOS", name="Mobolaji Johnson", city="Lagos", state="Lagos")
        self.ibadan = Station.objects.create(code="IBD", name="Moniya", city="Ibadan", state="Oyo")
        Route.objects.create(origin=self.kaduna, destination=self.abuja)
        Route.objects.create(origin=self.lagos, destination=self.ibadan)

    def test_kaduna_only_lists_abuja(self):
        response = self.client.get(reverse("destinations"), {"origin": self.kaduna.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([s["city"] for s in response.json()["stations"]], ["Abuja"])

    def test_unrelated_stations_are_not_listed(self):
        response = self.client.get(reverse("destinations"), {"origin": self.lagos.id})
        self.assertEqual([s["city"] for s in response.json()["stations"]], ["Ibadan"])

    def test_invalid_origin_returns_empty_destinations(self):
        response = self.client.get(reverse("destinations"), {"origin": "invalid"})
        self.assertEqual(response.json()["stations"], [])

    def test_inactive_route_is_hidden(self):
        Route.objects.filter(origin=self.kaduna).update(is_active=False)
        response = self.client.get(reverse("destinations"), {"origin": self.kaduna.id})
        self.assertEqual(response.json()["stations"], [])
