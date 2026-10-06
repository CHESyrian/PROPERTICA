"""DRF serializers for PROPERTICA API."""

from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework import serializers

from accounts.models import Account, AccountType, AgencyAgent, Plan
from listings.models import (
    Favorite,
    Listing,
    ListingMedia,
    ListingStatus,
    PropertyCategory,
    SavedSearch,
)
from messaging.models import Message, MessageThread, Report


# ── Auth ──────────────────────────────────────────────────────────────

class RegisterSerializer(serializers.Serializer):
    account_type = serializers.ChoiceField(choices=AccountType.choices)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    agency_invite_token = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        if Account.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value.lower()

    def create(self, validated_data):
        validated_data.pop("agency_invite_token", None)
        user = Account.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            account_type=validated_data["account_type"],
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs["email"],
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")
        attrs["user"] = user
        return attrs


class AccountSerializer(serializers.ModelSerializer):
    plan = serializers.SerializerMethodField()
    email_verified = serializers.SerializerMethodField()
    display_name_resolved = serializers.CharField(
        source="resolved_display_name", read_only=True
    )
    agency_id = serializers.UUIDField(read_only=True, allow_null=True)

    class Meta:
        model = Account
        fields = [
            "id",
            "username",
            "account_type",
            "display_name",
            "display_name_resolved",
            "email",
            "phone",
            "agency_id",
            "plan",
            "email_verified",
            "status",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "email", "account_type", "status", "date_joined"]

    def get_plan(self, obj):
        return obj.plan.code if obj.plan_id else "free"

    def get_email_verified(self, obj):
        return obj.email_verified_at is not None

    def update(self, instance, validated_data):
        # Personal accounts: ignore display_name changes for public resolution
        if instance.account_type == AccountType.PERSONAL:
            validated_data.pop("display_name", None)
        if instance.account_type == AccountType.AGENT and instance.agency_id:
            validated_data.pop("display_name", None)
        return super().update(instance, validated_data)


class PublicAccountSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="resolved_display_name", read_only=True)
    email_verified = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "username",
            "account_type",
            "display_name",
            "email_verified",
        ]

    def get_email_verified(self, obj):
        return obj.email_verified_at is not None


# ── Listings ──────────────────────────────────────────────────────────

class ListingMediaSerializer(serializers.ModelSerializer):
    display_url = serializers.CharField(read_only=True)

    class Meta:
        model = ListingMedia
        fields = ["id", "url", "display_url", "sort_order", "is_cover", "alt_text"]


class ListingListSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.code", read_only=True)
    category_label = serializers.CharField(source="category.label", read_only=True)
    owner_display_name = serializers.CharField(
        source="owner.resolved_display_name", read_only=True
    )
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "price",
            "currency",
            "negotiable",
            "city",
            "region",
            "country",
            "latitude",
            "longitude",
            "area_value",
            "status",
            "category_code",
            "category_label",
            "owner_display_name",
            "cover_url",
            "published_at",
            "created_at",
        ]

    def get_cover_url(self, obj):
        cover = obj.media.filter(is_cover=True).first() or obj.media.first()
        return cover.display_url if cover else ""


class ListingDetailSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.code", read_only=True)
    category_label = serializers.CharField(source="category.label", read_only=True)
    owner = PublicAccountSerializer(read_only=True)
    media = ListingMediaSerializer(many=True, read_only=True)

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "description",
            "price",
            "currency",
            "negotiable",
            "address_line",
            "city",
            "region",
            "country",
            "latitude",
            "longitude",
            "area_value",
            "type_attributes",
            "status",
            "category_code",
            "category_label",
            "owner",
            "media",
            "featured_until",
            "published_at",
            "expires_at",
            "created_at",
            "updated_at",
        ]


class ListingCreateUpdateSerializer(serializers.ModelSerializer):
    category_code = serializers.SlugRelatedField(
        source="category",
        slug_field="code",
        queryset=PropertyCategory.objects.all(),
    )

    class Meta:
        model = Listing
        fields = [
            "category_code",
            "title",
            "description",
            "price",
            "currency",
            "negotiable",
            "address_line",
            "city",
            "region",
            "country",
            "latitude",
            "longitude",
            "area_value",
            "type_attributes",
        ]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        validated_data["status"] = ListingStatus.DRAFT
        return super().create(validated_data)


class ListingStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            ListingStatus.ACTIVE,
            ListingStatus.UNDER_OFFER,
            ListingStatus.SOLD,
            ListingStatus.DRAFT,
        ]
    )


# ── Favorites / saved search ──────────────────────────────────────────

class FavoriteSerializer(serializers.ModelSerializer):
    listing = ListingListSerializer(read_only=True)
    listing_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Favorite
        fields = ["id", "listing", "listing_id", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        listing_id = validated_data.pop("listing_id")
        listing = Listing.objects.get(pk=listing_id, status=ListingStatus.ACTIVE)
        fav, _ = Favorite.objects.get_or_create(
            account=self.context["request"].user,
            listing=listing,
        )
        return fav


# ── Messaging ─────────────────────────────────────────────────────────

class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    sender_display_name = serializers.CharField(
        source="sender.resolved_display_name", read_only=True
    )

    class Meta:
        model = Message
        fields = [
            "id",
            "sender_username",
            "sender_display_name",
            "body",
            "read_at",
            "created_at",
        ]
        read_only_fields = ["id", "read_at", "created_at"]


class MessageThreadSerializer(serializers.ModelSerializer):
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    listing_id = serializers.UUIDField(read_only=True)
    buyer_username = serializers.CharField(source="buyer.username", read_only=True)
    seller_username = serializers.CharField(source="seller.username", read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = MessageThread
        fields = [
            "id",
            "listing_id",
            "listing_title",
            "buyer_username",
            "seller_username",
            "last_message",
            "created_at",
        ]

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-created_at").first()
        if not msg:
            return None
        return MessageSerializer(msg).data


class ContactMessageSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=10, max_length=2000)


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["id", "listing", "reason", "details", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]


# ── Agency invite ─────────────────────────────────────────────────────

class AgencyInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
