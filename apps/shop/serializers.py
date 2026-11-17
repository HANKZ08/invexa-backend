from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import ShopSettings


# Vista pública de la tienda: nombre y logos, sin datos fiscales.
class ShopPublicSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    icon_url = serializers.SerializerMethodField()

    class Meta:
        model = ShopSettings
        fields = ("name", "logo_url", "icon_url")

    def _absolute(self, field_file):
        if not field_file:
            return None
        request = self.context.get("request")
        url = field_file.url
        return request.build_absolute_uri(url) if request else url

    @extend_schema_field(OpenApiTypes.URI)
    def get_logo_url(self, obj):
        return self._absolute(obj.logo)

    @extend_schema_field(OpenApiTypes.URI)
    def get_icon_url(self, obj):
        return self._absolute(obj.icon)


# Configuración completa para el administrador: lectura y cambios.
class ShopAdminSerializer(ShopPublicSerializer):
    logo = serializers.FileField(required=False, write_only=True, help_text="Logo completo nuevo.")
    icon = serializers.FileField(required=False, write_only=True, help_text="Ícono nuevo.")
    remove_logo = serializers.BooleanField(
        required=False, default=False, write_only=True, help_text="Quita el logo actual."
    )
    remove_icon = serializers.BooleanField(
        required=False, default=False, write_only=True, help_text="Quita el ícono actual."
    )

    class Meta(ShopPublicSerializer.Meta):
        fields = (
            "name",
            "legal_name",
            "tax_id",
            "address",
            "phone",
            "tax_rate",
            "currency_symbol",
            "logo_url",
            "icon_url",
            "logo",
            "icon",
            "remove_logo",
            "remove_icon",
        )

    def validate_tax_rate(self, value):
        if not 0 <= value < 1:
            raise serializers.ValidationError("El IGV debe estar entre 0 y 0.99 (por ejemplo 0.18 = 18 %).")
        return value

    def validate_tax_id(self, value):
        if value and (not value.isdigit() or len(value) != 11):
            raise serializers.ValidationError("El RUC debe tener 11 dígitos.")
        return value
