from django.contrib import messages
from django.conf import settings

from core.email import send_app_mail
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from listings.models import Listing, ListingStatus, PropertyCategory


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.db.models import Q
        from django.utils import timezone as tz

        now = tz.now()
        featured = (
            Listing.objects.filter(
                status=ListingStatus.ACTIVE,
                featured_until__gte=now,
            )
            .select_related("category", "owner")
            .prefetch_related("media")
            .order_by("-featured_until")[:8]
        )
        if featured.count() < 8:
            # Fill with recent active if not enough featured
            extra = (
                Listing.objects.filter(status=ListingStatus.ACTIVE)
                .exclude(pk__in=[x.pk for x in featured])
                .select_related("category", "owner")
                .prefetch_related("media")
                .order_by("-published_at")[: 8 - featured.count()]
            )
            ctx["featured_listings"] = list(featured) + list(extra)
            ctx["featured_is_fallback"] = featured.count() == 0
        else:
            ctx["featured_listings"] = featured
            ctx["featured_is_fallback"] = False
        ctx["categories"] = PropertyCategory.objects.all()
        # Active favorites for current user (red neon hearts on home cards)
        if self.request.user.is_authenticated:
            listing_ids = [L.pk for L in ctx["featured_listings"]]
            from listings.models import Favorite

            ctx["favorited_ids"] = set(
                Favorite.objects.filter(
                    account=self.request.user,
                    listing_id__in=listing_ids,
                ).values_list("listing_id", flat=True)
            )
        else:
            ctx["favorited_ids"] = set()
        return ctx


class AboutView(TemplateView):
    template_name = "core/about.html"


class TermsView(TemplateView):
    template_name = "core/terms.html"


class PrivacyView(TemplateView):
    template_name = "core/privacy.html"


class ContactView(View):
    template_name = "core/contact.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        subject = (request.POST.get("subject") or "").strip() or "Contact form"
        body = (request.POST.get("message") or "").strip()

        if not name or not email or not body:
            messages.error(request, "Please fill in name, email, and message.")
            return render(
                request,
                self.template_name,
                {"name": name, "email": email, "subject": subject, "message": body},
            )

        support_to = getattr(settings, "CONTACT_EMAIL", None) or settings.DEFAULT_FROM_EMAIL
        send_app_mail(
            subject=f"[Propertica Contact] {subject}",
            message=f"From: {name} <{email}>\n\n{body}",
            recipient_list=support_to,
            reply_to=[email],
            fail_silently=True,
        )
        messages.success(
            request,
            "Thanks — your message has been sent. We'll get back to you soon.",
        )
        return redirect("core:contact")



class PricingView(TemplateView):
    """P3-3: plan catalog (payment integration stub)."""

    template_name = "core/pricing.html"

    def get_context_data(self, **kwargs):
        from accounts.models import Plan

        ctx = super().get_context_data(**kwargs)
        plans = Plan.objects.filter(is_active=True).prefetch_related("entitlements")
        ctx["plans"] = plans
        return ctx
