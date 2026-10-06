"""Reputation helpers (P3-1)."""

from __future__ import annotations

from accounts.models import Account, AccountType, ReputationEvent, ReputationSummary

# Points mapping (tunable later)
POINTS = {
    ReputationEvent.EventType.LISTING_PUBLISHED: 5,
    ReputationEvent.EventType.LEAD_RECEIVED: 2,
    ReputationEvent.EventType.LEAD_RESPONDED: 3,
    ReputationEvent.EventType.RATING_RECEIVED: 0,  # value comes from rating
    ReputationEvent.EventType.LISTING_SOLD: 25,
    ReputationEvent.EventType.MANUAL_ADJUST: 0,
}

LEVEL_THRESHOLDS = [0, 50, 150, 400, 1000, 2500]


def _level_for_xp(xp: int) -> int:
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS, start=1):
        if xp >= threshold:
            level = i
    return level


def can_accrue(account: Account) -> bool:
    return account.account_type in (AccountType.AGENT, AccountType.AGENCY)


def record_event(
    *,
    subject: Account,
    event_type: str,
    actor: Account | None = None,
    value: int | None = None,
    metadata: dict | None = None,
) -> ReputationEvent | None:
    if not can_accrue(subject):
        return None
    if value is None:
        value = POINTS.get(event_type, 0)
    event = ReputationEvent.objects.create(
        subject=subject,
        actor=actor,
        event_type=event_type,
        value=value,
        metadata=metadata or {},
    )
    summary, _ = ReputationSummary.objects.get_or_create(account=subject)
    summary.points += value
    summary.experience += max(value, 0)
    summary.level = _level_for_xp(summary.experience)
    if event_type == ReputationEvent.EventType.RATING_RECEIVED and metadata:
        rating = int(metadata.get("rating") or 0)
        if 1 <= rating <= 5:
            summary.rating_sum += rating
            summary.rating_count += 1
    summary.save()
    return event
