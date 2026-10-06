"""
Accounts module — custom user model matching PRD/TDD/Database Schema.

Key decisions:
- username is auto-generated as USR + 10 digits and is immutable.
- display_name resolution depends on account_type (see TDD §4.2).
- plan_id + entitlements are present from day one for future paid tiers.
"""

from __future__ import annotations

import secrets
import string
import uuid
from typing import Optional

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class AccountType(models.TextChoices):
    PERSONAL = "personal", "Personal"
    AGENT = "agent", "Agent"
    AGENCY = "agency", "Agency"


class AccountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    DELETED = "deleted", "Deleted"


class Plan(models.Model):
    """Subscription plan. v1 seeds a single 'free' plan."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    label = models.CharField(max_length=100)
    applies_to = models.CharField(
        max_length=20,
        choices=[
            ("personal", "Personal"),
            ("agent", "Agent"),
            ("agency", "Agency"),
            ("all", "All"),
        ],
        default="all",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "plans"

    def __str__(self) -> str:
        return self.label


class PlanEntitlement(models.Model):
    """Key/value entitlements for a plan (e.g. max_active_listings=10)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="entitlements")
    entitlement_key = models.CharField(max_length=60)
    entitlement_value = models.CharField(max_length=100)

    class Meta:
        db_table = "plan_entitlements"
        unique_together = [("plan", "entitlement_key")]

    def __str__(self) -> str:
        return f"{self.plan.code}.{self.entitlement_key}={self.entitlement_value}"


class AccountManager(BaseUserManager):
    def _generate_username(self) -> str:
        """Generate unique USRXXXXXXXXXX (10 digits)."""
        alphabet = string.digits
        for _ in range(20):
            digits = "".join(secrets.choice(alphabet) for _ in range(10))
            username = f"USR{digits}"
            if not self.model.objects.filter(username=username).exists():
                return username
        raise RuntimeError("Could not generate unique username after retries")

    def create_user(
        self,
        email: str,
        password: Optional[str] = None,
        account_type: str = AccountType.PERSONAL,
        **extra_fields,
    ):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        username = self._generate_username()
        extra_fields.setdefault("status", AccountStatus.ACTIVE)

        plan, _ = Plan.objects.get_or_create(
            code="free",
            defaults={"label": "Free", "applies_to": "all", "is_active": True},
        )
        if "plan" not in extra_fields and "plan_id" not in extra_fields:
            extra_fields["plan"] = plan

        user = self.model(
            email=email,
            username=username,
            account_type=account_type,
            **extra_fields,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: Optional[str] = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("account_type", AccountType.PERSONAL)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class Account(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model.

    - username: immutable auto-generated USRXXXXXXXXXX
    - display_name: editable; public resolution depends on account_type
    - agency: only for agents linked to an agency
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=16, unique=True, editable=False)
    account_type = models.CharField(
        max_length=20, choices=AccountType.choices, default=AccountType.PERSONAL
    )
    display_name = models.CharField(max_length=120, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True, null=True)

    oauth_provider = models.CharField(max_length=30, blank=True, null=True)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    phone_verified_at = models.DateTimeField(blank=True, null=True)

    agency = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agents",
        limit_choices_to={"account_type": AccountType.AGENCY},
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name="accounts", null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=AccountStatus.choices, default=AccountStatus.ACTIVE
    )

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AccountManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "accounts"
        indexes = [
            models.Index(fields=["account_type"]),
            models.Index(fields=["agency"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(agency__isnull=True)
                | models.Q(account_type=AccountType.AGENT),
                name="agency_id_only_for_agents",
            ),
        ]

    def __str__(self) -> str:
        return self.username

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = Account.objects._generate_username()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.agency_id and self.account_type != AccountType.AGENT:
            raise ValidationError(
                {"agency": "Only agent accounts can be linked to an agency."}
            )

    @property
    def resolved_display_name(self) -> str:
        """
        Public-facing name per TDD §4.2:
        - Personal  → username
        - Agent linked to agency → agency.display_name
        - Agent independent → display_name or username
        - Agency → display_name
        """
        if self.account_type == AccountType.PERSONAL:
            return self.username
        if self.account_type == AccountType.AGENT and self.agency_id:
            agency = self.agency
            if agency and agency.display_name:
                return agency.display_name
            return self.username
        if self.account_type == AccountType.AGENCY:
            return self.display_name or self.username
        return self.display_name or self.username

    def get_entitlement(self, key: str, default: Optional[str] = None) -> Optional[str]:
        if not self.plan_id:
            return default
        ent = self.plan.entitlements.filter(entitlement_key=key).first()
        return ent.entitlement_value if ent else default


class AgencyAgent(models.Model):
    """Tracks agency ↔ agent invite/relationship history."""

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        REMOVED = "removed", "Removed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="agency_memberships",
        limit_choices_to={"account_type": AccountType.AGENCY},
    )
    agent = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="agent_memberships",
        limit_choices_to={"account_type": AccountType.AGENT},
    )
    invited_at = models.DateTimeField(default=timezone.now)
    joined_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.INVITED
    )

    class Meta:
        db_table = "agency_agents"
        constraints = [
            models.UniqueConstraint(
                fields=["agency", "agent"],
                condition=models.Q(status="active"),
                name="unique_active_agency_agent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.agent} @ {self.agency}"



class ReputationEvent(models.Model):
    """Atomic reputation event (P3-1). Only Agent/Agency accrue summaries."""

    class EventType(models.TextChoices):
        LISTING_PUBLISHED = "listing_published", "Listing published"
        LEAD_RECEIVED = "lead_received", "Lead received"
        LEAD_RESPONDED = "lead_responded", "Lead responded"
        RATING_RECEIVED = "rating_received", "Rating received"
        LISTING_SOLD = "listing_sold", "Listing sold"
        MANUAL_ADJUST = "manual_adjust", "Manual adjustment"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="reputation_events_as_subject",
        help_text="Agent or Agency receiving the event",
    )
    actor = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reputation_events_as_actor",
    )
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    value = models.IntegerField(default=0, help_text="Points delta")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reputation_events"
        indexes = [
            models.Index(fields=["subject", "-created_at"]),
            models.Index(fields=["event_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} {self.value} → {self.subject_id}"


class ReputationSummary(models.Model):
    """Aggregated points/XP for Agent & Agency accounts only."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.OneToOneField(
        Account, on_delete=models.CASCADE, related_name="reputation"
    )
    points = models.IntegerField(default=0)
    experience = models.IntegerField(default=0)
    level = models.PositiveIntegerField(default=1)
    rating_sum = models.IntegerField(default=0)
    rating_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reputation_summaries"

    def __str__(self) -> str:
        return f"{self.account_id} pts={self.points} lvl={self.level}"

    @property
    def average_rating(self) -> float | None:
        if self.rating_count == 0:
            return None
        return round(self.rating_sum / self.rating_count, 2)
