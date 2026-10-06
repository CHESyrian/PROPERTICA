"""
Central email helpers for PROPERTICA.

- Uses Django's configured EMAIL_BACKEND (console in dev, SMTP when EMAIL_HOST is set).
- Never raises into request handlers by default (fail_silently=True).
- Supports plain text + optional HTML.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional, Sequence, Union

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection, send_mail

logger = logging.getLogger(__name__)

Recipient = Union[str, Sequence[str]]


def _normalize_recipients(to: Recipient) -> list[str]:
    if isinstance(to, str):
        return [to] if to.strip() else []
    return [a for a in to if a and str(a).strip()]


def send_app_mail(
    *,
    subject: str,
    message: str,
    recipient_list: Recipient,
    from_email: Optional[str] = None,
    html_message: Optional[str] = None,
    fail_silently: bool = True,
    reply_to: Optional[Iterable[str]] = None,
) -> int:
    """
    Send a transactional email.

    Returns number of messages sent (0 or 1). On failure logs and returns 0
    when fail_silently is True.
    """
    recipients = _normalize_recipients(recipient_list)
    if not recipients:
        logger.warning("send_app_mail skipped: empty recipient list (subject=%r)", subject)
        return 0

    from_addr = from_email or settings.DEFAULT_FROM_EMAIL
    try:
        if html_message:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=from_addr,
                to=recipients,
                reply_to=list(reply_to) if reply_to else None,
            )
            msg.attach_alternative(html_message, "text/html")
            return msg.send(fail_silently=fail_silently)

        return send_mail(
            subject=subject,
            message=message,
            from_email=from_addr,
            recipient_list=recipients,
            fail_silently=fail_silently,
            html_message=None,
        )
    except Exception:
        logger.exception(
            "Email send failed (subject=%r, to=%s, backend=%s)",
            subject,
            recipients,
            getattr(settings, "EMAIL_BACKEND", "?"),
        )
        if not fail_silently:
            raise
        return 0


def email_backend_label() -> str:
    """Human-readable description of the active email backend."""
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if "console" in backend:
        return "console (messages print to server logs)"
    if "smtp" in backend:
        host = getattr(settings, "EMAIL_HOST", "") or "?"
        port = getattr(settings, "EMAIL_PORT", "")
        return f"SMTP ({host}:{port})"
    if "filebased" in backend:
        return "file-based"
    if "locmem" in backend:
        return "in-memory (tests)"
    return backend or "unknown"


def test_connection() -> tuple[bool, str]:
    """
    Open the configured mail connection (useful for SMTP smoke tests).
    Returns (ok, detail_message).
    """
    try:
        conn = get_connection(fail_silently=False)
        conn.open()
        conn.close()
        return True, f"OK — {email_backend_label()}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
