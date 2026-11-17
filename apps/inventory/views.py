from django.db.models import Count, ProtectedError
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.users.models import User
from apps.users.permissions import RoleBasedPermission

from .filters import ProductFilter, StockMovementFilter
from .models import Category, Product, StockMovement, Supplier
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    StockMovementCreateSerializer,
    StockMovementSerializer,
    SupplierSerializer,
)
from .services import register_manual_movement

ALL_ROLES = tuple(User.Role.values)
WAREHOUSE = (User.Role.WAREHOUSE,)


class ProtectedDeleteMixin:
    """Devuelve 400 en vez de 500 si el registro está referenciado."""

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise ValidationError(
                "No se puede eliminar porque tiene registros asociados. Desactívalo en su lugar."
            ) from exc


@extend_schema(tags=["Inventario · Categorías"])
class CategoryViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = (RoleBasedPermission,)
    read_roles = ALL_ROLES
    write_roles = WAREHOUSE
    filterset_fields = ("is_active",)
    search_fields = ("name",)
    ordering_fields = ("name", "created_at")

    def get_queryset(self):
        return Category.objects.annotate(products_count=Count("products"))


@extend_schema(tags=["Inventario · Proveedores"])
class SupplierViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = (RoleBasedPermission,)
    read_roles = WAREHOUSE
    write_roles = WAREHOUSE
    filterset_fields = ("is_active",)
    search_fields = ("name", "tax_id", "contact_name", "email")
    ordering_fields = ("name", "created_at")


@extend_schema(tags=["Inventario · Productos"])
class ProductViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    """Catálogo de productos. Usa ``?search=`` para buscar por nombre, SKU o código de barras."""

    queryset = Product.objects.select_related("category", "supplier")
    serializer_class = ProductSerializer
    permission_classes = (RoleBasedPermission,)
    read_roles = ALL_ROLES
    write_roles = WAREHOUSE
    filterset_class = ProductFilter
    search_fields = ("name", "sku", "barcode")
    ordering_fields = ("name", "sku", "sale_price", "stock", "created_at")


@extend_schema(tags=["Inventario · Movimientos"])
class StockMovementViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Kardex: historial inmutable de entradas, salidas, ajustes y ventas."""

    queryset = StockMovement.objects.select_related("product", "user")
    serializer_class = StockMovementSerializer
    permission_classes = (RoleBasedPermission,)
    read_roles = WAREHOUSE
    write_roles = WAREHOUSE
    filterset_class = StockMovementFilter
    search_fields = ("product__name", "product__sku", "note")
    ordering_fields = ("created_at",)

    @extend_schema(
        summary="Registrar entrada, salida o ajuste de stock",
        request=StockMovementCreateSerializer,
        responses={201: StockMovementSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = StockMovementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        movement = register_manual_movement(user=request.user, **serializer.validated_data)
        return Response(StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED)
