from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.models import Product
from apps.inventory.serializers import ProductSerializer
from apps.users.models import User
from apps.users.permissions import IsAdmin, RoleBasedPermission

from .exports import inventory_workbook, sales_workbook
from .serializers import DashboardSerializer, DateRangeSerializer
from .services import dashboard

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLSX_RESPONSE = {(200, XLSX): OpenApiResponse(OpenApiTypes.BINARY)}


def _xlsx_response(content: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _date_range(request):
    serializer = DateRangeSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data["date_from"], serializer.validated_data["date_to"]


@extend_schema(tags=["Reportes"])
class DashboardView(APIView):
    """KPIs del negocio. Por defecto, los últimos 30 días."""

    permission_classes = (IsAdmin,)

    @extend_schema(
        summary="Dashboard de ventas e inventario",
        parameters=[DateRangeSerializer],
        responses=DashboardSerializer,
    )
    def get(self, request):
        date_from, date_to = _date_range(request)
        return Response(DashboardSerializer(dashboard(date_from, date_to)).data)


@extend_schema(tags=["Reportes"])
class LowStockView(APIView):
    permission_classes = (RoleBasedPermission,)
    read_roles = (User.Role.WAREHOUSE,)

    @extend_schema(summary="Productos con stock bajo", responses=ProductSerializer(many=True))
    def get(self, request):
        products = Product.objects.low_stock().select_related("category", "supplier").order_by("stock")
        return Response(ProductSerializer(products, many=True).data)


@extend_schema(tags=["Reportes"])
class SalesExportView(APIView):
    permission_classes = (IsAdmin,)

    @extend_schema(
        summary="Exportar ventas a Excel", parameters=[DateRangeSerializer], responses=XLSX_RESPONSE
    )
    def get(self, request):
        date_from, date_to = _date_range(request)
        return _xlsx_response(sales_workbook(date_from, date_to), f"ventas_{date_from}_{date_to}.xlsx")


@extend_schema(tags=["Reportes"])
class InventoryExportView(APIView):
    permission_classes = (RoleBasedPermission,)
    read_roles = (User.Role.WAREHOUSE,)

    @extend_schema(summary="Exportar inventario a Excel", responses=XLSX_RESPONSE)
    def get(self, request):
        return _xlsx_response(inventory_workbook(), "inventario.xlsx")
