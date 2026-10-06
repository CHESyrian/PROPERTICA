from django.urls import path

from . import views

app_name = "listings"

urlpatterns = [
    path("search/", views.ListingSearchView.as_view(), name="search"),
    path("create/", views.ListingWizardView.as_view(), name="create"),
    path("favorites/", views.FavoritesListView.as_view(), name="favorites"),
    path("bulk-status/", views.ListingBulkStatusView.as_view(), name="bulk_status"),
    path("saved-searches/", views.SavedSearchListView.as_view(), name="saved_searches"),
    path("saved-searches/save/", views.SavedSearchCreateView.as_view(), name="save_search"),
    path(
        "saved-searches/<uuid:pk>/delete/",
        views.SavedSearchDeleteView.as_view(),
        name="saved_search_delete",
    ),
    path(
        "saved-searches/<uuid:pk>/update/",
        views.SavedSearchUpdateView.as_view(),
        name="saved_search_update",
    ),
    path(
        "api/categories/<uuid:category_id>/attributes/",
        views.CategoryAttributesAPI.as_view(),
        name="category_attributes",
    ),
    path("api/geocode/", views.GeocodeAPI.as_view(), name="geocode"),
    path("api/reverse-geocode/", views.ReverseGeocodeAPI.as_view(), name="reverse_geocode"),
    path("<uuid:pk>/", views.ListingDetailView.as_view(), name="detail"),
    path("<uuid:pk>/edit/", views.ListingEditView.as_view(), name="edit"),
    path("<uuid:pk>/publish/", views.ListingPublishView.as_view(), name="publish"),
    path("<uuid:pk>/feature/", views.ListingFeatureView.as_view(), name="feature"),
    path("<uuid:pk>/status/", views.ListingSetStatusView.as_view(), name="set_status"),
    path("<uuid:pk>/favorite/", views.FavoriteToggleView.as_view(), name="favorite"),
    path("<uuid:pk>/phone/", views.PhoneRevealView.as_view(), name="phone_reveal"),
    path("<uuid:pk>/report/", views.ReportListingView.as_view(), name="report"),
]
