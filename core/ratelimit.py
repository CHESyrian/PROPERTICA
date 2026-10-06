"""Simple cache-backed rate limiting (P2-1)."""

from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse


def _client_key(request) -> str:
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        return f"user:{request.user.pk}"
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return f"ip:{xff.split(',')[0].strip()}"
    return f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"


def is_rate_limited(request, scope: str) -> bool:
    limits = getattr(settings, "RATE_LIMITS", {})
    limit, window = limits.get(scope, (60, 3600))
    key = f"rl:{scope}:{_client_key(request)}"
    count = cache.get(key, 0)
    if count >= limit:
        return True
    if count == 0:
        cache.set(key, 1, window)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, count + 1, window)
    return False


def rate_limit(scope: str, *, json_response: bool = False):
    """Decorator for FBVs or method views (wrap dispatch/get/post)."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if is_rate_limited(request, scope):
                if json_response or request.headers.get("Accept", "").startswith(
                    "application/json"
                ):
                    return JsonResponse(
                        {
                            "error": {
                                "code": "RATE_LIMITED",
                                "message": "Too many requests. Please try again later.",
                            }
                        },
                        status=429,
                    )
                return HttpResponse(
                    "Too many requests. Please try again later.",
                    status=429,
                    content_type="text/plain",
                )
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


class RateLimitMixin:
    """Mixin for class-based views: set rate_limit_scope = 'contact'."""

    rate_limit_scope: str | None = None
    rate_limit_json: bool = False

    def dispatch(self, request, *args, **kwargs):
        scope = getattr(self, "rate_limit_scope", None)
        if scope and is_rate_limited(request, scope):
            if self.rate_limit_json or request.headers.get("Accept", "").startswith(
                "application/json"
            ):
                return JsonResponse(
                    {
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many requests. Please try again later.",
                        }
                    },
                    status=429,
                )
            from django.contrib import messages
            from django.shortcuts import redirect

            messages.error(request, "Too many requests. Please try again later.")
            return redirect(request.META.get("HTTP_REFERER") or "/")
        return super().dispatch(request, *args, **kwargs)
