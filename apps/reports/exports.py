"""Exportación de reportes a Excel con openpyxl."""

from datetime import date
from io import BytesIO

from django.conf import settings
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from apps.inventory.models import Product

from .services import completed_sales

HEADER_FILL = PatternFill("solid", fgColor="1F2937")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def _write_sheet(ws, headers: list[str], rows) -> None:
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    for row in rows:
        ws.append(row)
    for idx, header in enumerate(headers, start=1):
        width = max([len(str(header))] + [len(str(c.value or "")) for c in ws[get_column_letter(idx)]])
        ws.column_dimensions[get_column_letter(idx)].width = min(width + 2, 50)
    ws.freeze_panes = "A2"


def _to_bytes(wb: Workbook) -> bytes:
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def sales_workbook(date_from: date, date_to: date) -> bytes:
    sales = completed_sales(date_from, date_to).select_related("cashier", "customer").order_by("created_at")
    wb = Workbook()
    ws = wb.active
    ws.title = "Ventas"
    _write_sheet(
        ws,
        [
            "Número",
            "Fecha",
            "Cajero",
            "Cliente",
            "Método de pago",
            "Subtotal",
            "Descuento",
            settings.INVEXA_TAX_LABEL,
            "Total",
        ],
        (
            [
                s.number,
                timezone.localtime(s.created_at).strftime("%Y-%m-%d %H:%M"),
                s.cashier.username,
                s.customer.name if s.customer else "Consumidor final",
                s.get_payment_method_display(),
                float(s.subtotal),
                float(s.discount),
                float(s.tax),
                float(s.total),
            ]
            for s in sales
        ),
    )
    return _to_bytes(wb)


def inventory_workbook() -> bytes:
    products = Product.objects.select_related("category", "supplier").order_by("name")
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventario"
    _write_sheet(
        ws,
        [
            "SKU",
            "Producto",
            "Categoría",
            "Proveedor",
            "Costo",
            "Precio",
            "Stock",
            "Stock mínimo",
            "Valor (costo)",
            "Estado",
        ],
        (
            [
                p.sku,
                p.name,
                p.category.name,
                p.supplier.name if p.supplier else "",
                float(p.cost_price),
                float(p.sale_price),
                p.stock,
                p.min_stock,
                float(p.cost_price * p.stock),
                "Stock bajo" if p.is_low_stock else "OK",
            ]
            for p in products
        ),
    )
    return _to_bytes(wb)
