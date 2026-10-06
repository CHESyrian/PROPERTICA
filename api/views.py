"""DRF API views — PROPERTICA v1."""

from __future__ import annotations

from django.contrib.auth import login, logout
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Account, AccountType, AgencyAgent
from listings.models import Favorite, Listing, ListingStatus, PropertyCategory
from messaging.models import Message, MessageThread, Report

from .pagination import ProperticaPagination
from .permissions import IsAgencyAccount, IsOwnerOrReadOnly
from .serializers import (
    AccountSerializer,
    ContactMessageSerializer,
    FavoriteSerializer,
    ListingCreateUpdateSerializer,
    ListingDetailSerializer,
    ListingListSerializer,
    ListingStatusSerializer,
    LoginSerializer,
    MessageSerializer,
    MessageThreadSerializer,
    PublicAccountSerializer,
    RegisterSerializer,
    ReportSerializer,
    AgencyInviteSerializer,
)


def _token_for(user):
    token, _ = Token.objects.get_or_create(user=user)
    return token.key


# ── Auth ──────────────────────────────────────────────────────────────

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        token = _token_for(user)
        data = AccountSerializer(user).data
        data["token"] = token
        return Response(data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.validated_data["user"]
        login(request, user)
        token = _token_for(user)
        data = AccountSerializer(user).data
        data["token"] = token
        return Response(data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Accounts ──────────────────────────────────────────────────────────

class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AccountSerializer

    def get_object(self):
        return self.request.user


class PublicAccountView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PublicAccountSerializer
    lookup_field = "username"
    queryset = Account.objects.filter(status="active")


class AgencyInviteView(APIView):
    permission_classes = [IsAuthenticated, IsAgencyAccount]

    def post(self, request):
        ser = AgencyInviteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower()
        agent = Account.objects.filter(
            email=email, account_type=AccountType.AGENT
        ).first()
        if not agent:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Agent account not found for this email."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        link, created = AgencyAgent.objects.get_or_create(
            agency=request.user,
            agent=agent,
            defaults={"status": AgencyAgent.Status.INVITED},
        )
        if not created and link.status == AgencyAgent.Status.ACTIVE:
            return Response(
                {"error": {"code": "CONFLICT", "message": "Agent already linked."}},
                status=status.HTTP_409_CONFLICT,
            )
        link.status = AgencyAgent.Status.INVITED
        link.save(update_fields=["status"])
        return Response(
            {"id": str(link.id), "agent_id": str(agent.id), "status": link.status},
            status=status.HTTP_201_CREATED,
        )


class AgencyRemoveAgentView(APIView):
    permission_classes = [IsAuthenticated, IsAgencyAccount]

    def post(self, request, agent_id):
        link = get_object_or_404(
            AgencyAgent, agency=request.user, agent_id=agent_id
        )
        link.status = AgencyAgent.Status.REMOVED
        link.save(update_fields=["status"])
        agent = link.agent
        if agent.agency_id == request.user.id:
            agent.agency = None
            agent.save(update_fields=["agency"])
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Listings ──────────────────────────────────────────────────────────

class ListingListCreateView(generics.ListCreateAPIView):
    pagination_class = ProperticaPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ListingCreateUpdateSerializer
        return ListingListSerializer

    def get_queryset(self):
        qs = (
            Listing.objects.select_related("category", "owner")
            .prefetch_related("media")
        )
        owner = self.request.query_params.get("owner")
        status_param = self.request.query_params.get("status")

        if owner == "me" and self.request.user.is_authenticated:
            qs = qs.filter(owner=self.request.user)
            if status_param:
                qs = qs.filter(status=status_param)
            return qs.order_by("-updated_at")

        # Public list: active only
        return qs.filter(status=ListingStatus.ACTIVE).order_by("-published_at")

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        listing = ser.save()
        return Response(
            ListingDetailSerializer(listing, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Listing.objects.select_related("category", "owner").prefetch_related("media")
    lookup_field = "pk"

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH", "DELETE"):
            return [IsAuthenticated(), IsOwnerOrReadOnly()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return ListingCreateUpdateSerializer
        return ListingDetailSerializer

    def perform_destroy(self, instance):
        instance.status = ListingStatus.REMOVED
        instance.save(update_fields=["status", "updated_at"])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.owner_id != request.user.id:
            return Response(status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListingPublishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, owner=request.user)
        try:
            listing.publish()
        except Exception as exc:
            return Response(
                {"error": {"code": "INVALID_STATE", "message": str(exc)}},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(ListingDetailSerializer(listing).data)


class ListingStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        listing = get_object_or_404(Listing, pk=pk, owner=request.user)
        ser = ListingStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        new_status = ser.validated_data["status"]

        # Going to ACTIVE must go through publish() so entitlement checks run.
        if new_status == ListingStatus.ACTIVE:
            try:
                listing.publish()
            except Exception as exc:
                return Response(
                    {"error": {"code": "QUOTA_OR_STATE", "message": str(exc)}},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
        else:
            listing.status = new_status
            listing.save(update_fields=["status", "updated_at"])

        return Response(ListingDetailSerializer(listing).data)


# ── Search ────────────────────────────────────────────────────────────

class SearchListingsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ListingListSerializer
    pagination_class = ProperticaPagination

    def get_queryset(self):
        qs = (
            Listing.objects.filter(status=ListingStatus.ACTIVE)
            .select_related("category", "owner")
            .prefetch_related("media")
        )
        p = self.request.query_params
        q = (p.get("q") or "").strip()
        category = (p.get("category") or "").strip()
        parent_group = (p.get("parent_group") or "").strip()
        city = (p.get("city") or "").strip()
        region = (p.get("region") or "").strip()
        country = (p.get("country") or "").strip()
        price_min = p.get("price_min")
        price_max = p.get("price_max")
        area_min = p.get("area_min")
        area_max = p.get("area_max")
        sort = p.get("sort") or "newest"

        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(city__icontains=q)
            )
        if category:
            qs = qs.filter(category__code=category)
        if parent_group:
            qs = qs.filter(category__parent_group=parent_group)
        if city:
            qs = qs.filter(city__icontains=city)
        if region:
            qs = qs.filter(region__icontains=region)
        if country:
            qs = qs.filter(country__icontains=country)
        if price_min:
            try:
                qs = qs.filter(price__gte=float(price_min))
            except ValueError:
                pass
        if price_max:
            try:
                qs = qs.filter(price__lte=float(price_max))
            except ValueError:
                pass
        if area_min:
            try:
                qs = qs.filter(area_value__gte=float(area_min))
            except ValueError:
                pass
        if area_max:
            try:
                qs = qs.filter(area_value__lte=float(area_max))
            except ValueError:
                pass

        if sort == "price_asc":
            qs = qs.order_by("price")
        elif sort == "price_desc":
            qs = qs.order_by("-price")
        elif sort == "area_asc":
            qs = qs.order_by("area_value")
        elif sort == "area_desc":
            qs = qs.order_by("-area_value")
        else:
            qs = qs.order_by("-published_at")
        return qs


# ── Favorites ─────────────────────────────────────────────────────────

class FavoriteListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteSerializer
    pagination_class = ProperticaPagination

    def get_queryset(self):
        return (
            Favorite.objects.filter(account=self.request.user)
            .select_related("listing", "listing__category", "listing__owner")
            .prefetch_related("listing__media")
            .order_by("-created_at")
        )


class FavoriteDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, listing_id):
        deleted, _ = Favorite.objects.filter(
            account=request.user, listing_id=listing_id
        ).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Messaging ─────────────────────────────────────────────────────────

class ContactSellerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, listing_id):
        listing = get_object_or_404(
            Listing,
            pk=listing_id,
            status__in=[ListingStatus.ACTIVE, ListingStatus.UNDER_OFFER],
        )
        if listing.owner_id == request.user.id:
            return Response(
                {"error": {"code": "FORBIDDEN", "message": "Cannot message yourself."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        ser = ContactMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        thread, _ = MessageThread.objects.get_or_create(
            listing=listing,
            buyer=request.user,
            defaults={"seller": listing.owner},
        )
        msg = Message.objects.create(
            thread=thread,
            sender=request.user,
            body=ser.validated_data["body"],
        )
        return Response(
            {
                "thread_id": str(thread.id),
                "message": MessageSerializer(msg).data,
            },
            status=status.HTTP_201_CREATED,
        )


class ThreadListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MessageThreadSerializer
    pagination_class = ProperticaPagination

    def get_queryset(self):
        user = self.request.user
        return (
            MessageThread.objects.filter(Q(buyer=user) | Q(seller=user))
            .select_related("listing", "buyer", "seller")
            .order_by("-created_at")
        )


class ThreadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_thread(self, request, thread_id):
        thread = get_object_or_404(
            MessageThread.objects.select_related("listing", "buyer", "seller"),
            pk=thread_id,
        )
        if request.user.id not in (thread.buyer_id, thread.seller_id):
            return None
        return thread

    def get(self, request, thread_id):
        thread = self._get_thread(request, thread_id)
        if not thread:
            return Response(status=status.HTTP_404_NOT_FOUND)
        Message.objects.filter(thread=thread, read_at__isnull=True).exclude(
            sender=request.user
        ).update(read_at=timezone.now())
        msgs = thread.messages.select_related("sender").order_by("created_at")
        return Response(
            {
                "thread": MessageThreadSerializer(thread).data,
                "messages": MessageSerializer(msgs, many=True).data,
            }
        )

    def post(self, request, thread_id):
        thread = self._get_thread(request, thread_id)
        if not thread:
            return Response(status=status.HTTP_404_NOT_FOUND)
        body = (request.data.get("body") or "").strip()
        if not body:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "body required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        msg = Message.objects.create(
            thread=thread, sender=request.user, body=body[:2000]
        )
        return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)


# ── Reports ───────────────────────────────────────────────────────────

class ReportCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        listing_id = request.data.get("listing_id")
        reason = (request.data.get("reason") or "other")[:60]
        details = request.data.get("details") or ""
        listing = None
        if listing_id:
            listing = get_object_or_404(Listing, pk=listing_id)
        report = Report.objects.create(
            listing=listing,
            reporter=request.user,
            reason=reason,
            details=details,
        )
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)


# ── Categories (helper) ───────────────────────────────────────────────

class CategoryListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cats = PropertyCategory.objects.all().order_by("parent_group", "label")
        data = [
            {
                "id": str(c.id),
                "code": c.code,
                "label": c.label,
                "parent_group": c.parent_group,
            }
            for c in cats
        ]
        return Response({"data": data})
