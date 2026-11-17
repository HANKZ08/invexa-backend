from django.urls import path

from .views import DashboardView, InventoryExportView, LowStockView, SalesExportView

urlpatterns = [
    path("reports/dashboard/", DashboardView.as_view(), name="report-dashboard"),
    path("reports/low-stock/", LowStockView.as_view(), name="report-low-stock"),
    path("reports/sales/export/", SalesExportView.as_view(), name="report-sales-export"),
    path("reports/inventory/export/", InventoryExportView.as_view(), name="report-inventory-export"),
]
