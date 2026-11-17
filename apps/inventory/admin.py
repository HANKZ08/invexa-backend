from django.contrib import admin

from .models import Category, Product, StockMovement, Supplier


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "tax_id", "email", "phone", "is_active")
    search_fields = ("name", "tax_id")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "category", "sale_price", "stock", "min_stock", "is_active")
    list_filter = ("category", "is_active")
    list_select_related = ("category",)
    search_fields = ("sku", "name", "barcode")
    readonly_fields = ("stock",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "product", "movement_type", "quantity", "stock_after", "user")
    list_filter = ("movement_type",)
    list_select_related = ("product", "user")
    search_fields = ("product__sku", "product__name")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
