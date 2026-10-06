"""Search service abstraction (P2-5).

Default backend: database (current ListingSearchView logic).
OpenSearch backend is a stub selected via SEARCH_BACKEND=opensearch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.db.models import Q, QuerySet


@dataclass
class SearchFilters:
    q: str = ""
    category: str = ""
    city: str = ""
    price_min: float | None = None
    price_max: float | None = None
    sort: str = "newest"
    lat: float | None = None
    lng: float | None = None
    radius_km: float | None = None
    min_lat: float | None = None
    min_lng: float | None = None
    max_lat: float | None = None
    max_lng: float | None = None
    currency: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class DatabaseSearchBackend:
    def search(self, filters: SearchFilters) -> QuerySet:
        from listings.models import Listing, ListingStatus

        qs = (
            Listing.objects.filter(status=ListingStatus.ACTIVE)
            .select_related("category", "owner")
            .prefetch_related("media")
        )
        if filters.q:
            qs = qs.filter(
                Q(title__icontains=filters.q)
                | Q(description__icontains=filters.q)
                | Q(city__icontains=filters.q)
            )
        if filters.category:
            qs = qs.filter(category__code=filters.category)
        if filters.city:
            qs = qs.filter(city__icontains=filters.city)
        if filters.currency:
            qs = qs.filter(currency__iexact=filters.currency)
        if filters.price_min is not None:
            qs = qs.filter(price__gte=filters.price_min)
        if filters.price_max is not None:
            qs = qs.filter(price__lte=filters.price_max)

        if None not in (filters.min_lat, filters.min_lng, filters.max_lat, filters.max_lng):
            qs = qs.filter(
                latitude__isnull=False,
                longitude__isnull=False,
                latitude__gte=filters.min_lat,
                latitude__lte=filters.max_lat,
                longitude__gte=filters.min_lng,
                longitude__lte=filters.max_lng,
            )
        elif filters.lat is not None and filters.lng is not None and filters.radius_km:
            import math

            lat, lng, radius_km = filters.lat, filters.lng, filters.radius_km
            dlat = radius_km / 111.0
            cos_lat = max(0.01, abs(math.cos(math.radians(lat))))
            dlng = radius_km / (111.0 * cos_lat)
            qs = qs.filter(
                latitude__isnull=False,
                longitude__isnull=False,
                latitude__gte=lat - dlat,
                latitude__lte=lat + dlat,
                longitude__gte=lng - dlng,
                longitude__lte=lng + dlng,
            )
            ids = []
            for row in qs.values("id", "latitude", "longitude")[:500]:
                if row["latitude"] is None:
                    continue
                r = 6371.0
                p1, p2 = math.radians(lat), math.radians(float(row["latitude"]))
                dphi = math.radians(float(row["latitude"]) - lat)
                dl = math.radians(float(row["longitude"]) - lng)
                a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
                dist = 2 * r * math.asin(math.sqrt(a))
                if dist <= radius_km:
                    ids.append(row["id"])
            qs = qs.filter(pk__in=ids)

        sort = filters.sort or "newest"
        if sort == "price_asc":
            qs = qs.order_by("price")
        elif sort == "price_desc":
            qs = qs.order_by("-price")
        elif sort == "area_asc":
            qs = qs.order_by("area_value")
        elif sort == "area_desc":
            qs = qs.order_by("-area_value")
        else:
            qs = qs.order_by("-published_at")
        return qs


class OpenSearchBackend:
    """Stub: falls back to database until a cluster is configured."""

    def search(self, filters: SearchFilters) -> QuerySet:
        # Future: translate filters to OpenSearch DSL using OPENSEARCH_URL
        return DatabaseSearchBackend().search(filters)


def get_search_backend():
    backend = getattr(settings, "SEARCH_BACKEND", "db")
    if backend == "opensearch":
        return OpenSearchBackend()
    return DatabaseSearchBackend()


def search_listings(filters: SearchFilters) -> QuerySet:
    return get_search_backend().search(filters)
