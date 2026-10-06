from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Account,
    AgencyAgent,
    Plan,
    PlanEntitlement,
    ReputationEvent,
    ReputationSummary,
)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "applies_to", "is_active")


@admin.register(PlanEntitlement)
class PlanEntitlementAdmin(admin.ModelAdmin):
    list_display = ("plan", "entitlement_key", "entitlement_value")
    list_filter = ("plan",)


@admin.register(Account)
class AccountAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "account_type",
        "display_name",
        "status",
        "is_staff",
        "date_joined",
    )
    list_filter = ("account_type", "status", "is_staff")
    search_fields = ("username", "email", "display_name")
    ordering = ("-date_joined",)
    readonly_fields = ("username", "id", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Identity",
            {
                "fields": (
                    "username",
                    "account_type",
                    "display_name",
                    "phone",
                    "agency",
                    "plan",
                    "status",
                )
            },
        ),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Verification", {"fields": ("email_verified_at", "phone_verified_at", "oauth_provider")}),
        ("Dates", {"fields": ("date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "account_type", "password1", "password2"),
            },
        ),
    )


@admin.register(AgencyAgent)
class AgencyAgentAdmin(admin.ModelAdmin):
    list_display = ("agency", "agent", "status", "invited_at", "joined_at")
    list_filter = ("status",)


@admin.register(ReputationEvent)
class ReputationEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "subject", "actor", "value", "created_at")
    list_filter = ("event_type",)
    raw_id_fields = ("subject", "actor")


@admin.register(ReputationSummary)
class ReputationSummaryAdmin(admin.ModelAdmin):
    list_display = ("account", "points", "experience", "level", "rating_count", "updated_at")
    raw_id_fields = ("account",)
