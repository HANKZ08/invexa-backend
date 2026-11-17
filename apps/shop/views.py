from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.permissions import IsAdmin

from .serializers import ShopAdminSerializer, ShopPublicSerializer
from .services import get_settings, update_settings


@extend_schema(tags=["Tienda"])
class ShopSettingsView(APIView):
    """Configuración de la tienda. GET es público (nombre y logos); el administrador ve y cambia todo."""

    parser_classes = (JSONParser, MultiPartParser, FormParser)

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAdmin()]

    @extend_schema(summary="Ver configuración de la tienda", responses=ShopPublicSerializer)
    def get(self, request):
        shop = get_settings()
        user = request.user
        if user.is_authenticated and user.is_admin:
            return Response(ShopAdminSerializer(shop, context={"request": request}).data)
        return Response(ShopPublicSerializer(shop, context={"request": request}).data)

    @extend_schema(
        summary="Cambiar configuración de la tienda (solo administrador)",
        request=ShopAdminSerializer,
        responses=ShopAdminSerializer,
    )
    def patch(self, request):
        shop = get_settings()
        serializer = ShopAdminSerializer(shop, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        update_settings(shop, serializer.validated_data)
        return Response(ShopAdminSerializer(shop, context={"request": request}).data)
