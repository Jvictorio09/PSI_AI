from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("workshop/", views.workshop_view, name="workshop"),

    path("chat-ai/", views.chat_ai, name="chat_ai"),
    path("generate-vision/", views.generate_vision, name="generate_vision"),
    path("save-onboarding/", views.save_onboarding, name="save_onboarding"),

    path("password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    path("api/profile/", views.profile_get, name="profile_get"),
    path("api/profile/save/", views.profile_save, name="profile_save"),
    path("", views.workshop_view, name="home"),
]
