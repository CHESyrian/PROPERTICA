from django.contrib import admin, messages
from django.utils import timezone

from listings.models import ListingStatus

from .models import Message, MessageThread, Notification, Report


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("sender", "body", "created_at", "read_at")


@admin.register(MessageThread)
class MessageThreadAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "buyer", "seller", "created_at")
    raw_id_fields = ("listing", "buyer", "seller")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "sender", "created_at", "read_at")
    raw_id_fields = ("thread", "sender")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """P0-5: focused moderation queue for open reports + quick actions."""

    list_display = (
        "id",
        "reason",
        "status",
        "reporter",
        "listing",
        "reported_account",
        "created_at",
    )
    list_filter = ("status", "reason")
    search_fields = ("reason", "details", "reporter__email", "listing__title")
    raw_id_fields = ("listing", "reported_account", "reporter")
    readonly_fields = ("id", "created_at")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50
    actions = (
        "mark_reviewed",
        "mark_dismissed",
        "mark_actioned",
        "remove_reported_listing",
        "suspend_reported_account",
    )

    @admin.action(description="Mark selected as Reviewed")
    def mark_reviewed(self, request, queryset):
        updated = queryset.update(status=Report.Status.REVIEWED)
        self.message_user(request, f"{updated} report(s) marked reviewed.", messages.SUCCESS)

    @admin.action(description="Mark selected as Dismissed")
    def mark_dismissed(self, request, queryset):
        updated = queryset.update(status=Report.Status.DISMISSED)
        self.message_user(request, f"{updated} report(s) dismissed.", messages.SUCCESS)

    @admin.action(description="Mark selected as Actioned")
    def mark_actioned(self, request, queryset):
        updated = queryset.update(status=Report.Status.ACTIONED)
        self.message_user(request, f"{updated} report(s) marked actioned.", messages.SUCCESS)

    @admin.action(description="Remove reported listing(s) + mark Actioned")
    def remove_reported_listing(self, request, queryset):
        removed = 0
        for report in queryset.select_related("listing"):
            if report.listing_id and report.listing:
                listing = report.listing
                listing.status = ListingStatus.REMOVED
                listing.save(update_fields=["status", "updated_at"])
                removed += 1
            report.status = Report.Status.ACTIONED
            report.save(update_fields=["status"])
        self.message_user(
            request,
            f"Removed {removed} listing(s); {queryset.count()} report(s) marked actioned.",
            messages.WARNING,
        )

    @admin.action(description="Suspend reported account(s) + mark Actioned")
    def suspend_reported_account(self, request, queryset):
        from accounts.models import AccountStatus

        suspended = 0
        for report in queryset.select_related("reported_account", "listing"):
            account = report.reported_account
            if account is None and report.listing_id and report.listing:
                account = report.listing.owner
            if account is not None:
                account.status = AccountStatus.SUSPENDED
                account.is_active = False
                account.save(update_fields=["status", "is_active", "updated_at"])
                suspended += 1
            report.status = Report.Status.ACTIONED
            report.save(update_fields=["status"])
        self.message_user(
            request,
            f"Suspended {suspended} account(s); {queryset.count()} report(s) marked actioned.",
            messages.WARNING,
        )



@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "notification_type", "recipient", "read_at", "created_at")
    list_filter = ("notification_type",)
    search_fields = ("title", "body", "recipient__email")
    raw_id_fields = ("recipient",)
    readonly_fields = ("id", "created_at")
