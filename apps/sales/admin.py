from django.contrib import admin

from .models import Customer, Sale, SaleItem


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "document_id", "email", "phone")
    search_fields = ("name", "document_id", "email")


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "product_name", "quantity", "unit_price", "line_total")
    fields = readonly_fields


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("number", "created_at", "cashier", "customer", "payment_method", "total", "status")
    list_filter = ("status", "payment_method", "created_at")
    list_select_related = ("cashier", "customer")
    search_fields = ("number", "customer__name")
    inlines = (SaleItemInline,)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False
