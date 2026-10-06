"""Tests for the core app: home page, context processor, exception handler."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.views import exception_handler as drf_exception_handler

from accounts.models import Plan
from core.context_processors import site_context
from core.exceptions import custom_exception_handler
from listings.models import Listing, ListingStatus, PropertyCategory, PropertyParentGroup

User = get_user_model()


class SiteContextTests(TestCase):
    def test_site_name_is_propertica(self):
        factory = RequestFactory()
        request = factory.get("/")
        ctx = site_context(request)
        self.assertEqual(ctx["SITE_NAME"], "PROPERTICA")
        self.assertIn("SITE_TAGLINE", ctx)


class HomeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        Plan.objects.get_or_create(code="free", defaults={"label": "Free", "applies_to": "all"})
        self.user = User.objects.create_user(
            email="home@example.com", password="pass12345"
        )
        self.category = PropertyCategory.objects.create(
            code="house",
            label="House",
            parent_group=PropertyParentGroup.RESIDENTIAL,
        )
        Listing.objects.create(
            owner=self.user,
            category=self.category,
            title="Featured Home",
            price=Decimal("180000"),
            currency="EUR",
            city="Damascus",
            country="Syria",
            status=ListingStatus.ACTIVE,
            published_at=timezone.now(),
        )
        Listing.objects.create(
            owner=self.user,
            category=self.category,
            title="Hidden Draft",
            price=Decimal("100000"),
            currency="EUR",
            city="Homs",
            country="Syria",
            status=ListingStatus.DRAFT,
        )

    def test_home_loads(self):
        resp = self.client.get(reverse("core:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "PROPERTICA")

    def test_home_shows_active_listings_only(self):
        resp = self.client.get(reverse("core:home"))
        self.assertContains(resp, "Featured Home")
        self.assertNotContains(resp, "Hidden Draft")

    def test_home_shows_categories(self):
        resp = self.client.get(reverse("core:home"))
        self.assertContains(resp, "House")


class StaticPagesTests(TestCase):
    """P0-6: About, Terms, Privacy, Contact."""

    def setUp(self):
        self.client = Client()

    def test_about_page(self):
        resp = self.client.get(reverse("core:about"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "About")

    def test_terms_page(self):
        resp = self.client.get(reverse("core:terms"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Terms of Service")

    def test_privacy_page(self):
        resp = self.client.get(reverse("core:privacy"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Privacy Policy")

    def test_contact_get(self):
        resp = self.client.get(reverse("core:contact"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Contact")

    def test_contact_post(self):
        resp = self.client.post(
            reverse("core:contact"),
            {
                "name": "Test User",
                "email": "test@example.com",
                "subject": "Hello",
                "message": "This is a test message.",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("core:contact"))

    def test_footer_links_on_home(self):
        resp = self.client.get(reverse("core:home"))
        self.assertContains(resp, reverse("core:about"))
        self.assertContains(resp, reverse("core:terms"))
        self.assertContains(resp, reverse("core:privacy"))
        self.assertContains(resp, reverse("core:contact"))


class ExceptionHandlerTests(TestCase):
    def test_validation_error_shape(self):
        factory = RequestFactory()
        request = factory.post("/api/test/")
        context = {"request": request, "view": type("V", (), {})()}

        exc = DRFValidationError({"price": ["required"]})
        # Wrap using DRF's handler path
        response = custom_exception_handler(exc, context)
        self.assertIsNotNone(response)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("fields", response.data["error"])
