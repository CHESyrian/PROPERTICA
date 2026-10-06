"""P2-4: periodic maintenance tasks (expire listings, clear featured)."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from listings.models import Listing, ListingStatus


class Command(BaseCommand):
    help = "Run maintenance: expire listings, clear stale featured flags"

    def handle(self, *args, **options):
        now = timezone.now()
        expired = Listing.objects.filter(
            status=ListingStatus.ACTIVE,
            expires_at__isnull=False,
            expires_at__lt=now,
        ).update(status=ListingStatus.EXPIRED)
        self.stdout.write(self.style.SUCCESS(f"Expired listings: {expired}"))

        # Featured flags in the past are ignored by queries; optional no-op clear
        stale_featured = Listing.objects.filter(
            featured_until__isnull=False,
            featured_until__lt=now,
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Stale featured flags (ignored by homepage): {stale_featured}"
            )
        )
        self.stdout.write(self.style.SUCCESS("Maintenance complete."))
