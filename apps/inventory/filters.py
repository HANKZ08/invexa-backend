import django_filters
from django.db.models import F

from .models import Product, StockMovement


class ProductFilter(django_filters.FilterSet):
    low_stock = django_filters.BooleanFilter(method="filter_low_stock", label="Stock bajo")
    min_price = django_filters.NumberFilter(field_name="sale_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="sale_price", lookup_expr="lte")

    class Meta:
        model = Product
        fields = ("category", "supplier", "is_active", "barcode")

    def filter_low_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__lte=F("min_stock"))
        return queryset.filter(stock__gt=F("min_stock"))


class StockMovementFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = StockMovement
        fields = ("product", "movement_type", "user", "sale")
