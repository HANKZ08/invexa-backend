from decimal import Decimal

from rest_framework import serializers

from apps.inventory.models import Product

from .models import Customer, DebtPayment, Sale, SaleItem, SalePayment


class CustomerSerializer(serializers.ModelSerializer):
    debt = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, default=0)
    pending_sales = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Customer
        fields = ("id", "name", "document_id", "email", "phone", "created_at", "debt", "pending_sales")
        read_only_fields = ("id", "created_at", "debt", "pending_sales")


class SalePaymentSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source="get_method_display", read_only=True)

    class Meta:
        model = SalePayment
        fields = ("id", "method", "method_display", "amount", "reference")
        read_only_fields = fields


class DebtPaymentSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source="get_method_display", read_only=True)

    class Meta:
        model = DebtPayment
        fields = ("id", "method", "method_display", "amount", "reference", "created_at")
        read_only_fields = fields


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = ("id", "product", "product_name", "product_sku", "quantity", "unit_price", "line_total")
        read_only_fields = fields


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    payments = SalePaymentSerializer(many=True, read_only=True)
    debt_payments = DebtPaymentSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(source="cashier.username", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True, default=None)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)

    class Meta:
        model = Sale
        fields = (
            "id",
            "number",
            "status",
            "status_display",
            "customer",
            "customer_name",
            "cashier",
            "cashier_name",
            "payment_method",
            "payment_method_display",
            "subtotal",
            "discount",
            "tax",
            "total",
            "amount_paid",
            "change",
            "notes",
            "items",
            "payments",
            "balance",
            "debt_payments",
            "created_at",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
        )
        read_only_fields = fields


class SaleListSerializer(SaleSerializer):
    items_count = serializers.IntegerField(read_only=True)

    class Meta(SaleSerializer.Meta):
        fields = tuple(f for f in SaleSerializer.Meta.fields if f != "items") + ("items_count",)
        read_only_fields = fields


class SaleItemInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    quantity = serializers.IntegerField(min_value=1)


class PaymentInputSerializer(serializers.Serializer):
    method = serializers.ChoiceField(
        choices=[c for c in Sale.PaymentMethod.choices if c[0] != Sale.PaymentMethod.MIXED]
    )
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    reference = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")


class SaleCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), required=False, allow_null=True
    )
    payments = PaymentInputSerializer(many=True, allow_empty=False)
    discount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=Decimal("0"), min_value=Decimal("0")
    )
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    items = SaleItemInputSerializer(many=True, allow_empty=False)


class DebtPaymentInputSerializer(serializers.Serializer):
    payments = PaymentInputSerializer(many=True, allow_empty=False)


class SaleCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
