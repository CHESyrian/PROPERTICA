"""Tests for the accounts app: models, display-name resolution, auth views."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Account, AccountType, AgencyAgent, Plan, PlanEntitlement

User = get_user_model()


class PlanModelTests(TestCase):
    def test_create_free_plan(self):
        plan = Plan.objects.create(code="free", label="Free", applies_to="all")
        self.assertEqual(str(plan), "Free")
        self.assertTrue(plan.is_active)

    def test_plan_entitlement(self):
        plan = Plan.objects.create(code="free", label="Free")
        ent = PlanEntitlement.objects.create(
            plan=plan,
            entitlement_key="max_active_listings",
            entitlement_value="10",
        )
        self.assertEqual(ent.entitlement_value, "10")
        self.assertIn("max_active_listings", str(ent))


class AccountModelTests(TestCase):
    def setUp(self):
        self.plan = Plan.objects.create(code="free", label="Free", applies_to="all")
        PlanEntitlement.objects.create(
            plan=self.plan,
            entitlement_key="max_active_listings",
            entitlement_value="5",
        )

    def test_create_personal_user_generates_usr_username(self):
        user = User.objects.create_user(
            email="buyer@example.com",
            password="testpass123",
            account_type=AccountType.PERSONAL,
        )
        self.assertTrue(user.username.startswith("USR"))
        self.assertEqual(len(user.username), 13)  # USR + 10 digits
        self.assertEqual(user.account_type, AccountType.PERSONAL)
        self.assertTrue(user.check_password("testpass123"))

    def test_username_is_unique(self):
        a = User.objects.create_user(email="a@example.com", password="x")
        b = User.objects.create_user(email="b@example.com", password="x")
        self.assertNotEqual(a.username, b.username)

    def test_resolved_display_name_personal_is_username(self):
        user = User.objects.create_user(
            email="p@example.com",
            password="x",
            account_type=AccountType.PERSONAL,
            display_name="Should Be Ignored",
        )
        self.assertEqual(user.resolved_display_name, user.username)

    def test_resolved_display_name_agency(self):
        agency = User.objects.create_user(
            email="agency@example.com",
            password="x",
            account_type=AccountType.AGENCY,
            display_name="Sunrise Realty",
        )
        self.assertEqual(agency.resolved_display_name, "Sunrise Realty")

    def test_resolved_display_name_agent_linked_to_agency(self):
        agency = User.objects.create_user(
            email="agency2@example.com",
            password="x",
            account_type=AccountType.AGENCY,
            display_name="Horizon Homes",
        )
        agent = User.objects.create_user(
            email="agent@example.com",
            password="x",
            account_type=AccountType.AGENT,
            display_name="Agent Name",
            agency=agency,
        )
        self.assertEqual(agent.resolved_display_name, "Horizon Homes")

    def test_resolved_display_name_independent_agent(self):
        agent = User.objects.create_user(
            email="solo@example.com",
            password="x",
            account_type=AccountType.AGENT,
            display_name="Solo Agent",
        )
        self.assertEqual(agent.resolved_display_name, "Solo Agent")

    def test_get_entitlement(self):
        user = User.objects.create_user(
            email="e@example.com",
            password="x",
            plan=self.plan,
        )
        self.assertEqual(user.get_entitlement("max_active_listings"), "5")
        self.assertIsNone(user.get_entitlement("missing_key"))
        self.assertEqual(user.get_entitlement("missing_key", "default"), "default")

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass",
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_agency_agent_link(self):
        agency = User.objects.create_user(
            email="ag@example.com",
            password="x",
            account_type=AccountType.AGENCY,
            display_name="Agency Co",
        )
        agent = User.objects.create_user(
            email="ag-agent@example.com",
            password="x",
            account_type=AccountType.AGENT,
        )
        link = AgencyAgent.objects.create(agency=agency, agent=agent, status="active")
        self.assertEqual(link.status, "active")
        self.assertIn(str(agent), str(link))


class AuthViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        Plan.objects.get_or_create(code="free", defaults={"label": "Free", "applies_to": "all"})

    def test_register_page_loads(self):
        resp = self.client.get(reverse("accounts:register"))
        self.assertEqual(resp.status_code, 200)

    def test_login_page_loads(self):
        resp = self.client.get(reverse("accounts:login"))
        self.assertEqual(resp.status_code, 200)

    def test_register_creates_user_and_logs_in(self):
        resp = self.client.post(
            reverse("accounts:register"),
            {
                "email": "newuser@example.com",
                "account_type": AccountType.PERSONAL,
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_dashboard_authenticated(self):
        user = User.objects.create_user(email="dash@example.com", password="pass12345")
        self.client.login(email="dash@example.com", password="pass12345")
        resp = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(resp.status_code, 200)


class EmailVerificationTests(TestCase):
    """P0-3: signed email verification flow."""

    def setUp(self):
        Plan.objects.get_or_create(code="free", defaults={"label": "Free", "applies_to": "all"})
        self.client = Client()
        self.user = User.objects.create_user(
            email="verify@example.com", password="pass12345"
        )

    def test_token_roundtrip(self):
        from accounts.tokens import load_email_verification_token, make_email_verification_token

        token = make_email_verification_token(self.user.id, self.user.email)
        data = load_email_verification_token(token)
        self.assertEqual(data["uid"], str(self.user.id))
        self.assertEqual(data["email"], self.user.email)

    def test_verify_email_sets_timestamp(self):
        from accounts.tokens import make_email_verification_token

        self.assertIsNone(self.user.email_verified_at)
        token = make_email_verification_token(self.user.id, self.user.email)
        resp = self.client.get(reverse("accounts:verify_email", kwargs={"token": token}))
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.email_verified_at)

    def test_invalid_token(self):
        resp = self.client.get(reverse("accounts:verify_email", kwargs={"token": "not-valid"}))
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.email_verified_at)

    def test_resend_requires_login(self):
        resp = self.client.post(reverse("accounts:resend_verification"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_resend_when_logged_in(self):
        self.client.login(email="verify@example.com", password="pass12345")
        resp = self.client.post(reverse("accounts:resend_verification"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("accounts:profile"))

    def test_register_sends_verification_flag(self):
        resp = self.client.post(
            reverse("accounts:register"),
            {
                "email": "newbie@example.com",
                "account_type": AccountType.PERSONAL,
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
        )
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(email="newbie@example.com")
        self.assertIsNone(user.email_verified_at)


class AgencyPublicPageTests(TestCase):
    def setUp(self):
        Plan.objects.get_or_create(code="free", defaults={"label": "Free", "applies_to": "all"})
        self.client = Client()
        self.agency = User.objects.create_user(
            email="agency@example.com",
            password="pass12345",
            account_type=AccountType.AGENCY,
            display_name="Skyline Realty",
        )

    def test_agency_public_page(self):
        resp = self.client.get(
            reverse("accounts:agency_public", kwargs={"username": self.agency.username})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Skyline Realty")


class ReputationTests(TestCase):
    def setUp(self):
        Plan.objects.get_or_create(code="free", defaults={"label": "Free", "applies_to": "all"})
        self.agent = User.objects.create_user(
            email="agent-rep@example.com",
            password="pass12345",
            account_type=AccountType.AGENT,
        )
        self.personal = User.objects.create_user(
            email="personal-rep@example.com",
            password="pass12345",
            account_type=AccountType.PERSONAL,
        )

    def test_agent_accrues_points(self):
        from accounts.models import ReputationEvent, ReputationSummary
        from accounts.reputation import record_event

        record_event(
            subject=self.agent,
            event_type=ReputationEvent.EventType.LISTING_PUBLISHED,
        )
        summary = ReputationSummary.objects.get(account=self.agent)
        self.assertGreaterEqual(summary.points, 5)
        self.assertEqual(summary.level, 1)

    def test_personal_does_not_accrue(self):
        from accounts.models import ReputationEvent, ReputationSummary
        from accounts.reputation import record_event

        result = record_event(
            subject=self.personal,
            event_type=ReputationEvent.EventType.LISTING_PUBLISHED,
        )
        self.assertIsNone(result)
        self.assertFalse(ReputationSummary.objects.filter(account=self.personal).exists())


class PricingPageTests(TestCase):
    def test_pricing_page(self):
        Plan.objects.get_or_create(code="free", defaults={"label": "Free", "applies_to": "all"})
        resp = Client().get(reverse("core:pricing"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Plans")
