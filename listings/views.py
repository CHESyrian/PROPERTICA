"""Listing views: search, detail, multi-step create wizard, publish, media."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DetailView, ListView, UpdateView

from core.ratelimit import RateLimitMixin

from messaging.forms import ContactSellerForm

from .forms import ListingWizardForm
from .models import (
    AttributeDefinition,
    Favorite,
    Listing,
    ListingMedia,
    ListingStatus,
    PropertyCategory,
)


class ListingSearchView(ListView):
    model = Listing
    template_name = "listings/search.html"
    context_object_name = "listings"
    paginate_by = 20

    def get_queryset(self):
        from search_app.services import SearchFilters, search_listings

        g = self.request.GET

        def _f(name):
            try:
                v = g.get(name)
                return float(v) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None

        filters = SearchFilters(
            q=(g.get("q") or "").strip(),
            category=(g.get("category") or "").strip(),
            city=(g.get("city") or "").strip(),
            price_min=_f("price_min"),
            price_max=_f("price_max"),
            sort=(g.get("sort") or "newest").strip(),
            lat=_f("lat"),
            lng=_f("lng"),
            radius_km=_f("radius_km"),
            min_lat=_f("min_lat"),
            min_lng=_f("min_lng"),
            max_lat=_f("max_lat"),
            max_lng=_f("max_lng"),
            currency=(g.get("currency") or "").strip().upper(),
        )
        return search_listings(filters)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = PropertyCategory.objects.all()
        ctx["current_filters"] = {
            "q": self.request.GET.get("q", ""),
            "category": self.request.GET.get("category", ""),
            "city": self.request.GET.get("city", ""),
            "price_min": self.request.GET.get("price_min", ""),
            "price_max": self.request.GET.get("price_max", ""),
            "sort": self.request.GET.get("sort", "newest"),
            "lat": self.request.GET.get("lat", ""),
            "lng": self.request.GET.get("lng", ""),
            "radius_km": self.request.GET.get("radius_km", ""),
            "currency": self.request.GET.get("currency", ""),
        }
        # Map pins for listings with coordinates (current page)
        pins = []
        for listing in ctx["listings"]:
            if listing.latitude is not None and listing.longitude is not None:
                pins.append({
                    "id": str(listing.pk),
                    "title": listing.title,
                    "price": str(listing.price),
                    "currency": listing.currency,
                    "lat": float(listing.latitude),
                    "lng": float(listing.longitude),
                    "url": reverse("listings:detail", args=[listing.pk]),
                })
        ctx["map_pins_json"] = json.dumps(pins)
        if self.request.user.is_authenticated:
            ids = set(
                Favorite.objects.filter(
                    account=self.request.user,
                    listing_id__in=[L.pk for L in ctx["listings"]],
                ).values_list("listing_id", flat=True)
            )
            ctx["favorited_ids"] = ids
        else:
            ctx["favorited_ids"] = set()
        return ctx


    def _parse_bbox(self):
        g = self.request.GET
        try:
            min_lat = float(g.get("min_lat"))
            min_lng = float(g.get("min_lng"))
            max_lat = float(g.get("max_lat"))
            max_lng = float(g.get("max_lng"))
        except (TypeError, ValueError):
            return None
        if min_lat > max_lat:
            min_lat, max_lat = max_lat, min_lat
        if min_lng > max_lng:
            min_lng, max_lng = max_lng, min_lng
        return (min_lat, min_lng, max_lat, max_lng)

    def _parse_radius_center(self):
        g = self.request.GET
        try:
            lat = float(g.get("lat"))
            lng = float(g.get("lng"))
            radius_km = float(g.get("radius_km") or 0)
        except (TypeError, ValueError):
            return None
        if radius_km <= 0:
            return None
        return (lat, lng, radius_km)

    def _filter_haversine(self, qs, lat, lng, radius_km):
        import math

        def haversine_km(lat1, lon1, lat2, lon2):
            r = 6371.0
            p1, p2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dl = math.radians(lon2 - lon1)
            a = (
                math.sin(dphi / 2) ** 2
                + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
            )
            return 2 * r * math.asin(math.sqrt(a))

        ids = []
        # Avoid only() + select_related conflict; values() is enough for distance check
        for row in qs.values("id", "latitude", "longitude")[:500]:
            if row["latitude"] is None or row["longitude"] is None:
                continue
            if haversine_km(lat, lng, float(row["latitude"]), float(row["longitude"])) <= radius_km:
                ids.append(row["id"])
        return qs.filter(pk__in=ids)



class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/detail.html"
    context_object_name = "listing"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        listing = self.object
        # Don't count owner views
        if not request.user.is_authenticated or request.user.id != listing.owner_id:
            try:
                listing.record_view()
                from .models import ListingViewEvent

                ListingViewEvent.objects.create(
                    listing=listing,
                    viewer=request.user if request.user.is_authenticated else None,
                    session_key=(request.session.session_key or "")[:40],
                )
            except Exception:
                pass
        return response

    def get_queryset(self):
        return (
            Listing.objects.select_related("category", "owner")
            .prefetch_related("media", "category__attribute_definitions")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["contact_form"] = ContactSellerForm()
        listing = self.object
        user = self.request.user
        ctx["is_favorited"] = False
        ctx["has_phone"] = bool(listing.owner.phone)
        if user.is_authenticated:
            ctx["is_favorited"] = Favorite.objects.filter(
                account=user, listing=listing
            ).exists()
            if user.id != listing.owner_id:
                from messaging.models import MessageThread

                existing = MessageThread.objects.filter(
                    listing=listing, buyer=user
                ).first()
                ctx["existing_thread"] = existing

        # P0-4: similar listings (same category, prefer same city).
        similar = (
            Listing.objects.filter(
                status=ListingStatus.ACTIVE,
                category_id=listing.category_id,
            )
            .exclude(pk=listing.pk)
            .select_related("category", "owner")
            .prefetch_related("media")
        )
        if listing.city:
            same_city = list(similar.filter(city__iexact=listing.city)[:6])
            if len(same_city) < 6:
                extra = list(
                    similar.exclude(city__iexact=listing.city).order_by("-published_at")[
                        : 6 - len(same_city)
                    ]
                )
                ctx["similar_listings"] = same_city + extra
            else:
                ctx["similar_listings"] = same_city
        else:
            ctx["similar_listings"] = list(similar.order_by("-published_at")[:6])

        # Cover / first image for Open Graph + JSON-LD (P1-1)
        media = list(listing.media.all())
        cover = next((m for m in media if m.is_cover), media[0] if media else None)
        ctx["og_image"] = cover.display_url if cover else ""

        request = self.request
        abs_url = request.build_absolute_uri()
        image_url = ""
        if cover and cover.display_url:
            path = cover.display_url
            if path.startswith("http"):
                image_url = path
            else:
                image_url = f"{request.scheme}://{request.get_host()}{path}"

        ld = {
            "@context": "https://schema.org",
            "@type": "RealEstateListing",
            "name": listing.title,
            "description": (listing.description or "")[:300],
            "url": abs_url,
            "offers": {
                "@type": "Offer",
                "price": str(listing.price),
                "priceCurrency": listing.currency,
            },
        }
        if listing.published_at:
            ld["datePosted"] = listing.published_at.isoformat()
        if image_url:
            ld["image"] = image_url
        if listing.latitude is not None and listing.longitude is not None:
            ld["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": str(listing.latitude),
                "longitude": str(listing.longitude),
            }
        if listing.city or listing.address_line:
            ld["address"] = {
                "@type": "PostalAddress",
                "streetAddress": listing.address_line or "",
                "addressLocality": listing.city or "",
                "addressRegion": listing.region or "",
                "addressCountry": listing.country or "",
            }
        ctx["json_ld"] = json.dumps(ld, ensure_ascii=False)
        return ctx


class ListingWizardView(LoginRequiredMixin, View):
    """Multi-step listing creation wizard with forms."""

    template_name = "listings/wizard.html"

    def _categories_and_attr_map(self):
        categories = list(
            PropertyCategory.objects.prefetch_related("attribute_definitions").all()
        )
        attr_map = {}
        for cat in categories:
            attr_map[str(cat.id)] = [
                {
                    "key": d.attribute_key,
                    "label": d.label or d.attribute_key.replace("_", " ").title(),
                    "data_type": d.data_type,
                    "is_required": d.is_required,
                    "enum_options": d.enum_options or [],
                    "display_order": d.display_order,
                }
                for d in cat.attribute_definitions.all()
            ]
        steps = [
            {"num": 1, "label": "Type"},
            {"num": 2, "label": "Basics"},
            {"num": 3, "label": "Location"},
            {"num": 4, "label": "Details"},
            {"num": 5, "label": "Photos"},
            {"num": 6, "label": "Review"},
        ]
        return categories, attr_map, steps

    def get(self, request):
        categories, attr_map, steps = self._categories_and_attr_map()
        form = ListingWizardForm()
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "categories": categories,
                "attr_map_json": json.dumps(attr_map),
                "steps": steps,
            },
        )

    def post(self, request):
        category_id = request.POST.get("category")
        attribute_defs = []
        category = None
        if category_id:
            try:
                category = PropertyCategory.objects.get(pk=category_id)
                attribute_defs = list(category.attribute_definitions.all())
            except (PropertyCategory.DoesNotExist, ValueError):
                pass

        form = ListingWizardForm(request.POST, attribute_defs=attribute_defs)
        categories, attr_map, steps = self._categories_and_attr_map()

        if not form.is_valid():
            messages.error(request, "Please fix the errors below.")
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "categories": categories,
                    "attr_map_json": json.dumps(attr_map),
                    "steps": steps,
                    "initial_step": self._infer_error_step(form),
                },
            )

        cleaned = form.cleaned_data
        action = cleaned.get("action") or request.POST.get("action") or "draft"

        with transaction.atomic():
            listing = Listing(
                owner=request.user,
                category=cleaned["category"],
                title=cleaned["title"],
                description=cleaned.get("description") or "",
                price=cleaned["price"],
                currency=cleaned["currency"],
                negotiable=cleaned.get("negotiable", False),
                address_line=cleaned.get("address_line") or "",
                city=cleaned["city"],
                region=cleaned.get("region") or "",
                country=cleaned.get("country") or "",
                latitude=cleaned.get("latitude"),
                longitude=cleaned.get("longitude"),
                area_value=cleaned.get("area_value"),
                type_attributes=cleaned.get("type_attributes") or {},
                status=ListingStatus.DRAFT,
            )
            listing.full_clean()
            listing.save()

            files = request.FILES.getlist("photos")
            cover_index = cleaned.get("cover_index") or 0
            try:
                cover_index = int(cover_index)
            except (TypeError, ValueError):
                cover_index = 0

            media_count = 0
            for i, f in enumerate(files):
                if not getattr(f, "content_type", "").startswith("image/"):
                    continue
                ListingMedia.objects.create(
                    listing=listing,
                    image=f,
                    sort_order=i,
                    is_cover=(i == cover_index),
                    alt_text=listing.title,
                )
                media_count += 1

            if action == "publish":
                # P0-7: require at least one photo before going live.
                if media_count < 1:
                    messages.error(
                        request,
                        "Add at least one photo before publishing. "
                        "Your listing was saved as a draft.",
                    )
                else:
                    try:
                        listing.publish()
                        messages.success(request, "Listing published successfully!")
                    except ValidationError as exc:
                        msg = (
                            "; ".join(exc.messages)
                            if hasattr(exc, "messages")
                            else str(exc)
                        )
                        messages.error(request, msg)
            else:
                messages.success(request, "Listing saved as draft.")

        return redirect("accounts:dashboard")

    def _infer_error_step(self, form) -> int:
        step1 = {"category"}
        step2 = {"title", "description", "price", "currency", "negotiable"}
        step3 = {"address_line", "city", "region", "country", "latitude", "longitude"}
        for field in form.errors:
            if field in step1:
                return 1
            if field in step2:
                return 2
            if field in step3:
                return 3
            if field == "area_value" or field.startswith("attr_"):
                return 4
        return 1



class ListingPublishView(LoginRequiredMixin, UpdateView):
    model = Listing
    fields = []
    http_method_names = ["post"]

    def get_queryset(self):
        return Listing.objects.filter(owner=self.request.user)

    def form_valid(self, form):
        listing = form.instance
        try:
            listing.publish()
            messages.success(self.request, "Listing published.")
        except ValidationError as exc:
            msg = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            messages.error(self.request, msg)
        return redirect("accounts:dashboard")


class CategoryAttributesAPI(View):
    """Return attribute definitions for a category (JSON) — for dynamic form."""

    def get(self, request, category_id):
        cat = get_object_or_404(PropertyCategory, pk=category_id)
        defs = [
            {
                "key": d.attribute_key,
                "label": d.label or d.attribute_key.replace("_", " ").title(),
                "data_type": d.data_type,
                "is_required": d.is_required,
                "enum_options": d.enum_options or [],
                "display_order": d.display_order,
            }
            for d in cat.attribute_definitions.all()
        ]
        return JsonResponse({"category": cat.code, "attributes": defs})


class GeocodeAPI(RateLimitMixin, View):
    rate_limit_scope = "geocode"
    rate_limit_json = True
    """
    Address → lat/lng via Photon (Komoot / OpenStreetMap data).
    Server-side proxy avoids CORS and keeps a single integration point.
    """

    def get(self, request):
        q = (request.GET.get("q") or "").strip()
        if not q or len(q) < 3:
            return JsonResponse({"error": "Query too short"}, status=400)

        # Map / geocode language follows active site language (en, ar, …)
        from django.utils import translation

        lang = (request.GET.get("lang") or translation.get_language() or "en").split("-")[0]
        if lang not in ("en", "ar", "fr", "de", "es", "it", "nl", "ru", "tr"):
            lang = "en"

        params = urllib.parse.urlencode({"q": q, "limit": 5, "lang": lang})
        url = f"https://photon.komoot.io/api/?{params}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "PROPERTICA/1.0 (dev)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=502)

        results = []
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            coords = (feat.get("geometry") or {}).get("coordinates") or [None, None]
            lon, lat = coords[0], coords[1]
            # Photon property names vary; build a readable label
            parts = [
                props.get("name"),
                props.get("street"),
                props.get("housenumber"),
                props.get("city") or props.get("town") or props.get("village"),
                props.get("state"),
                props.get("country"),
            ]
            display = ", ".join(p for p in parts if p)
            if not display:
                display = props.get("name") or f"{lat}, {lon}"

            street_parts = [props.get("housenumber"), props.get("street") or props.get("name")]
            road = " ".join(p for p in street_parts if p)

            results.append({
                "display_name": display,
                "lat": str(lat) if lat is not None else None,
                "lon": str(lon) if lon is not None else None,
                "city": props.get("city") or props.get("town") or props.get("village") or props.get("county") or "",
                "region": props.get("state") or props.get("district") or "",
                "country": props.get("country") or "",
                "road": props.get("street") or "",
                "house_number": props.get("housenumber") or "",
            })
        return JsonResponse({"results": results})


class ReverseGeocodeAPI(RateLimitMixin, View):
    """lat/lng → address fields via Photon reverse."""

    rate_limit_scope = "geocode"
    rate_limit_json = True

    def get(self, request):
        try:
            lat = float(request.GET.get("lat"))
            lon = float(request.GET.get("lon") or request.GET.get("lng"))
        except (TypeError, ValueError):
            return JsonResponse({"error": "lat and lon required"}, status=400)

        from django.utils import translation

        lang = (request.GET.get("lang") or translation.get_language() or "en").split("-")[0]
        if lang not in ("en", "ar", "fr", "de", "es", "it", "nl", "ru", "tr"):
            lang = "en"

        params = urllib.parse.urlencode(
            {"lat": lat, "lon": lon, "limit": 1, "lang": lang}
        )
        url = f"https://photon.komoot.io/reverse?{params}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "PROPERTICA/1.0 (dev)", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=502)

        feats = data.get("features") or []
        if not feats:
            return JsonResponse(
                {
                    "lat": str(lat),
                    "lon": str(lon),
                    "city": "",
                    "region": "",
                    "country": "",
                    "address_line": "",
                    "display_name": f"{lat}, {lon}",
                }
            )

        props = feats[0].get("properties") or {}
        street_parts = [props.get("housenumber"), props.get("street") or props.get("name")]
        road = " ".join(p for p in street_parts if p)
        city = props.get("city") or props.get("town") or props.get("village") or props.get("county") or ""
        region = props.get("state") or props.get("district") or ""
        country = props.get("country") or ""
        parts = [road, city, region, country]
        display = ", ".join(p for p in parts if p) or f"{lat}, {lon}"
        return JsonResponse(
            {
                "lat": str(lat),
                "lon": str(lon),
                "city": city,
                "region": region,
                "country": country,
                "address_line": road,
                "road": props.get("street") or "",
                "house_number": props.get("housenumber") or "",
                "display_name": display,
            }
        )


class FavoriteToggleView(LoginRequiredMixin, View):
    """POST toggle favorite; returns JSON for AJAX, otherwise redirects."""

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, status=ListingStatus.ACTIVE)
        fav, created = Favorite.objects.get_or_create(
            account=request.user, listing=listing
        )
        if not created:
            fav.delete()
            favorited = False
        else:
            favorited = True

        wants_json = (
            request.headers.get("HX-Request")
            or request.GET.get("format") == "json"
            or "application/json" in (request.headers.get("Accept") or "")
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )
        if wants_json:
            return JsonResponse({"favorited": favorited, "listing_id": str(pk)})

        if favorited:
            messages.success(request, "Saved to favorites.")
        else:
            messages.info(request, "Removed from favorites.")
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse(
            "listings:detail", args=[pk]
        )
        return redirect(next_url)


class FavoritesListView(LoginRequiredMixin, ListView):
    template_name = "listings/favorites.html"
    context_object_name = "listings"
    paginate_by = 20

    def get_queryset(self):
        return (
            Listing.objects.filter(
                favorited_by__account=self.request.user,
                status=ListingStatus.ACTIVE,
            )
            .select_related("category", "owner")
            .prefetch_related("media")
            .distinct()
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["favorited_ids"] = {L.pk for L in ctx["listings"]}
        return ctx


class ListingEditView(LoginRequiredMixin, View):
    """Owner edit for core listing fields."""

    template_name = "listings/edit.html"

    def get_listing(self, request, pk):
        return get_object_or_404(Listing, pk=pk, owner=request.user)

    def get(self, request, pk):
        listing = self.get_listing(request, pk)
        from .forms import ListingEditForm
        form = ListingEditForm(instance=listing)
        return render(request, self.template_name, {"form": form, "listing": listing})

    def post(self, request, pk):
        listing = self.get_listing(request, pk)
        from .forms import ListingEditForm
        form = ListingEditForm(request.POST, instance=listing)
        if form.is_valid():
            form.save()
            messages.success(request, "Listing updated.")
            return redirect("listings:detail", pk=listing.pk)
        return render(request, self.template_name, {"form": form, "listing": listing})


class PhoneRevealView(LoginRequiredMixin, View):
    """Return owner phone for a listing (click-to-reveal)."""

    def get(self, request, pk):
        listing = get_object_or_404(
            Listing.objects.select_related("owner"),
            pk=pk,
            status__in=[ListingStatus.ACTIVE, ListingStatus.UNDER_OFFER],
        )
        phone = listing.owner.phone
        if not phone:
            return JsonResponse({"error": "No phone number available"}, status=404)
        return JsonResponse({
            "phone": phone,
            "owner": listing.owner.resolved_display_name,
        })


class ReportListingView(LoginRequiredMixin, RateLimitMixin, View):
    rate_limit_scope = "report"
    """Flag a listing as fraudulent/incorrect."""

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk)
        reason = (request.POST.get("reason") or "other").strip()[:60]
        details = (request.POST.get("details") or "").strip()
        if listing.owner_id == request.user.id:
            messages.error(request, "You cannot report your own listing.")
            return redirect("listings:detail", pk=pk)

        from messaging.models import Report
        Report.objects.create(
            listing=listing,
            reporter=request.user,
            reason=reason or "other",
            details=details,
        )
        messages.success(request, "Thanks — we received your report.")
        return redirect("listings:detail", pk=pk)


class ListingSetStatusView(LoginRequiredMixin, View):
    """Owner changes listing status (publish / under_offer / sold / draft)."""

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, owner=request.user)
        new_status = (request.POST.get("status") or "").strip()
        allowed = {
            ListingStatus.DRAFT,
            ListingStatus.ACTIVE,
            ListingStatus.UNDER_OFFER,
            ListingStatus.SOLD,
        }
        if new_status not in allowed:
            messages.error(request, "Invalid status.")
            return redirect("accounts:dashboard")

        if new_status == ListingStatus.ACTIVE:
            try:
                listing.publish()
            except Exception as exc:
                messages.error(request, str(exc))
                return redirect("accounts:dashboard")
        else:
            listing.status = new_status
            listing.save(update_fields=["status", "updated_at"])

        messages.success(request, f"Listing marked as {listing.get_status_display()}.")
        next_url = request.POST.get("next") or reverse("accounts:dashboard")
        return redirect(next_url)


# ── Saved searches (P0-2) ─────────────────────────────────────────────

class SavedSearchCreateView(LoginRequiredMixin, View):
    """Save current search filters from the search results page."""

    def post(self, request):
        from .models import SavedSearch

        name = (request.POST.get("name") or "").strip() or "My search"
        filters = {
            "q": (request.POST.get("q") or "").strip(),
            "category": (request.POST.get("category") or "").strip(),
            "city": (request.POST.get("city") or "").strip(),
            "price_min": (request.POST.get("price_min") or "").strip(),
            "price_max": (request.POST.get("price_max") or "").strip(),
            "sort": (request.POST.get("sort") or "newest").strip(),
        }
        notify = request.POST.get("notify_by_email") == "on"
        SavedSearch.objects.create(
            account=request.user,
            name=name[:120],
            filters=filters,
            notify_by_email=notify,
        )
        messages.success(request, f'Search "{name}" saved.')
        # Rebuild query string for redirect back to search
        from urllib.parse import urlencode

        qs = {k: v for k, v in filters.items() if v}
        return redirect(reverse("listings:search") + ("?" + urlencode(qs) if qs else ""))


class SavedSearchListView(LoginRequiredMixin, ListView):
    template_name = "listings/saved_searches.html"
    context_object_name = "saved_searches"

    def get_queryset(self):
        from .models import SavedSearch

        return SavedSearch.objects.filter(account=self.request.user).order_by("-created_at")


class SavedSearchDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from .models import SavedSearch

        ss = get_object_or_404(SavedSearch, pk=pk, account=request.user)
        name = ss.name or "Saved search"
        ss.delete()
        messages.success(request, f'"{name}" deleted.')
        return redirect("listings:saved_searches")


class SavedSearchUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        from .models import SavedSearch

        ss = get_object_or_404(SavedSearch, pk=pk, account=request.user)
        name = (request.POST.get("name") or "").strip()
        if name:
            ss.name = name[:120]
        ss.notify_by_email = request.POST.get("notify_by_email") == "on"
        ss.save(update_fields=["name", "notify_by_email"])
        messages.success(request, "Saved search updated.")
        return redirect("listings:saved_searches")



class ListingFeatureView(LoginRequiredMixin, View):
    """P2-2: activate featured placement if plan allows."""

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, owner=request.user)
        try:
            listing.feature()
            messages.success(
                request,
                f"Listing featured until {listing.featured_until:%b %d, %Y}.",
            )
        except ValidationError as exc:
            msg = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
            messages.error(request, msg)
        return redirect("accounts:dashboard")



class ListingBulkStatusView(LoginRequiredMixin, View):
    """P3-5: bulk status change for owner's listings."""

    def post(self, request):
        ids = request.POST.getlist("listing_ids")
        new_status = (request.POST.get("status") or "").strip()
        allowed = {
            ListingStatus.DRAFT,
            ListingStatus.ACTIVE,
            ListingStatus.UNDER_OFFER,
            ListingStatus.SOLD,
        }
        if new_status not in allowed or not ids:
            messages.error(request, "Select listings and a valid status.")
            return redirect("accounts:dashboard")

        qs = Listing.objects.filter(owner=request.user, pk__in=ids)
        updated = 0
        errors = 0
        for listing in qs:
            if new_status == ListingStatus.ACTIVE:
                try:
                    listing.publish()
                    updated += 1
                except ValidationError:
                    errors += 1
            else:
                listing.status = new_status
                listing.save(update_fields=["status", "updated_at"])
                updated += 1
        messages.success(
            request,
            f"Updated {updated} listing(s)"
            + (f"; {errors} could not be published." if errors else "."),
        )
        return redirect("accounts:dashboard")
