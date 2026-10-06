from django.conf import settings
from django.utils import translation


def site_context(request):
    lang = translation.get_language() or settings.LANGUAGE_CODE
    rtl_langs = getattr(settings, "RTL_LANGUAGES", {"ar"})
    ctx = {
        "SITE_NAME": "PROPERTICA",
        "SITE_TAGLINE": "Find your next property",
        "CURRENT_LANGUAGE": lang,
        "IS_RTL": lang.split("-")[0] in rtl_langs,
        "AVAILABLE_LANGUAGES": settings.LANGUAGES,
        "unread_notification_count": 0,
        "OAUTH_ENABLED": getattr(settings, "OAUTH_ENABLED", False),
        "REQUIRE_ACCOUNT_VERIFICATION": getattr(settings, "REQUIRE_ACCOUNT_VERIFICATION", False),
    }
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        try:
            from messaging.models import Notification

            ctx["unread_notification_count"] = Notification.objects.filter(
                recipient=user, read_at__isnull=True
            ).count()
        except Exception:
            pass
    return ctx
