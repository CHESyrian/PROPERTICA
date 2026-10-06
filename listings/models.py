"""
Listings module — property listings with extensible type-specific attributes.
Matches Database Schema §2.3–2.6 and TDD hybrid schema decision.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class PropertyParentGroup(models.TextChoices):
    RESIDENTIAL = "residential", "Residential"
    LAND = "land", "Land"
    COMMERCIAL = "commercial", "Commercial"
    OTHER = "other", "Other"


class ListingStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING_REVIEW = "pending_review", "Pending Review"
    ACTIVE = "active", "Active"
    UNDER_OFFER = "under_offer", "Under Offer"
    SOLD = "sold", "Sold"
    EXPIRED = "expired", "Expired"
    REMOVED = "removed", "Removed"


class PropertyCategory(models.Model):
    """Seed/reference data for property types (house, apartment, land, …)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    parent_group = models.CharField(max_length=20, choices=PropertyParentGroup.choices)
    label = models.CharField(max_length=100)

    class Meta:
        db_table = "property_categories"
        verbose_name_plural = "property categories"

    def __str__(self) -> str:
        return self.label


class AttributeDefinition(models.Model):
    """Defines type-specific fields per category (data-driven form + validation)."""

    class DataType(models.TextChoices):
        STRING = "string", "String"
        NUMBER = "number", "Number"
        BOOLEAN = "boolean", "Boolean"
        ENUM = "enum", "Enum"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        PropertyCategory, on_delete=models.CASCADE, related_name="attribute_definitions"
    )
    attribute_key = models.CharField(max_length=60)
    data_type = models.CharField(max_length=20, choices=DataType.choices)
    enum_options = models.JSONField(blank=True, null=True)
    is_required = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    label = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = "attribute_definitions"
        ordering = ["display_order", "attribute_key"]
        unique_together = [("category", "attribute_key")]

    def __str__(self) -> str:
        return f"{self.category.code}.{self.attribute_key}"


class Listing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listings",
    )
    category = models.ForeignKey(
        PropertyCategory, on_delete=models.PROTECT, related_name="listings"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    negotiable = models.BooleanField(default=False)

    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    area_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, help_text="m²"
    )

    type_attributes = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=20, choices=ListingStatus.choices, default=ListingStatus.DRAFT
    )
    featured_until = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "listings"
        indexes = [
            models.Index(fields=["owner"]),
            models.Index(fields=["category"]),
            models.Index(fields=["status"]),
            models.Index(fields=["city"]),
            models.Index(fields=["price"]),
            models.Index(fields=["-published_at"]),
        ]
        ordering = ["-published_at", "-created_at"]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        super().clean()
        self._validate_type_attributes()

    def _validate_type_attributes(self) -> None:
        if not self.category_id:
            return
        defs = {
            d.attribute_key: d
            for d in self.category.attribute_definitions.all()
        }
        attrs = self.type_attributes or {}
        for key, definition in defs.items():
            if definition.is_required and key not in attrs:
                raise ValidationError(
                    {f"type_attributes.{key}": f"'{key}' is required for this category."}
                )
            if key in attrs:
                value = attrs[key]
                if definition.data_type == AttributeDefinition.DataType.NUMBER:
                    if not isinstance(value, (int, float)) and value is not None:
                        raise ValidationError(
                            {f"type_attributes.{key}": f"'{key}' must be a number."}
                        )
                elif definition.data_type == AttributeDefinition.DataType.BOOLEAN:
                    if not isinstance(value, bool):
                        raise ValidationError(
                            {f"type_attributes.{key}": f"'{key}' must be a boolean."}
                        )
                elif definition.data_type == AttributeDefinition.DataType.ENUM:
                    options = definition.enum_options or []
                    if value not in options:
                        raise ValidationError(
                            {
                                f"type_attributes.{key}": (
                                    f"'{key}' must be one of {options}."
                                )
                            }
                        )

    def publish(self) -> None:
        """
        Transition draft/pending → active, enforcing plan entitlement
        ``max_active_listings`` (P0-1) and requiring ≥1 photo (P0-7).
        """
        if self.status not in (ListingStatus.DRAFT, ListingStatus.PENDING_REVIEW):
            raise ValidationError("Only draft or pending listings can be published.")

        # P0-7: at least one photo required to publish.
        if not self.media.exists():
            raise ValidationError(
                "Add at least one photo before publishing this listing."
            )

        # Entitlement gate: count other active listings for this owner.
        # The current listing is not yet ACTIVE, so it is not included.
        max_active = self._max_active_listings_for_owner()
        if max_active is not None:
            active_count = (
                Listing.objects.filter(
                    owner_id=self.owner_id,
                    status=ListingStatus.ACTIVE,
                )
                .exclude(pk=self.pk)
                .count()
            )
            if active_count >= max_active:
                raise ValidationError(
                    f"You have reached your plan limit of {max_active} active "
                    f"listing{'s' if max_active != 1 else ''}. "
                    "Unpublish or sell an existing listing, or upgrade your plan."
                )

        self.status = ListingStatus.ACTIVE
        self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])
        try:
            from accounts.models import ReputationEvent
            from accounts.reputation import record_event

            record_event(
                subject=self.owner,
                event_type=ReputationEvent.EventType.LISTING_PUBLISHED,
                metadata={"listing_id": str(self.pk)},
            )
        except Exception:
            pass

    def _max_active_listings_for_owner(self) -> int | None:
        """Return the numeric max_active_listings entitlement, or None if unlimited."""
        owner = getattr(self, "owner", None)
        if owner is None and self.owner_id:
            from django.contrib.auth import get_user_model

            owner = get_user_model().objects.filter(pk=self.owner_id).first()
        if owner is None:
            return None
        raw = owner.get_entitlement("max_active_listings", default="10")
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return 10
        # Treat 0 or negative as unlimited only if explicitly set that way;
        # normal free plan uses a positive integer.
        if value < 0:
            return None
        return value


    def is_featured(self) -> bool:
        if not self.featured_until:
            return False
        return self.featured_until >= timezone.now()

    def feature(self, days: int | None = None) -> None:
        """Activate featured placement if plan allows (P2-2)."""
        from django.conf import settings

        owner = self.owner
        raw = owner.get_entitlement("can_feature_listing", default="false") if owner else "false"
        if str(raw).lower() not in ("1", "true", "yes"):
            raise ValidationError(
                "Featured listings are not available on your current plan."
            )
        duration = days if days is not None else int(
            getattr(settings, "FEATURED_DURATION_DAYS", 14)
        )
        self.featured_until = timezone.now() + timezone.timedelta(days=duration)
        self.save(update_fields=["featured_until", "updated_at"])

    def record_view(self) -> None:
        """Increment denormalized view counter (P2-3)."""
        from django.db.models import F

        Listing.objects.filter(pk=self.pk).update(view_count=F("view_count") + 1)
        self.view_count = (self.view_count or 0) + 1



class ListingMedia(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="media"
    )
    image = models.ImageField(upload_to="listings/%Y/%m/", blank=True, null=True)
    url = models.URLField(max_length=500, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_cover = models.BooleanField(default=False)
    alt_text = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "listing_media"
        ordering = ["sort_order", "created_at"]

    def __str__(self) -> str:
        return f"Media for {self.listing_id} (#{self.sort_order})"

    @property
    def display_url(self) -> str:
        if self.url:
            return self.url
        if self.image:
            return self.image.url
        return ""


class Favorite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "favorites"
        unique_together = [("account", "listing")]

    def __str__(self) -> str:
        return f"{self.account_id} ♥ {self.listing_id}"


class SavedSearch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_searches",
    )
    name = models.CharField(max_length=120, blank=True)
    filters = models.JSONField(default=dict)
    notify_by_email = models.BooleanField(default=True)
    last_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "saved_searches"

    def __str__(self) -> str:
        return self.name or f"Saved search {self.id}"



class ListingViewEvent(models.Model):
    """Optional per-view log for analytics (P2-3)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="view_events"
    )
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="listing_views",
    )
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "listing_view_events"
        indexes = [
            models.Index(fields=["listing", "-created_at"]),
        ]
