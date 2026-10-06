"""Messaging & leads — inquiry threads between buyers and listing owners."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class MessageThread(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(
        "listings.Listing", on_delete=models.CASCADE, related_name="message_threads"
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buyer_threads",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_threads",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "message_threads"
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "buyer"],
                name="unique_thread_per_buyer_listing",
            ),
        ]
        indexes = [
            models.Index(fields=["buyer"]),
            models.Index(fields=["seller"]),
            models.Index(fields=["listing"]),
        ]

    def __str__(self) -> str:
        return f"Thread {self.id} on listing {self.listing_id}"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        MessageThread, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Message {self.id} in thread {self.thread_id}"


class Report(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWED = "reviewed", "Reviewed"
        DISMISSED = "dismissed", "Dismissed"
        ACTIONED = "actioned", "Actioned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
    )
    reported_account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports_against",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_filed",
    )
    reason = models.CharField(max_length=60)
    details = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reports"

    def __str__(self) -> str:
        return f"Report {self.id} ({self.status})"


class Notification(models.Model):
    """In-app notification (P1-3)."""

    class Type(models.TextChoices):
        NEW_LEAD = "new_lead", "New lead"
        NEW_MESSAGE = "new_message", "New message"
        AGENCY_INVITE = "agency_invite", "Agency invite"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=30, choices=Type.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["recipient", "read_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.notification_type}: {self.title}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
