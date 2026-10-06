"""Smoke-test the configured email backend (console or SMTP)."""

from django.conf import settings
from django.core.management.base import BaseCommand

from core.email import email_backend_label, send_app_mail, test_connection


class Command(BaseCommand):
    help = "Send a test email and/or verify the mail connection"

    def add_arguments(self, parser):
        parser.add_argument(
            "to",
            nargs="?",
            default="",
            help="Recipient address (default: DEFAULT_FROM_EMAIL)",
        )
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="Only open/close the mail connection; do not send a message",
        )

    def handle(self, *args, **options):
        self.stdout.write(f"Backend: {email_backend_label()}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")

        ok, detail = test_connection()
        if ok:
            self.stdout.write(self.style.SUCCESS(f"Connection: {detail}"))
        else:
            self.stdout.write(self.style.ERROR(f"Connection: {detail}"))
            if options["check_only"]:
                return

        if options["check_only"]:
            return

        to = (options["to"] or settings.DEFAULT_FROM_EMAIL or "").strip()
        if not to:
            self.stderr.write(
                self.style.ERROR("No recipient. Pass an address or set DEFAULT_FROM_EMAIL.")
            )
            return

        n = send_app_mail(
            subject="[Propertica] Test email",
            message=(
                "This is a test message from Propertica.\n\n"
                f"Backend: {email_backend_label()}\n"
                "If you received this, outbound email is working.\n"
            ),
            html_message=(
                "<p>This is a <strong>test message</strong> from Propertica.</p>"
                f"<p>Backend: <code>{email_backend_label()}</code></p>"
                "<p>If you received this, outbound email is working.</p>"
            ),
            recipient_list=to,
            fail_silently=False,
        )
        if n:
            self.stdout.write(self.style.SUCCESS(f"Sent test email to {to}"))
        else:
            self.stdout.write(self.style.ERROR(f"Failed to send to {to}"))
