from decimal import Decimal

import django_filters
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.models import User
from apps.users.permissions import IsAdmin, RoleBasedPermission

from .invoice import build_invoice_pdf
from .models import Customer, Sale
from .serializers import (
    CustomerSerializer,
    DebtPaymentInputSerializer,
    SaleCancelSerializer,
    SaleCreateSerializer,
    SaleListSerializer,
    SaleSerializer,
)
from .services import cancel_sale, create_sale, pay_debt

CASHIER = (User.Role.CASHIER,)


class SaleFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = Sale
        fields = ("status", "payment_method", "cashier", "customer")


@extend_schema(tags=["Ventas · Clientes"])
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()

    def get_queryset(self):
        """Cada cliente lleva su deuda: suma de saldos de sus ventas pendientes."""
        qs = Customer.objects.annotate(
            debt=Coalesce(Sum("sales__balance", filter=Q(sales__status=Sale.Status.PENDING)), Decimal("0")),
            pending_sales=Count("sales", filter=Q(sales__status=Sale.Status.PENDING), distinct=True),
        )
        if self.request.query_params.get("has_debt") in ("1", "true", "True"):
            qs = qs.filter(debt__gt=0).order_by("-debt")
        return qs

    serializer_class = CustomerSerializer
    permission_classes = (RoleBasedPermission,)
    read_roles = CASHIER
    write_roles = CASHIER
    search_fields = ("name", "document_id", "email")
    ordering_fields = ("name", "created_at", "debt")


@extend_schema(tags=["Ventas"])
class SaleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """Ventas del punto de venta.

    Los cajeros solo ven sus propias ventas; los administradores ven todas.
    """

    permission_classes = (RoleBasedPermission,)
    read_roles = CASHIER
    write_roles = CASHIER
    filterset_class = SaleFilter
    search_fields = ("number", "customer__name", "customer__document_id")
    ordering_fields = ("created_at", "total")

    def get_queryset(self):
        qs = Sale.objects.select_related("cashier", "customer")
        if self.action == "list":
            qs = qs.annotate(items_count=Count("items")).order_by("-created_at", "-id")
        else:
            qs = qs.prefetch_related("items")
        if getattr(self, "swagger_fake_view", False):  # generación del esquema OpenAPI
            return qs
        user = self.request.user
        if not user.is_admin:
            qs = qs.filter(cashier=user)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return SaleListSerializer
        return SaleSerializer

    def get_permissions(self):
        if self.action == "cancel":
            return [IsAdmin()]
        return super().get_permissions()

    @extend_schema(
        summary="Registrar una venta",
        request=SaleCreateSerializer,
        responses={201: SaleSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = create_sale(cashier=request.user, **serializer.validated_data)
        sale = self.get_queryset().get(pk=sale.pk)
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Anular una venta (solo administradores)",
        request=SaleCancelSerializer,
        responses={200: SaleSerializer},
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        serializer = SaleCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = cancel_sale(sale=self.get_object(), user=request.user, **serializer.validated_data)
        return Response(SaleSerializer(self.get_queryset().get(pk=sale.pk)).data)

    @extend_schema(
        summary="Descargar factura en PDF",
        responses={(200, "application/pdf"): OpenApiResponse(OpenApiTypes.BINARY)},
    )
    @extend_schema(
        summary="Registrar abonos a una venta pendiente",
        request=DebtPaymentInputSerializer,
        responses={200: SaleSerializer},
    )
    @action(detail=True, methods=["post"], url_path="pay-debt", url_name="pay-debt")
    def pay_debt_action(self, request, pk=None):
        serializer = DebtPaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = pay_debt(
            sale=self.get_object(), user=request.user, payments=serializer.validated_data["payments"]
        )
        return Response(SaleSerializer(self.get_queryset().get(pk=sale.pk)).data)

    @action(detail=True, methods=["get"])
    def invoice(self, request, pk=None):
        sale = self.get_object()
        response = HttpResponse(build_invoice_pdf(sale), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="factura-{sale.number}.pdf"'
        return response
