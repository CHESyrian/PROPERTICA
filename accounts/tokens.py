"""Email verification codes (8 chars: abcd-efgh style)."""

from __future__ import annotations

import hashlib
import secrets
import string

from django.core.cache import cache

VERIFY_MAX_AGE = 60 * 60 * 48  # 48 hours
CODE_ALPHABET = string.ascii_lowercase + string.digits


def generate_verification_code() -> str:
    """Return an 8-character code formatted as xxxx-xxxx (letters + digits)."""
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def _cache_key(user_id: str) -> str:
    return f"email_verify_code:{user_id}"


def store_verification_code(user_id: str, email: str, code: str) -> None:
    """Store hashed code + email for the user (TTL 48h)."""
    normalized = (code or "").strip().lower().replace(" ", "")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cache.set(
        _cache_key(str(user_id)),
        {
            "digest": digest,
            "email": (email or "").strip().lower(),
        },
        timeout=VERIFY_MAX_AGE,
    )


def check_verification_code(user_id: str, email: str, code: str) -> bool:
    """Validate code for user."""
    data = cache.get(_cache_key(str(user_id)))
    if not data:
        return False
    normalized = (code or "").strip().lower().replace(" ", "")
    if not normalized:
        return False
    compact = normalized.replace("-", "")
    variants = {normalized}
    if len(compact) == 8:
        variants.add(f"{compact[:4]}-{compact[4:]}")
        variants.add(compact)
    for candidate in variants:
        digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        if secrets.compare_digest(digest, data.get("digest", "")):
            stored_email = (data.get("email") or "").lower()
            if stored_email and stored_email != (email or "").strip().lower():
                return False
            return True
    return False


def clear_verification_code(user_id: str) -> None:
    cache.delete(_cache_key(str(user_id)))


def make_email_verification_token(user_id: str, email: str) -> str:
    return generate_verification_code()


def load_email_verification_token(token: str) -> dict:
    raise ValueError("Link tokens are no longer used; submit a verification code.")


def sanitize_token(token: str) -> str:
    return (token or "").strip().lower().replace(" ", "")
