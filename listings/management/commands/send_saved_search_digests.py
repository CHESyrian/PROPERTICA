"""P3-4: email digests for saved searches with new matching listings."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.email import send_app_mail
from listings.models import SavedSearch
from search_app.services import SearchFilters, search_listings


class Command(BaseCommand):
    help = "Send saved-search digest emails for new matching listings"

    def handle(self, *args, **options):
        now = timezone.now()
        sent = 0
        for ss in SavedSearch.objects.filter(notify_by_email=True).select_related(
            "account"
        ):
            filters_data = ss.filters or {}

            def _f(key):
                v = filters_data.get(key)
                if v in (None, ""):
                    return None
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None

            filters = SearchFilters(
                q=filters_data.get("q") or "",
                category=filters_data.get("category") or "",
                city=filters_data.get("city") or "",
                price_min=_f("price_min"),
                price_max=_f("price_max"),
                sort=filters_data.get("sort") or "newest",
            )
            qs = search_listings(filters)
            if ss.last_notified_at:
                qs = qs.filter(published_at__gt=ss.last_notified_at)
            else:
                qs = qs.filter(published_at__isnull=False)
            matches = list(qs[:20])
            if not matches:
                continue
            lines = [f"- {m.title} ({m.currency} {m.price}) — {m.city}" for m in matches]
            body = (
                f"New listings matching your saved search “{ss.name or 'Untitled'}”:\n\n"
                + "\n".join(lines)
                + "\n\nVisit Propertica to view them.\n"
            )
            send_app_mail(
                subject=f"[Propertica] {len(matches)} new listing(s) for “{ss.name or 'your search'}”",
                message=body,
                recipient_list=ss.account.email,
                fail_silently=True,
            )
            ss.last_notified_at = now
            ss.save(update_fields=["last_notified_at"])
            sent += 1
        self.stdout.write(self.style.SUCCESS(f"Digests sent: {sent}"))
