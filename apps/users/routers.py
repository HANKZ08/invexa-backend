from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AvatarView,
    ChangePasswordView,
    LoginView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendCodeView,
    UserViewSet,
    VerifyEmailView,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

auth_tag = extend_schema(tags=["Autenticación"])

urlpatterns = [
    path("auth/token/", LoginView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", auth_tag(TokenRefreshView).as_view(), name="token_refresh"),
    path("auth/verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path("auth/resend-code/", ResendCodeView.as_view(), name="resend_code"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("auth/password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/me/avatar/", AvatarView.as_view(), name="me_avatar"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change_password"),
    *router.urls,
]
