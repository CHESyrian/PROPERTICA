"""Tests for messaging: contact seller, inbox, threads."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Plan
from listings.models import Listing, ListingStatus, PropertyCategory, PropertyParentGroup
from messaging.forms import ContactSellerForm, ReplyForm
from messaging.models import Message, MessageThread, Report

User = get_user_model()


class MessagingFixturesMixin:
    def setUp(self):
        Plan.objects.get_or_create(code="free", defaults={"label": "Free", "applies_to": "all"})
        self.seller = User.objects.create_user(
            email="seller@example.com", password="pass12345"
        )
        self.buyer = User.objects.create_user(
            email="buyer@example.com", password="pass12345"
        )
        self.category = PropertyCategory.objects.create(
            code="house",
            label="House",
            parent_group=PropertyParentGroup.RESIDENTIAL,
        )
        self.listing = Listing.objects.create(
            owner=self.seller,
            category=self.category,
            title="Message Test House",
            price=Decimal("200000"),
            currency="EUR",
            city="Damascus",
            country="Syria",
            status=ListingStatus.ACTIVE,
            published_at=timezone.now(),
        )


class MessageModelTests(MessagingFixturesMixin, TestCase):
    def test_create_thread_and_message(self):
        thread = MessageThread.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
        )
        msg = Message.objects.create(
            thread=thread,
            sender=self.buyer,
            body="Is this still available?",
        )
        self.assertEqual(thread.messages.count(), 1)
        self.assertIn(str(thread.id), str(thread))
        self.assertIn("Message", str(msg))

    def test_unique_thread_per_buyer_listing(self):
        MessageThread.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
        )
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            MessageThread.objects.create(
                listing=self.listing,
                buyer=self.buyer,
                seller=self.seller,
            )

    def test_report_model(self):
        report = Report.objects.create(
            listing=self.listing,
            reporter=self.buyer,
            reason="spam",
            details="Looks fake",
        )
        self.assertEqual(report.status, Report.Status.OPEN)


class ContactSellerViewTests(MessagingFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_contact_requires_login(self):
        resp = self.client.post(
            reverse("messaging:contact", args=[self.listing.pk]),
            {"body": "Hello, is this available still?"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_contact_creates_thread(self):
        self.client.login(email="buyer@example.com", password="pass12345")
        resp = self.client.post(
            reverse("messaging:contact", args=[self.listing.pk]),
            {"body": "Hello, is this property still available for viewing?"},
        )
        self.assertEqual(resp.status_code, 302)
        thread = MessageThread.objects.get(listing=self.listing, buyer=self.buyer)
        self.assertEqual(thread.seller, self.seller)
        self.assertEqual(thread.messages.count(), 1)
        self.assertIn("available", thread.messages.first().body)

    def test_contact_cannot_message_own_listing(self):
        self.client.login(email="seller@example.com", password="pass12345")
        resp = self.client.post(
            reverse("messaging:contact", args=[self.listing.pk]),
            {"body": "Talking to myself should fail here."},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(MessageThread.objects.count(), 0)

    def test_contact_rejects_short_message(self):
        self.client.login(email="buyer@example.com", password="pass12345")
        resp = self.client.post(
            reverse("messaging:contact", args=[self.listing.pk]),
            {"body": "Hi"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(MessageThread.objects.count(), 0)

    def test_second_contact_reuses_thread(self):
        self.client.login(email="buyer@example.com", password="pass12345")
        url = reverse("messaging:contact", args=[self.listing.pk])
        self.client.post(url, {"body": "First message about availability please."})
        self.client.post(url, {"body": "Second follow-up message about viewing times."})
        self.assertEqual(MessageThread.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 2)


class InboxViewTests(MessagingFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.thread = MessageThread.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
        )
        Message.objects.create(
            thread=self.thread,
            sender=self.buyer,
            body="Initial inquiry about the property listing.",
        )

    def test_inbox_requires_login(self):
        resp = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(resp.status_code, 302)

    def test_inbox_shows_threads_for_buyer(self):
        self.client.login(email="buyer@example.com", password="pass12345")
        resp = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.listing.title)

    def test_inbox_shows_threads_for_seller(self):
        self.client.login(email="seller@example.com", password="pass12345")
        resp = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.listing.title)


class ThreadDetailViewTests(MessagingFixturesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.thread = MessageThread.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            seller=self.seller,
        )
        Message.objects.create(
            thread=self.thread,
            sender=self.buyer,
            body="Can we schedule a viewing this weekend?",
        )

    def test_thread_accessible_by_participant(self):
        self.client.login(email="buyer@example.com", password="pass12345")
        resp = self.client.get(
            reverse("messaging:thread", args=[self.thread.pk])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "schedule a viewing")

    def test_thread_forbidden_for_outsider(self):
        outsider = User.objects.create_user(
            email="other@example.com", password="pass12345"
        )
        self.client.login(email="other@example.com", password="pass12345")
        resp = self.client.get(
            reverse("messaging:thread", args=[self.thread.pk])
        )
        self.assertEqual(resp.status_code, 404)

    def test_reply_creates_message(self):
        self.client.login(email="seller@example.com", password="pass12345")
        resp = self.client.post(
            reverse("messaging:thread", args=[self.thread.pk]),
            {"body": "Yes, Saturday at 10am works for me."},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.thread.messages.count(), 2)
        self.assertEqual(self.thread.messages.last().sender, self.seller)

    def test_marks_messages_read(self):
        self.client.login(email="seller@example.com", password="pass12345")
        self.client.get(reverse("messaging:thread", args=[self.thread.pk]))
        msg = self.thread.messages.first()
        msg.refresh_from_db()
        self.assertIsNotNone(msg.read_at)


class MessagingFormTests(TestCase):
    def test_contact_form_min_length(self):
        form = ContactSellerForm(data={"body": "short"})
        self.assertFalse(form.is_valid())

    def test_contact_form_valid(self):
        form = ContactSellerForm(
            data={"body": "This is a long enough inquiry message."}
        )
        self.assertTrue(form.is_valid())

    def test_reply_form(self):
        form = ReplyForm(data={"body": "OK"})
        self.assertTrue(form.is_valid())


class ReportModerationTests(MessagingFixturesMixin, TestCase):
    """P0-5: admin actions for report queue."""

    def _admin_request(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.backends.db import SessionStore
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post("/admin/")
        request.user = User.objects.create_superuser(
            email="admin-mod@example.com", password="pass12345"
        )
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_remove_reported_listing_action(self):
        from django.contrib.admin.sites import AdminSite

        from messaging.admin import ReportAdmin

        report = Report.objects.create(
            listing=self.listing,
            reporter=self.buyer,
            reason="spam",
            details="Looks fake",
            status=Report.Status.OPEN,
        )
        request = self._admin_request()
        admin_obj = ReportAdmin(Report, AdminSite())
        admin_obj.remove_reported_listing(request, Report.objects.filter(pk=report.pk))

        report.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(report.status, Report.Status.ACTIONED)
        self.assertEqual(self.listing.status, ListingStatus.REMOVED)

    def test_mark_dismissed_action(self):
        from django.contrib.admin.sites import AdminSite

        from messaging.admin import ReportAdmin

        report = Report.objects.create(
            listing=self.listing,
            reporter=self.buyer,
            reason="incorrect",
            status=Report.Status.OPEN,
        )
        request = self._admin_request()
        admin_obj = ReportAdmin(Report, AdminSite())
        admin_obj.mark_dismissed(request, Report.objects.filter(pk=report.pk))
        report.refresh_from_db()
        self.assertEqual(report.status, Report.Status.DISMISSED)


class NotificationServiceTests(MessagingFixturesMixin, TestCase):
    """P1-3 / P1-4: notifications + lead email helper."""

    def test_notify_new_lead_creates_notification(self):
        from messaging.models import Notification
        from messaging.services import notify_new_lead

        thread = MessageThread.objects.create(
            listing=self.listing, buyer=self.buyer, seller=self.seller
        )
        notify_new_lead(
            seller=self.seller,
            buyer=self.buyer,
            listing=self.listing,
            thread=thread,
            message_body="I am interested in this house.",
        )
        n = Notification.objects.get(recipient=self.seller)
        self.assertEqual(n.notification_type, Notification.Type.NEW_LEAD)
        self.assertIn(self.listing.title, n.title)
        self.assertTrue(n.link)

    def test_notifications_list_requires_login(self):
        resp = self.client.get(reverse("messaging:notifications"))
        self.assertEqual(resp.status_code, 302)

    def test_notifications_list_authenticated(self):
        from messaging.models import Notification

        Notification.objects.create(
            recipient=self.seller,
            notification_type="system",
            title="Hello",
            body="Test",
        )
        self.client.login(email="seller@example.com", password="pass12345")
        resp = self.client.get(reverse("messaging:notifications"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hello")
