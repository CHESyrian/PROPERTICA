"""Tests for the listings app: models, search, detail, wizard, geocode API."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Plan
from listings.forms import ListingWizardForm
from listings.models import (
    AttributeDefinition,
    Favorite,
    Listing,
    ListingMedia,
    ListingStatus,
    PropertyCategory,
    PropertyParentGroup,
    SavedSearch,
)

User = get_user_model()


class ListingFixturesMixin:
    def setUp(self):
        Plan.objects.get_or_create(code="free", defaults={"label": "Free", "applies_to": "all"})
        self.user = User.objects.create_user(
            email="seller@example.com", password="pass12345"
        )
        self.category = PropertyCategory.objects.create(
            code="house",
            label="House",
            parent_group=PropertyParentGroup.RESIDENTIAL,
        )
        AttributeDefinition.objects.create(
            category=self.category,
            attribute_key="bedrooms",
            data_type=AttributeDefinition.DataType.NUMBER,
            is_required=True,
            display_order=1,
            label="Bedrooms",
        )
        AttributeDefinition.objects.create(
            category=self.category,
            attribute_key="furnished",
            data_type=AttributeDefinition.DataType.BOOLEAN,
            is_required=False,
            display_order=2,
            label="Furnished",
        )

    def make_listing(self, **kwargs):
        defaults = {
            "owner": self.user,
            "category": self.category,
            "title": "Test House",
            "description": "A nice house",
            "price": Decimal("250000.00"),
            "currency": "EUR",
            "city": "Damascus",
            "country": "Syria",
            "status": ListingStatus.ACTIVE,
            "published_at": timezone.now(),
            "type_attributes": {"bedrooms": 3, "furnished": False},
            "area_value": Decimal("120"),
        }
        defaults.update(kwargs)
        return Listing.objects.create(**defaults)


class PropertyCategoryTests(TestCase):
    def test_str(self):
        cat = PropertyCategory.objects.create(
            code="apartment",
            label="Apartment",
            parent_group=PropertyParentGroup.RESIDENTIAL,
        )
        self.assertEqual(str(cat), "Apartment")


class ListingModelTests(ListingFixturesMixin, TestCase):
    def test_create_listing(self):
        listing = self.make_listing()
        self.assertEqual(listing.status, ListingStatus.ACTIVE)
        self.assertEqual(str(listing), "Test House")
        self.assertEqual(listing.type_attributes["bedrooms"], 3)

    def test_publish_from_draft(self):
        listing = self.make_listing(status=ListingStatus.DRAFT, published_at=None)
        ListingMedia.objects.create(listing=listing, url="https://example.com/a.jpg", is_cover=True)
        listing.publish()
        listing.refresh_from_db()
        self.assertEqual(listing.status, ListingStatus.ACTIVE)
        self.assertIsNotNone(listing.published_at)

    def test_publish_rejects_sold(self):
        listing = self.make_listing(status=ListingStatus.SOLD)
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            listing.publish()

    def test_publish_requires_photo(self):
        """P0-7: cannot publish without at least one photo."""
        from django.core.exceptions import ValidationError

        listing = self.make_listing(status=ListingStatus.DRAFT, published_at=None)
        with self.assertRaises(ValidationError) as cm:
            listing.publish()
        self.assertIn("photo", str(cm.exception).lower())

    def test_publish_enforces_max_active_listings(self):
        """P0-1: publish blocked when owner is at plan active-listing limit."""
        from django.core.exceptions import ValidationError

        from accounts.models import Plan, PlanEntitlement

        plan, _ = Plan.objects.get_or_create(
            code="free", defaults={"label": "Free", "applies_to": "all"}
        )
        PlanEntitlement.objects.update_or_create(
            plan=plan,
            entitlement_key="max_active_listings",
            defaults={"entitlement_value": "2"},
        )
        self.user.plan = plan
        self.user.save(update_fields=["plan"])

        # Two already-active listings fill the quota.
        self.make_listing(title="Active 1")
        self.make_listing(title="Active 2")
        draft = self.make_listing(title="Draft", status=ListingStatus.DRAFT, published_at=None)
        ListingMedia.objects.create(listing=draft, url="https://example.com/c.jpg", is_cover=True)

        with self.assertRaises(ValidationError) as cm:
            draft.publish()
        self.assertIn("limit of 2", str(cm.exception))
        draft.refresh_from_db()
        self.assertEqual(draft.status, ListingStatus.DRAFT)

    def test_publish_allowed_under_limit(self):
        """P0-1: publish succeeds when under the active-listing limit."""
        from accounts.models import Plan, PlanEntitlement

        plan, _ = Plan.objects.get_or_create(
            code="free", defaults={"label": "Free", "applies_to": "all"}
        )
        PlanEntitlement.objects.update_or_create(
            plan=plan,
            entitlement_key="max_active_listings",
            defaults={"entitlement_value": "5"},
        )
        self.user.plan = plan
        self.user.save(update_fields=["plan"])

        self.make_listing(title="Active 1")
        draft = self.make_listing(title="Draft", status=ListingStatus.DRAFT, published_at=None)
        ListingMedia.objects.create(listing=draft, url="https://example.com/b.jpg", is_cover=True)
        draft.publish()
        draft.refresh_from_db()
        self.assertEqual(draft.status, ListingStatus.ACTIVE)
        self.assertIsNotNone(draft.published_at)

    def test_validate_required_type_attributes(self):
        listing = Listing(
            owner=self.user,
            category=self.category,
            title="Incomplete",
            price=Decimal("100"),
            currency="EUR",
            city="Aleppo",
            type_attributes={},  # missing required bedrooms
        )
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            listing.full_clean()

    def test_favorite_unique(self):
        listing = self.make_listing()
        Favorite.objects.create(account=self.user, listing=listing)
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            Favorite.objects.create(account=self.user, listing=listing)

    def test_saved_search(self):
        ss = SavedSearch.objects.create(
            account=self.user,
            name="Damascus houses",
            filters={"city": "Damascus", "category": "house"},
        )
        self.assertEqual(str(ss), "Damascus houses")

    def test_listing_media_display_url_from_url(self):
        listing = self.make_listing()
        media = ListingMedia.objects.create(
            listing=listing, url="https://cdn.example.com/photo.jpg", sort_order=0
        )
        self.assertEqual(media.display_url, "https://cdn.example.com/photo.jpg")


class ListingSearchViewTests(ListingFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.make_listing(title="Sunny Villa", city="Damascus", price=Decimal("300000"))
        self.make_listing(
            title="City Flat",
            city="Aleppo",
            price=Decimal("150000"),
            status=ListingStatus.DRAFT,
            published_at=None,
        )

    def test_search_page_loads(self):
        resp = self.client.get(reverse("listings:search"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sunny Villa")
        self.assertNotContains(resp, "City Flat")  # draft hidden

    def test_search_filter_by_city(self):
        resp = self.client.get(reverse("listings:search"), {"city": "Damascus"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sunny Villa")

    def test_search_filter_by_price(self):
        resp = self.client.get(
            reverse("listings:search"), {"price_min": "200000", "price_max": "400000"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sunny Villa")

    def test_search_keyword(self):
        resp = self.client.get(reverse("listings:search"), {"q": "Sunny"})
        self.assertContains(resp, "Sunny Villa")


class ListingDetailViewTests(ListingFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.listing = self.make_listing()

    def test_detail_page(self):
        resp = self.client.get(reverse("listings:detail", args=[self.listing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.listing.title)
        self.assertContains(resp, "Damascus")

    def test_detail_shows_contact_form_for_other_user(self):
        buyer = User.objects.create_user(email="buyer@example.com", password="pass12345")
        self.client.login(email="buyer@example.com", password="pass12345")
        resp = self.client.get(reverse("listings:detail", args=[self.listing.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Contact seller")


class ListingWizardViewTests(ListingFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(email="seller@example.com", password="pass12345")

    def test_wizard_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("listings:create"))
        self.assertEqual(resp.status_code, 302)

    def test_wizard_get(self):
        resp = self.client.get(reverse("listings:create"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Post a listing")

    def test_wizard_post_creates_draft(self):
        resp = self.client.post(
            reverse("listings:create"),
            {
                "category": str(self.category.pk),
                "title": "Wizard House",
                "description": "Built via tests",
                "price": "199000",
                "currency": "EUR",
                "city": "Homs",
                "country": "Syria",
                "attr_bedrooms": "4",
                "attr_furnished": "true",
                "action": "draft",
            },
        )
        self.assertEqual(resp.status_code, 302)
        listing = Listing.objects.get(title="Wizard House")
        self.assertEqual(listing.status, ListingStatus.DRAFT)
        self.assertEqual(listing.owner, self.user)
        self.assertEqual(listing.type_attributes.get("bedrooms"), 4)

    def test_wizard_post_publish_without_photo_stays_draft(self):
        """P0-7: publish without photos keeps listing as draft."""
        resp = self.client.post(
            reverse("listings:create"),
            {
                "category": str(self.category.pk),
                "title": "Published House",
                "price": "220000",
                "currency": "EUR",
                "city": "Latakia",
                "country": "Syria",
                "attr_bedrooms": "2",
                "action": "publish",
            },
        )
        self.assertEqual(resp.status_code, 302)
        listing = Listing.objects.get(title="Published House")
        self.assertEqual(listing.status, ListingStatus.DRAFT)



    def test_wizard_photo_order_and_cover(self):
        """P0-7: uploaded photos respect order and cover_index."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Minimal valid 1x1 PNGs
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        f1 = SimpleUploadedFile("a.png", png, content_type="image/png")
        f2 = SimpleUploadedFile("b.png", png, content_type="image/png")
        f3 = SimpleUploadedFile("c.png", png, content_type="image/png")
        resp = self.client.post(
            reverse("listings:create"),
            {
                "category": str(self.category.pk),
                "title": "Photo Order House",
                "price": "150000",
                "currency": "EUR",
                "city": "Damascus",
                "country": "Syria",
                "attr_bedrooms": "3",
                "cover_index": "1",  # middle photo is cover
                "action": "publish",
                "photos": [f1, f2, f3],
            },
        )
        self.assertEqual(resp.status_code, 302)
        listing = Listing.objects.get(title="Photo Order House")
        self.assertEqual(listing.status, ListingStatus.ACTIVE)
        media = list(listing.media.order_by("sort_order"))
        self.assertEqual(len(media), 3)
        self.assertEqual([m.sort_order for m in media], [0, 1, 2])
        covers = [m for m in media if m.is_cover]
        self.assertEqual(len(covers), 1)
        self.assertEqual(covers[0].sort_order, 1)


class ListingWizardFormTests(ListingFixturesMixin, TestCase):
    def test_form_builds_dynamic_fields(self):
        defs = list(self.category.attribute_definitions.all())
        form = ListingWizardForm(attribute_defs=defs)
        self.assertIn("attr_bedrooms", form.fields)
        self.assertIn("attr_furnished", form.fields)

    def test_form_assembles_type_attributes(self):
        defs = list(self.category.attribute_definitions.all())
        form = ListingWizardForm(
            data={
                "category": str(self.category.pk),
                "title": "Form Test",
                "price": "100000",
                "currency": "EUR",
                "city": "Damascus",
                "country": "Syria",
                "attr_bedrooms": "3",
                "attr_furnished": True,
            },
            attribute_defs=defs,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["type_attributes"]["bedrooms"], 3)
        self.assertTrue(form.cleaned_data["type_attributes"]["furnished"])


class GeocodeAPITests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_geocode_rejects_short_query(self):
        resp = self.client.get(reverse("listings:geocode"), {"q": "ab"})
        self.assertEqual(resp.status_code, 400)

    @patch("listings.views.urllib.request.urlopen")
    def test_geocode_success(self, mock_urlopen):
        payload = {
            "features": [
                {
                    "geometry": {"coordinates": [36.2765, 33.5138]},
                    "properties": {
                        "name": "Damascus",
                        "city": "Damascus",
                        "country": "Syria",
                        "state": "Damascus Governorate",
                    },
                }
            ]
        }
        import json

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        resp = self.client.get(reverse("listings:geocode"), {"q": "Damascus Syria"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["city"], "Damascus")


class SavedSearchViewTests(ListingFixturesMixin, TestCase):
    """P0-2: save / list / delete saved searches."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.login(email="seller@example.com", password="pass12345")

    def test_save_search(self):
        resp = self.client.post(
            reverse("listings:save_search"),
            {
                "name": "Damascus houses",
                "q": "",
                "category": "house",
                "city": "Damascus",
                "price_min": "",
                "price_max": "300000",
                "sort": "newest",
                "notify_by_email": "on",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(SavedSearch.objects.filter(account=self.user).count(), 1)
        ss = SavedSearch.objects.get(account=self.user)
        self.assertEqual(ss.name, "Damascus houses")
        self.assertEqual(ss.filters["city"], "Damascus")

    def test_list_saved_searches(self):
        SavedSearch.objects.create(
            account=self.user, name="Test", filters={"city": "Homs"}
        )
        resp = self.client.get(reverse("listings:saved_searches"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Test")

    def test_delete_saved_search(self):
        ss = SavedSearch.objects.create(
            account=self.user, name="Delete me", filters={}
        )
        resp = self.client.post(reverse("listings:saved_search_delete", args=[ss.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(SavedSearch.objects.filter(pk=ss.pk).exists())


class GeoSearchTests(ListingFixturesMixin, TestCase):
    """P1-5: radius / bbox search."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.make_listing(
            title="Near Center",
            latitude=Decimal("33.5138"),
            longitude=Decimal("36.2765"),
            status=ListingStatus.ACTIVE,
        )
        self.make_listing(
            title="Far Away",
            latitude=Decimal("36.2021"),
            longitude=Decimal("37.1343"),
            status=ListingStatus.ACTIVE,
        )

    def test_radius_filter(self):
        resp = self.client.get(
            reverse("listings:search"),
            {"lat": "33.51", "lng": "36.28", "radius_km": "50"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Near Center")
        self.assertNotContains(resp, "Far Away")

    def test_bbox_filter(self):
        resp = self.client.get(
            reverse("listings:search"),
            {
                "min_lat": "33.4",
                "max_lat": "33.6",
                "min_lng": "36.1",
                "max_lng": "36.4",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Near Center")
        self.assertNotContains(resp, "Far Away")


class FeatureAndAnalyticsTests(ListingFixturesMixin, TestCase):
    """P2-2 / P2-3."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        from accounts.models import Plan, PlanEntitlement

        plan, _ = Plan.objects.get_or_create(
            code="free", defaults={"label": "Free", "applies_to": "all"}
        )
        PlanEntitlement.objects.update_or_create(
            plan=plan,
            entitlement_key="can_feature_listing",
            defaults={"entitlement_value": "false"},
        )
        self.user.plan = plan
        self.user.save(update_fields=["plan"])

    def test_feature_blocked_on_free_plan(self):
        from django.core.exceptions import ValidationError

        listing = self.make_listing(status=ListingStatus.ACTIVE)
        with self.assertRaises(ValidationError):
            listing.feature()

    def test_feature_allowed_when_entitled(self):
        from accounts.models import PlanEntitlement

        PlanEntitlement.objects.update_or_create(
            plan=self.user.plan,
            entitlement_key="can_feature_listing",
            defaults={"entitlement_value": "true"},
        )
        listing = self.make_listing(status=ListingStatus.ACTIVE)
        listing.feature(days=7)
        listing.refresh_from_db()
        self.assertTrue(listing.is_featured())

    def test_record_view(self):
        listing = self.make_listing()
        listing.record_view()
        listing.refresh_from_db()
        self.assertEqual(listing.view_count, 1)


class RateLimitTests(TestCase):
    def test_is_rate_limited(self):
        from django.test import RequestFactory

        from core.ratelimit import is_rate_limited

        factory = RequestFactory()
        req = factory.get("/")
        req.user = type("U", (), {"is_authenticated": False})()
        # Force a tiny limit
        from django.conf import settings

        settings.RATE_LIMITS = {"testscope": (2, 60)}
        self.assertFalse(is_rate_limited(req, "testscope"))
        self.assertFalse(is_rate_limited(req, "testscope"))
        self.assertTrue(is_rate_limited(req, "testscope"))


class MaintenanceCommandTests(ListingFixturesMixin, TestCase):
    def test_expire_listings(self):
        from datetime import timedelta

        from django.core.management import call_command
        from django.utils import timezone

        listing = self.make_listing(
            status=ListingStatus.ACTIVE,
            expires_at=timezone.now() - timedelta(days=1),
        )
        call_command("run_maintenance_tasks")
        listing.refresh_from_db()
        self.assertEqual(listing.status, ListingStatus.EXPIRED)
