from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import User
from .services import send_verification_code


class UserSerializer(serializers.ModelSerializer):
    """Gestión de usuarios por el administrador.

    Al crear un usuario (o cambiarle el correo) la cuenta queda inactiva y se envía un
    código de 6 dígitos; el dueño del correo la activa y define su contraseña.
    """

    password = serializers.CharField(
        write_only=True,
        required=False,
        style={"input_type": "password"},
        help_text="Solo para restablecer la contraseña de un usuario ya verificado.",
    )
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "role_display",
            "is_active",
            "email_verified_at",
            "password",
            "date_joined",
        )
        read_only_fields = ("id", "email_verified_at", "date_joined")

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if self.instance is None:
            if attrs.get("password"):
                raise serializers.ValidationError(
                    {"password": "La contraseña la define el usuario al verificar su correo."}
                )
            attrs["is_active"] = False
        elif attrs.get("is_active") and not self.instance.email_verified_at:
            email_changed = "email" in attrs and attrs["email"].lower() != self.instance.email.lower()
            if not email_changed:
                raise serializers.ValidationError(
                    {"is_active": "El usuario debe verificar su correo antes de activarse."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User(**validated_data)
        user.set_unusable_password()
        user.save()
        send_verification_code(user)
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        email_changed = (
            "email" in validated_data and validated_data["email"].lower() != instance.email.lower()
        )
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        if email_changed:
            # Un correo nuevo se vuelve a verificar
            instance.email_verified_at = None
            instance.is_active = False
        instance.save()
        if email_changed:
            send_verification_code(instance)
        return instance


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="Correo de la cuenta a activar.")
    code = serializers.RegexField(
        r"^\d{6}$",
        help_text="Código de 6 dígitos recibido por correo.",
        error_messages={"invalid": "El código debe tener 6 dígitos."},
    )
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        help_text="Contraseña nueva de la cuenta.",
    )

    def validate_password(self, value):
        validate_password(value)
        return value


class ResendCodeSerializer(serializers.Serializer):
    email = serializers.EmailField(help_text="Correo de la cuenta pendiente de verificar.")


class MeSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "role_display",
            "avatar_url",
        )
        read_only_fields = ("id", "username", "role", "role_display", "avatar_url")

    @extend_schema_field(OpenApiTypes.URI)
    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None
        request = self.context.get("request")
        url = obj.avatar.url
        return request.build_absolute_uri(url) if request else url


ALLOWED_AVATAR_TYPES = {"image/png": "PNG", "image/jpeg": "JPEG", "image/gif": "GIF"}
MAX_AVATAR_BYTES = 10 * 1024 * 1024


class AvatarSerializer(serializers.Serializer):
    avatar = serializers.ImageField(help_text="PNG, JPG o GIF de máximo 10 MB.")

    def validate_avatar(self, value):
        if value.size > MAX_AVATAR_BYTES:
            raise serializers.ValidationError("La foto supera los 10 MB.")
        if value.content_type not in ALLOWED_AVATAR_TYPES:
            raise serializers.ValidationError("Solo se aceptan fotos PNG, JPG o GIF.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("La contraseña actual no es correcta.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value
