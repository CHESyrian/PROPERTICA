"""PROPERTICA REST API v1 routes."""

from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    # Auth
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    # Accounts — specific paths before username catch-all
    path("accounts/me/", views.MeView.as_view(), name="accounts-me"),
    path("accounts/agency/invite-agent/", views.AgencyInviteView.as_view(), name="agency-invite"),
    path(
        "accounts/agency/agents/<uuid:agent_id>/remove/",
        views.AgencyRemoveAgentView.as_view(),
        name="agency-remove",
    ),
    path("accounts/<str:username>/", views.PublicAccountView.as_view(), name="accounts-public"),
    # Listings
    path("listings/", views.ListingListCreateView.as_view(), name="listings"),
    path("listings/<uuid:pk>/", views.ListingDetailView.as_view(), name="listing-detail"),
    path("listings/<uuid:pk>/publish/", views.ListingPublishView.as_view(), name="listing-publish"),
    path("listings/<uuid:pk>/status/", views.ListingStatusView.as_view(), name="listing-status"),
    path(
        "listings/<uuid:listing_id>/messages/",
        views.ContactSellerView.as_view(),
        name="listing-message",
    ),
    # Search
    path("search/listings/", views.SearchListingsView.as_view(), name="search-listings"),
    path("categories/", views.CategoryListView.as_view(), name="categories"),
    # Favorites
    path("favorites/", views.FavoriteListCreateView.as_view(), name="favorites"),
    path("favorites/<uuid:listing_id>/", views.FavoriteDeleteView.as_view(), name="favorite-delete"),
    # Messaging
    path("messages/threads/", views.ThreadListView.as_view(), name="threads"),
    path("messages/threads/<uuid:thread_id>/", views.ThreadDetailView.as_view(), name="thread-detail"),
    # Reports
    path("reports/", views.ReportCreateView.as_view(), name="reports"),
]
