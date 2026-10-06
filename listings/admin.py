from django.contrib import admin

from .models import (
    AttributeDefinition,
    Favorite,
    Listing,
    ListingMedia,
    PropertyCategory,
    SavedSearch,
    ListingViewEvent,
)


class AttributeDefinitionInline(admin.TabularInline):
    model = AttributeDefinition
    extra = 0


@admin.register(PropertyCategory)
class PropertyCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "parent_group")
    list_filter = ("parent_group",)
    inlines = [AttributeDefinitionInline]


class ListingMediaInline(admin.TabularInline):
    model = ListingMedia
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "price",
        "currency",
        "city",
        "status",
        "owner",
        "published_at",
        "view_count",
    )
    list_filter = ("status", "category", "currency")
    search_fields = ("title", "city", "address_line")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ListingMediaInline]
    raw_id_fields = ("owner",)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("account", "listing", "created_at")
    raw_id_fields = ("account", "listing")


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    list_display = ("account", "name", "notify_by_email", "created_at")
    raw_id_fields = ("account",)



@admin.register(ListingViewEvent)
class ListingViewEventAdmin(admin.ModelAdmin):
    list_display = ("listing", "viewer", "session_key", "created_at")
    raw_id_fields = ("listing", "viewer")
    readonly_fields = ("id", "created_at")
