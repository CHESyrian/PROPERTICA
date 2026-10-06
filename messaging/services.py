"""Messaging helpers: notifications + lead emails (P1-3 / P1-4)."""

from __future__ import annotations

import logging

from django.urls import reverse

from core.email import send_app_mail

from .models import Notification

logger = logging.getLogger(__name__)


def create_notification(
    *,
    recipient,
    notification_type: str,
    title: str,
    body: str = "",
    link: str = "",
) -> Notification:
    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        body=body,
        link=link,
    )


def notify_new_lead(*, seller, buyer, listing, thread, message_body: str) -> None:
    """In-app + email when a buyer contacts a seller about a listing."""
    try:
        thread_path = reverse("messaging:thread", kwargs={"thread_id": thread.pk})
    except Exception:
        thread_path = "/messages/"

    try:
        from accounts.models import ReputationEvent
        from accounts.reputation import record_event

        record_event(
            subject=seller,
            actor=buyer,
            event_type=ReputationEvent.EventType.LEAD_RECEIVED,
            metadata={"listing_id": str(listing.pk)},
        )
    except Exception:
        pass

    create_notification(
        recipient=seller,
        notification_type=Notification.Type.NEW_LEAD,
        title=f"New inquiry on “{listing.title}”",
        body=(message_body or "")[:500],
        link=thread_path,
    )

    subject = f"[Propertica] New inquiry on {listing.title}"
    email_body = (
        f"You received a new message about your listing “{listing.title}”.\n\n"
        f"From: {buyer.email}\n\n"
        f"{message_body}\n\n"
        f"Reply in your inbox on Propertica.\n"
    )
    send_app_mail(
        subject=subject,
        message=email_body,
        recipient_list=seller.email,
        fail_silently=True,
    )


def notify_new_message(*, recipient, sender, thread, message_body: str) -> None:
    """In-app notification for a reply in an existing thread."""
    try:
        thread_path = reverse("messaging:thread", kwargs={"thread_id": thread.pk})
    except Exception:
        thread_path = "/messages/"

    create_notification(
        recipient=recipient,
        notification_type=Notification.Type.NEW_MESSAGE,
        title=f"New message from {getattr(sender, 'resolved_display_name', sender.email)}",
        body=(message_body or "")[:500],
        link=thread_path,
    )
