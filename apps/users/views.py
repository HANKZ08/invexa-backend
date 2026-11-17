from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .permissions import IsAdmin
from .serializers import (
    AvatarSerializer,
    ChangePasswordSerializer,
    MeSerializer,
    ResendCodeSerializer,
    UserSerializer,
    VerifyEmailSerializer,
)
from .services import (
    request_password_reset,
    resend_verification_code,
    reset_password,
    send_password_changed_notice,
    send_verification_code,
    verify_email,
)

CODE_SENT = {"detail": "Si la cuenta está pendiente de verificación, enviamos un código a ese correo."}


@extend_schema_view(
    list=extend_schema(summary="Listar usuarios"),
    create=extend_schema(summary="Crear usuario"),
    retrieve=extend_schema(summary="Detalle de usuario"),
    update=extend_schema(summary="Actualizar usuario"),
    partial_update=extend_schema(summary="Actualizar parcialmente un usuario"),
    destroy=extend_schema(summary="Desactivar usuario (borrado lógico)"),
)
@extend_schema(tags=["Usuarios"])
class UserViewSet(viewsets.ModelViewSet):
    """Gestión de usuarios (solo administradores)."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAdmin,)
    filterset_fields = ("role", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering_fields = ("username", "date_joined")

    @extend_schema(summary="Reenviar código de verificación al usuario", request=None, responses={204: None})
    @action(detail=True, methods=["post"], url_path="resend-verification")
    def resend_verification(self, request, pk=None):
        user = self.get_object()
        if user.email_verified_at:
            raise ValidationError("El correo de este usuario ya está verificado.")
        send_verification_code(user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        # Borrado lógico: conserva el historial de ventas del usuario.
        instance.is_active = False
        instance.save(update_fields=["is_active"])


@extend_schema(tags=["Autenticación"], summary="Iniciar sesión (obtener access y refresh token)")
class LoginView(TokenObtainPairView):
    """Login JWT con límite de intentos por IP (LOGIN_THROTTLE_RATE)."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"


@extend_schema(
    tags=["Autenticación"],
    summary="Verificar correo y activar la cuenta",
    responses={200: MeSerializer, 400: OpenApiResponse(description="Código inválido o vencido.")},
)
class VerifyEmailView(generics.GenericAPIView):
    """Recibe el código de 6 dígitos y la contraseña nueva; activa la cuenta."""

    serializer_class = VerifyEmailSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "email_verification"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = verify_email(**serializer.validated_data)
        return Response(MeSerializer(user).data)


@extend_schema(
    tags=["Autenticación"],
    summary="Reenviar código de verificación",
    responses={200: OpenApiResponse(description="Respuesta genérica: no revela si el correo existe.")},
)
@extend_schema(
    tags=["Autenticación"],
    summary="Pedir código para recuperar la contraseña",
    responses={200: OpenApiResponse(description="Respuesta genérica: no revela si el correo existe.")},
)
class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = ResendCodeSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "email_verification"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(serializer.validated_data["email"])
        return Response(CODE_SENT)


@extend_schema(
    tags=["Autenticación"],
    summary="Cambiar la contraseña con el código recibido",
    responses={204: None, 400: OpenApiResponse(description="Código inválido o vencido.")},
)
class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = VerifyEmailSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "email_verification"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reset_password(**serializer.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResendCodeView(generics.GenericAPIView):
    serializer_class = ResendCodeSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "email_verification"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resend_verification_code(serializer.validated_data["email"])
        return Response(CODE_SENT)


@extend_schema(tags=["Autenticación"])
@extend_schema(tags=["Autenticación"], request=AvatarSerializer, responses={200: MeSerializer})
class AvatarView(generics.GenericAPIView):
    """Sube o quita la foto de perfil del usuario autenticado."""

    serializer_class = AvatarSerializer
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if user.avatar:
            user.avatar.delete(save=False)
        user.avatar.save(
            serializer.validated_data["avatar"].name, serializer.validated_data["avatar"], save=False
        )
        user.save(update_fields=["avatar"])
        return Response(MeSerializer(user, context={"request": request}).data)

    def delete(self, request):
        user = request.user
        if user.avatar:
            user.avatar.delete(save=False)
        user.avatar = None
        user.save(update_fields=["avatar"])
        return Response(MeSerializer(user, context={"request": request}).data)


class MeView(generics.RetrieveUpdateAPIView):
    """Perfil del usuario autenticado."""

    serializer_class = MeSerializer
    http_method_names = ("get", "patch")

    def get_object(self):
        return self.request.user


@extend_schema(tags=["Autenticación"], responses={204: None})
class ChangePasswordView(generics.GenericAPIView):
    """Cambia la contraseña del usuario autenticado."""

    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        send_password_changed_notice(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
