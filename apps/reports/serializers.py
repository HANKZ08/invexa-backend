from rest_framework import serializers

from .services import default_range


class DateRangeSerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs):
        default_from, default_to = default_range()
        attrs.setdefault("date_from", default_from)
        attrs.setdefault("date_to", default_to)
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError({"date_from": "Debe ser anterior o igual a date_to."})
        return attrs


class SummarySerializer(serializers.Serializer):
    sales_count = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=16, decimal_places=2)
    tax = serializers.DecimalField(max_digits=16, decimal_places=2)
    discounts = serializers.DecimalField(max_digits=16, decimal_places=2)
    units_sold = serializers.IntegerField()
    gross_profit = serializers.DecimalField(max_digits=16, decimal_places=2)
    average_ticket = serializers.DecimalField(max_digits=16, decimal_places=2)
    cancelled_count = serializers.IntegerField()


class InventorySummarySerializer(serializers.Serializer):
    products_count = serializers.IntegerField()
    inventory_cost = serializers.DecimalField(max_digits=18, decimal_places=2)
    low_stock_count = serializers.IntegerField()


class SalesByDaySerializer(serializers.Serializer):
    day = serializers.DateField()
    sales_count = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=16, decimal_places=2)


class SalesByPaymentSerializer(serializers.Serializer):
    payment_method = serializers.CharField()
    payment_method_display = serializers.CharField()
    sales_count = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=16, decimal_places=2)


class TopProductSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_sku = serializers.CharField()
    product_name = serializers.CharField()
    units_sold = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=16, decimal_places=2)


class DashboardSerializer(serializers.Serializer):
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    summary = SummarySerializer()
    inventory = InventorySummarySerializer()
    sales_by_day = SalesByDaySerializer(many=True)
    sales_by_payment_method = SalesByPaymentSerializer(many=True)
    top_products = TopProductSerializer(many=True)
