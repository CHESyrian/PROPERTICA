from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.AccountLoginView.as_view(), name="login"),
    path("logout/", views.AccountLogoutView.as_view(), name="logout"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("export/", views.DataExportView.as_view(), name="data_export"),
    path("delete/", views.AccountDeleteView.as_view(), name="account_delete"),
    path(
        "verify-email/<path:token>/",
        views.VerifyEmailView.as_view(),
        name="verify_email",
    ),
    # Fallback for clients that strip path tokens — ?token=
    path(
        "verify-email/",
        views.VerifyEmailView.as_view(),
        name="verify_email_qs",
    ),
    path(
        "resend-verification/",
        views.ResendVerificationView.as_view(),
        name="resend_verification",
    ),
    path(
        "phone/request-code/",
        views.RequestPhoneCodeView.as_view(),
        name="request_phone_code",
    ),
    path(
        "phone/confirm/",
        views.ConfirmPhoneCodeView.as_view(),
        name="confirm_phone_code",
    ),
    path("agency/invite/", views.AgencyInviteView.as_view(), name="agency_invite"),
    path("a/<str:username>/", views.AgencyPublicView.as_view(), name="agency_public"),
    path("u/<str:username>/", views.PublicProfileView.as_view(), name="public_profile"),
    path(
        "agency/agents/<uuid:link_id>/remove/",
        views.AgencyRemoveAgentView.as_view(),
        name="agency_remove",
    ),
    path(
        "agency/invites/<uuid:link_id>/accept/",
        views.AgencyAcceptInviteView.as_view(),
        name="agency_accept",
    ),
    path(
        "agency/invites/<uuid:link_id>/decline/",
        views.AgencyDeclineInviteView.as_view(),
        name="agency_decline",
    ),
]
