"""Messaging & leads — contact seller, inbox, thread view."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from core.ratelimit import RateLimitMixin

from listings.models import Listing, ListingStatus

from .forms import ContactSellerForm, ReplyForm
from .models import Message, MessageThread


class ContactSellerView(LoginRequiredMixin, RateLimitMixin, View):
    rate_limit_scope = "contact"
    """POST from listing detail — create or append to a thread with the owner."""

    def post(self, request, listing_id):
        listing = get_object_or_404(
            Listing.objects.select_related("owner"),
            pk=listing_id,
            status__in=[
                ListingStatus.ACTIVE,
                ListingStatus.UNDER_OFFER,
            ],
        )
        if listing.owner_id == request.user.id:
            messages.error(request, "You cannot message yourself about your own listing.")
            return redirect("listings:detail", pk=listing.pk)

        form = ContactSellerForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please enter a message (at least 10 characters).")
            return redirect("listings:detail", pk=listing.pk)

        thread, created = MessageThread.objects.get_or_create(
            listing=listing,
            buyer=request.user,
            defaults={"seller": listing.owner},
        )
        # If thread existed but seller changed ownership edge-case, keep original seller
        body = form.cleaned_data["body"].strip()
        Message.objects.create(
            thread=thread,
            sender=request.user,
            body=body,
        )
        if created:
            from .services import notify_new_lead

            notify_new_lead(
                seller=listing.owner,
                buyer=request.user,
                listing=listing,
                thread=thread,
                message_body=body,
            )
        else:
            from .services import notify_new_message

            notify_new_message(
                recipient=listing.owner,
                sender=request.user,
                thread=thread,
                message_body=body,
            )
        messages.success(request, "Message sent. You can continue the conversation in your inbox.")
        return redirect("messaging:thread", thread_id=thread.pk)


class InboxView(LoginRequiredMixin, ListView):
    """Unified inbox: threads where the user is buyer or seller."""

    template_name = "messaging/inbox.html"
    context_object_name = "threads"
    paginate_by = 30

    def get_queryset(self):
        user = self.request.user
        last_msg = (
            Message.objects.filter(thread_id=OuterRef("pk"))
            .order_by("-created_at")
            .values("body")[:1]
        )
        last_at = (
            Message.objects.filter(thread_id=OuterRef("pk"))
            .order_by("-created_at")
            .values("created_at")[:1]
        )
        unread = (
            Message.objects.filter(
                thread_id=OuterRef("pk"),
                read_at__isnull=True,
            )
            .exclude(sender=user)
            .values("thread_id")
            .annotate(c=Count("id"))
            .values("c")[:1]
        )

        return (
            MessageThread.objects.filter(Q(buyer=user) | Q(seller=user))
            .select_related("listing", "listing__category", "buyer", "seller")
            .annotate(
                last_message_body=Subquery(last_msg),
                last_message_at=Subquery(last_at),
                unread_count=Subquery(unread),
            )
            .order_by("-last_message_at", "-created_at")
        )


class ThreadDetailView(LoginRequiredMixin, View):
    """Conversation view — mark others' messages as read, allow reply."""

    template_name = "messaging/thread.html"

    def _get_thread(self, request, thread_id):
        thread = get_object_or_404(
            MessageThread.objects.select_related(
                "listing", "listing__owner", "buyer", "seller"
            ),
            pk=thread_id,
        )
        if request.user.id not in (thread.buyer_id, thread.seller_id):
            raise Http404
        return thread

    def get(self, request, thread_id):
        thread = self._get_thread(request, thread_id)
        # Mark messages from the other party as read
        Message.objects.filter(thread=thread, read_at__isnull=True).exclude(
            sender=request.user
        ).update(read_at=timezone.now())

        msgs = thread.messages.select_related("sender").order_by("created_at")
        other = thread.seller if request.user.id == thread.buyer_id else thread.buyer
        return render(
            request,
            self.template_name,
            {
                "thread": thread,
                "thread_messages": msgs,
                "other_party": other,
                "form": ReplyForm(),
                "is_buyer": request.user.id == thread.buyer_id,
            },
        )

    def post(self, request, thread_id):
        thread = self._get_thread(request, thread_id)
        form = ReplyForm(request.POST)
        if form.is_valid():
            body = form.cleaned_data["body"].strip()
            Message.objects.create(
                thread=thread,
                sender=request.user,
                body=body,
            )
            recipient = (
                thread.seller if request.user.id == thread.buyer_id else thread.buyer
            )
            from .services import notify_new_message

            notify_new_message(
                recipient=recipient,
                sender=request.user,
                thread=thread,
                message_body=body,
            )
            messages.success(request, "Reply sent.")
            return redirect("messaging:thread", thread_id=thread.pk)
        msgs = thread.messages.select_related("sender").order_by("created_at")
        other = thread.seller if request.user.id == thread.buyer_id else thread.buyer
        return render(
            request,
            self.template_name,
            {
                "thread": thread,
                "thread_messages": msgs,
                "other_party": other,
                "form": form,
                "is_buyer": request.user.id == thread.buyer_id,
            },
        )



class NotificationListView(LoginRequiredMixin, ListView):
    """P1-3: in-app notification center."""

    template_name = "messaging/notifications.html"
    context_object_name = "notifications"
    paginate_by = 30

    def get_queryset(self):
        from .models import Notification

        return Notification.objects.filter(recipient=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from .models import Notification

        ctx["unread_count"] = Notification.objects.filter(
            recipient=self.request.user, read_at__isnull=True
        ).count()
        return ctx


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request, pk=None):
        from .models import Notification

        if pk:
            updated = Notification.objects.filter(
                recipient=request.user, pk=pk, read_at__isnull=True
            ).update(read_at=timezone.now())
        else:
            updated = Notification.objects.filter(
                recipient=request.user, read_at__isnull=True
            ).update(read_at=timezone.now())
        if request.headers.get("HX-Request") or request.GET.get("format") == "json":
            from django.http import JsonResponse

            return JsonResponse({"marked": updated})
        messages.success(request, "Notifications marked as read.")
        return redirect("messaging:notifications")
