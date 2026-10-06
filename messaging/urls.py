from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.InboxView.as_view(), name="inbox"),
    path("thread/<uuid:thread_id>/", views.ThreadDetailView.as_view(), name="thread"),
    path(
        "contact/<uuid:listing_id>/",
        views.ContactSellerView.as_view(),
        name="contact",
    ),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path(
        "notifications/mark-read/",
        views.NotificationMarkReadView.as_view(),
        name="notifications_mark_all",
    ),
    path(
        "notifications/<uuid:pk>/mark-read/",
        views.NotificationMarkReadView.as_view(),
        name="notification_mark_read",
    ),
]
