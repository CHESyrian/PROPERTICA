"""API smoke tests."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from accounts.models import Plan
from listings.models import Listing, ListingStatus, PropertyCategory, PropertyParentGroup

User = get_user_model()


class APIAuthTests(TestCase):
    def setUp(self):
        Plan.objects.get_or_create(code="free", defaults={"label": "Free", "applies_to": "all"})
        self.client = APIClient()

    def test_register_and_login(self):
        resp = self.client.post(
            "/api/v1/auth/register/",
            {
                "account_type": "personal",
                "email": "apiuser@example.com",
                "password": "securepass1",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", resp.data)
        self.assertTrue(resp.data["username"].startswith("USR"))

        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "apiuser@example.com", "password": "securepass1"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("token", resp.data)


class APIListingTests(TestCase):
    def setUp(self):
        Plan.objects.get_or_create(code="free", defaults={"label": "Free", "applies_to": "all"})
        self.user = User.objects.create_user(
            email="seller@example.com", password="pass12345"
        )
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.category = PropertyCategory.objects.create(
            code="house",
            label="House",
            parent_group=PropertyParentGroup.RESIDENTIAL,
        )
        self.listing = Listing.objects.create(
            owner=self.user,
            category=self.category,
            title="API House",
            price=Decimal("200000"),
            currency="EUR",
            city="Damascus",
            country="Syria",
            status=ListingStatus.ACTIVE,
            published_at=timezone.now(),
        )

    def test_search_listings(self):
        client = APIClient()
        resp = client.get("/api/v1/search/listings/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("data", resp.data)
        self.assertIn("pagination", resp.data)

    def test_create_listing(self):
        resp = self.client.post(
            "/api/v1/listings/",
            {
                "category_code": "house",
                "title": "New API Listing",
                "price": "150000",
                "currency": "EUR",
                "city": "Aleppo",
                "country": "Syria",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], "draft")

    def test_me(self):
        resp = self.client.get("/api/v1/accounts/me/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["email"], "seller@example.com")

    def test_public_profile(self):
        client = APIClient()
        resp = client.get(f"/api/v1/accounts/{self.user.username}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], self.user.username)
