from rest_framework import serializers

from .models import Category, Product, StockMovement, Supplier


class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "description", "is_active", "products_count", "created_at")
        read_only_fields = ("id", "created_at")


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = (
            "id",
            "name",
            "tax_id",
            "contact_name",
            "email",
            "phone",
            "address",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "sku",
            "barcode",
            "name",
            "description",
            "category",
            "category_name",
            "supplier",
            "supplier_name",
            "cost_price",
            "sale_price",
            "stock",
            "min_stock",
            "is_low_stock",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "stock", "created_at", "updated_at")

    def validate(self, attrs):
        cost = attrs.get("cost_price", getattr(self.instance, "cost_price", None))
        sale = attrs.get("sale_price", getattr(self.instance, "sale_price", None))
        if cost is not None and sale is not None and sale < cost:
            raise serializers.ValidationError(
                {"sale_price": "El precio de venta no puede ser menor al costo."}
            )
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    movement_type_display = serializers.CharField(source="get_movement_type_display", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = StockMovement
        fields = (
            "id",
            "product",
            "product_name",
            "product_sku",
            "movement_type",
            "movement_type_display",
            "quantity",
            "stock_before",
            "stock_after",
            "note",
            "sale",
            "user",
            "user_name",
            "created_at",
        )
        read_only_fields = fields


class StockMovementCreateSerializer(serializers.Serializer):
    MANUAL_TYPES = (
        StockMovement.MovementType.IN,
        StockMovement.MovementType.OUT,
        StockMovement.MovementType.ADJUSTMENT,
    )

    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.filter(is_active=True))
    movement_type = serializers.ChoiceField(
        choices=[(t.value, t.label) for t in MANUAL_TYPES],
        help_text="in = entrada, out = salida, adjustment = stock contado físicamente.",
    )
    quantity = serializers.IntegerField(min_value=0)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["movement_type"] != StockMovement.MovementType.ADJUSTMENT and attrs["quantity"] < 1:
            raise serializers.ValidationError({"quantity": "Debe ser mayor a cero."})
        return attrs
