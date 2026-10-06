from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core import signing
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, TemplateView

from core.email import send_app_mail
from core.ratelimit import RateLimitMixin, is_rate_limited

from listings.models import Listing, ListingStatus

from .forms import LoginForm, ProfileForm, RegisterForm
from .models import Account, AccountType, AgencyAgent
from .tokens import (
    check_verification_code,
    clear_verification_code,
    generate_verification_code,
    store_verification_code,
)


def send_verification_email(request, user: Account) -> str:
    """Send an 8-character verification code (xxxx-xxxx). Returns the code (for tests)."""
    code = generate_verification_code()
    store_verification_code(user.id, user.email, code)
    subject = "Your Propertica verification code"
    text_body = (
        "Hi,\n\n"
        "Your Propertica email verification code is:\n\n"
        f"  {code}\n\n"
        "Enter this code on your profile page. It expires in 48 hours.\n\n"
        "If you did not create an account, you can ignore this message.\n"
    )
    html_body = (
        "<p>Hi,</p>"
        "<p>Your Propertica email verification code is:</p>"
        f'<p style="font-size:1.5rem;font-weight:700;letter-spacing:0.12em;'
        f'font-family:ui-monospace,monospace;color:#06b6d4;">{code}</p>'
        "<p>Enter this code on your profile page. It expires in 48 hours.</p>"
        "<p>If you did not create an account, you can ignore this message.</p>"
    )
    send_app_mail(
        subject=subject,
        message=text_body,
        html_message=html_body,
        recipient_list=user.email,
        fail_silently=True,
    )
    return code


class RegisterView(RateLimitMixin, CreateView):
    rate_limit_scope = "register"
    model = Account
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:dashboard")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        send_verification_email(self.request, user)
        messages.info(
            self.request,
            "Account created. Check your email for an 8-character verification code "
            "(also printed to the server console in development).",
        )
        return redirect(self.success_url)


class VerifyEmailView(LoginRequiredMixin, View):
    """Confirm email with an 8-character code from the verification email."""

    def get(self, request, token=None):
        # Old bookmark links → profile where the code form lives
        return redirect("accounts:profile")

    def post(self, request, token=None):
        user = request.user
        if user.email_verified_at:
            messages.info(request, "Your email is already verified.")
            return redirect("accounts:profile")

        code = (request.POST.get("code") or request.POST.get("token") or "").strip()
        if not code:
            messages.error(request, "Enter the verification code from your email.")
            return redirect("accounts:profile")

        if not check_verification_code(user.id, user.email, code):
            messages.error(
                request,
                "Invalid or expired verification code. Request a new one.",
            )
            return redirect("accounts:profile")

        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at", "updated_at"])
        clear_verification_code(user.id)
        messages.success(request, "Email verified successfully. Thank you!")
        return redirect("accounts:dashboard")


class ResendVerificationView(LoginRequiredMixin, View):
    """Resend verification code email from profile."""

    def post(self, request):
        user = request.user
        if user.email_verified_at:
            messages.info(request, "Your email is already verified.")
            return redirect("accounts:profile")
        send_verification_email(request, user)
        messages.success(
            request,
            "Verification code sent. Check your inbox (or the server console in development).",
        )
        return redirect("accounts:profile")


class AccountLoginView(RateLimitMixin, LoginView):
    rate_limit_scope = "login"
    form_class = LoginForm
    template_name = "accounts/login.html"


class AccountLogoutView(LogoutView):
    next_page = reverse_lazy("core:home")
    http_method_names = ["get", "post", "options", "head"]

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        listings = user.listings.select_related("category").order_by("-updated_at")
        active_count = listings.filter(status=ListingStatus.ACTIVE).count()
        ctx["my_listings"] = listings[:50]
        ctx["stats"] = {
            "total": listings.count(),
            "active": active_count,
            "draft": listings.filter(status=ListingStatus.DRAFT).count(),
            "sold": listings.filter(status=ListingStatus.SOLD).count(),
            "under_offer": listings.filter(status=ListingStatus.UNDER_OFFER).count(),
        }
        from django.db.models import Sum
        from messaging.models import MessageThread

        ctx["stats"]["total_views"] = (
            listings.aggregate(s=Sum("view_count"))["s"] or 0
        )
        ctx["stats"]["total_leads"] = MessageThread.objects.filter(
            seller=user
        ).count()
        ctx["can_feature"] = (
            str(user.get_entitlement("can_feature_listing", default="false")).lower()
            in ("1", "true", "yes")
        )

        # Plan quota (P0-1) — shown on dashboard.
        raw_max = user.get_entitlement("max_active_listings", default="10")
        try:
            max_active = int(raw_max) if raw_max is not None else None
        except (TypeError, ValueError):
            max_active = 10
        ctx["quota"] = {
            "active": active_count,
            "max_active": max_active,
            "at_limit": max_active is not None and active_count >= max_active,
        }

        if user.account_type == AccountType.AGENCY:
            ctx["agency_agents"] = (
                AgencyAgent.objects.filter(agency=user)
                .exclude(status=AgencyAgent.Status.REMOVED)
                .select_related("agent")
                .order_by("-invited_at")
            )
            ctx["is_agency"] = True
        else:
            ctx["is_agency"] = False

        if user.account_type == AccountType.AGENT:
            ctx["pending_invites"] = (
                AgencyAgent.objects.filter(
                    agent=user, status=AgencyAgent.Status.INVITED
                )
                .select_related("agency")
                .order_by("-invited_at")
            )
            ctx["is_agent"] = True
        else:
            ctx["is_agent"] = False

        return ctx


class ProfileView(LoginRequiredMixin, View):
    template_name = "accounts/profile.html"

    def get(self, request):
        form = ProfileForm(instance=request.user)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            old_phone = (request.user.phone or "").strip()
            user = form.save(commit=False)
            # Personal: display_name ignored for public resolution
            if user.account_type == AccountType.PERSONAL:
                user.display_name = user.display_name  # stored but not shown
            if user.account_type == AccountType.AGENT and user.agency_id:
                # Keep linked agent's public name from agency
                pass
            new_phone = (user.phone or "").strip()
            # Changing or clearing phone invalidates prior phone verification
            if new_phone != old_phone:
                user.phone_verified_at = None
            user.save()
            messages.success(request, "Profile updated.")
            if new_phone and new_phone != old_phone:
                messages.info(
                    request,
                    "Phone number saved. You can verify it on this page.",
                )
            return redirect("accounts:profile")
        return render(request, self.template_name, {"form": form})


class AgencyInviteView(LoginRequiredMixin, View):
    def post(self, request):
        if request.user.account_type != AccountType.AGENCY:
            messages.error(request, "Only agency accounts can invite agents.")
            return redirect("accounts:dashboard")

        email = (request.POST.get("email") or "").strip().lower()
        if not email:
            messages.error(request, "Email is required.")
            return redirect("accounts:dashboard")

        agent = Account.objects.filter(
            email__iexact=email, account_type=AccountType.AGENT
        ).first()
        if not agent:
            messages.error(
                request,
                "No agent account found with that email. They must register as Agent first.",
            )
            return redirect("accounts:dashboard")

        link, created = AgencyAgent.objects.get_or_create(
            agency=request.user,
            agent=agent,
            defaults={"status": AgencyAgent.Status.INVITED},
        )
        if not created:
            if link.status == AgencyAgent.Status.ACTIVE:
                messages.info(request, "This agent is already linked to your agency.")
                return redirect("accounts:dashboard")
            link.status = AgencyAgent.Status.INVITED
            link.invited_at = timezone.now()
            link.save(update_fields=["status", "invited_at"])

        messages.success(request, f"Invite sent to {email}.")
        return redirect("accounts:dashboard")


class AgencyRemoveAgentView(LoginRequiredMixin, View):
    def post(self, request, link_id):
        link = get_object_or_404(
            AgencyAgent, pk=link_id, agency=request.user
        )
        link.status = AgencyAgent.Status.REMOVED
        link.save(update_fields=["status"])
        agent = link.agent
        if agent.agency_id == request.user.id:
            agent.agency = None
            agent.save(update_fields=["agency"])
        messages.success(request, "Agent removed from agency.")
        return redirect("accounts:dashboard")


class AgencyAcceptInviteView(LoginRequiredMixin, View):
    def post(self, request, link_id):
        link = get_object_or_404(
            AgencyAgent,
            pk=link_id,
            agent=request.user,
            status=AgencyAgent.Status.INVITED,
        )
        link.status = AgencyAgent.Status.ACTIVE
        link.joined_at = timezone.now()
        link.save(update_fields=["status", "joined_at"])
        request.user.agency = link.agency
        request.user.save(update_fields=["agency"])
        messages.success(
            request, f"You joined {link.agency.resolved_display_name}."
        )
        return redirect("accounts:dashboard")


class AgencyDeclineInviteView(LoginRequiredMixin, View):
    def post(self, request, link_id):
        link = get_object_or_404(
            AgencyAgent,
            pk=link_id,
            agent=request.user,
            status=AgencyAgent.Status.INVITED,
        )
        link.status = AgencyAgent.Status.REMOVED
        link.save(update_fields=["status"])
        messages.info(request, "Invite declined.")
        return redirect("accounts:dashboard")



class AgencyPublicView(View):
    """P1-2: public agency brand page."""

    template_name = "accounts/agency_public.html"

    def get(self, request, username):
        agency = get_object_or_404(
            Account,
            username=username,
            account_type=AccountType.AGENCY,
            status="active",
        )
        agents = (
            AgencyAgent.objects.filter(agency=agency, status=AgencyAgent.Status.ACTIVE)
            .select_related("agent")
            .order_by("joined_at")
        )
        from listings.models import Listing, ListingStatus

        listings = (
            Listing.objects.filter(owner=agency, status=ListingStatus.ACTIVE)
            .select_related("category")
            .prefetch_related("media")
            .order_by("-published_at")[:24]
        )
        # Also include listings owned by linked agents
        agent_ids = [a.agent_id for a in agents]
        agent_listings = (
            Listing.objects.filter(owner_id__in=agent_ids, status=ListingStatus.ACTIVE)
            .select_related("category", "owner")
            .prefetch_related("media")
            .order_by("-published_at")[:24]
            if agent_ids
            else []
        )
        return render(
            request,
            self.template_name,
            {
                "agency": agency,
                "agents": agents,
                "listings": listings,
                "agent_listings": agent_listings,
            },
        )


class PublicProfileView(View):
    """Lightweight public profile by username (agency redirects to brand page)."""

    def get(self, request, username):
        account = get_object_or_404(Account, username=username, status="active")
        if account.account_type == AccountType.AGENCY:
            return redirect("accounts:agency_public", username=username)
        from listings.models import Listing, ListingStatus

        listings = (
            Listing.objects.filter(owner=account, status=ListingStatus.ACTIVE)
            .select_related("category")
            .prefetch_related("media")
            .order_by("-published_at")[:24]
        )
        return render(
            request,
            "accounts/public_profile.html",
            {"profile": account, "listings": listings},
        )



class RequestPhoneCodeView(LoginRequiredMixin, RateLimitMixin, View):
    rate_limit_scope = "phone_code"
    """P1-6: send a 6-digit code (console/email in dev)."""

    def post(self, request):
        import random
        import logging

        phone = (request.POST.get("phone") or "").strip() or (request.user.phone or "")
        if not phone:
            messages.error(request, "Enter a phone number first.")
            return redirect("accounts:profile")

        code = f"{random.randint(0, 999999):06d}"
        request.session["phone_verify"] = {
            "phone": phone,
            "code": code,
            "sent_at": timezone.now().isoformat(),
        }
        # Persist phone on profile if provided
        if phone != (request.user.phone or ""):
            request.user.phone = phone
            request.user.save(update_fields=["phone", "updated_at"])

        logger = logging.getLogger(__name__)
        logger.info("Phone verification code for %s: %s", phone, code)
        send_app_mail(
            subject="Your Propertica phone verification code",
            message=f"Your verification code is: {code}\nValid for 15 minutes.",
            recipient_list=request.user.email,
            fail_silently=True,
        )
        messages.success(
            request,
            "Verification code sent (check email / server console in development).",
        )
        return redirect("accounts:profile")


class ConfirmPhoneCodeView(LoginRequiredMixin, View):
    """P1-6: confirm phone code and set phone_verified_at."""

    def post(self, request):
        from datetime import timedelta

        data = request.session.get("phone_verify") or {}
        code = (request.POST.get("code") or "").strip()
        if not data or not code:
            messages.error(request, "Enter the verification code.")
            return redirect("accounts:profile")

        sent_at = data.get("sent_at")
        try:
            sent = timezone.datetime.fromisoformat(sent_at)
            if timezone.is_naive(sent):
                sent = timezone.make_aware(sent)
        except Exception:
            sent = None
        if sent and timezone.now() - sent > timedelta(minutes=15):
            messages.error(request, "Code expired. Request a new one.")
            return redirect("accounts:profile")

        if code != data.get("code"):
            messages.error(request, "Invalid code.")
            return redirect("accounts:profile")

        user = request.user
        user.phone = data.get("phone") or user.phone
        user.phone_verified_at = timezone.now()
        user.save(update_fields=["phone", "phone_verified_at", "updated_at"])
        request.session.pop("phone_verify", None)
        messages.success(request, "Phone number verified.")
        return redirect("accounts:profile")



class DataExportView(LoginRequiredMixin, View):
    """P3-2: download a JSON export of the user's data."""

    def get(self, request):
        import json
        from django.http import HttpResponse

        from listings.models import Favorite, Listing, SavedSearch
        from messaging.models import Message, MessageThread

        user = request.user
        listings = list(
            Listing.objects.filter(owner=user).values(
                "id", "title", "status", "price", "currency", "city", "created_at"
            )
        )
        for row in listings:
            for k, v in list(row.items()):
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()
                else:
                    row[k] = str(v)
        payload = {
            "account": {
                "username": user.username,
                "email": user.email,
                "account_type": user.account_type,
                "display_name": user.display_name,
                "phone": user.phone,
                "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            },
            "listings": listings,
            "favorites": [
                str(x) for x in Favorite.objects.filter(account=user).values_list("listing_id", flat=True)
            ],
            "saved_searches": list(
                SavedSearch.objects.filter(account=user).values("name", "filters", "created_at")
            ),
            "message_threads": MessageThread.objects.filter(
                Q(buyer=user) | Q(seller=user)
            ).count(),
        }
        for ss in payload["saved_searches"]:
            if ss.get("created_at") and hasattr(ss["created_at"], "isoformat"):
                ss["created_at"] = ss["created_at"].isoformat()
        body = json.dumps(payload, indent=2, default=str)
        resp = HttpResponse(body, content_type="application/json")
        resp["Content-Disposition"] = 'attachment; filename="propertica-export.json"'
        return resp


class AccountDeleteView(LoginRequiredMixin, View):
    """P3-2: soft-delete account (anonymize + deactivate)."""

    def post(self, request):
        confirm = (request.POST.get("confirm") or "").strip().lower()
        if confirm not in ("delete", "yes"):
            messages.error(request, 'Type "delete" to confirm account deletion.')
            return redirect("accounts:profile")
        user = request.user
        from accounts.models import AccountStatus

        user.status = AccountStatus.DELETED
        user.is_active = False
        user.email = f"deleted-{user.username}@invalid.local"
        user.phone = None
        user.display_name = None
        user.set_unusable_password()
        user.save()
        from django.contrib.auth import logout

        logout(request)
        messages.success(request, "Your account has been deleted.")
        return redirect("core:home")
