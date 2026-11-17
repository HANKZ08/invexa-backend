"""Generación de la factura en PDF con ReportLab."""

from io import BytesIO

from django.conf import settings
from django.utils import timezone
from django.utils.html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.shop.services import get_settings

from .models import Sale


def _payment_line(payment) -> str:
    ref = f" (op. {escape(payment.reference)})" if payment.reference else ""
    return f"{escape(payment.get_method_display())} {_fmt(payment.amount)}{ref}"


def _fmt(value) -> str:
    return f"{get_settings().currency_symbol} {value:,.2f}"


def build_invoice_pdf(sale: Sale) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Factura {sale.number}",
    )
    styles = getSampleStyleSheet()
    shop = get_settings()
    created = timezone.localtime(sale.created_at).strftime("%d/%m/%Y %H:%M")
    customer = sale.customer
    elements = [
        Paragraph(escape(shop.name), styles["Title"]),
        *([Paragraph(escape(shop.legal_name), styles["Normal"])] if shop.legal_name else []),
        *([Paragraph(f"RUC {escape(shop.tax_id)}", styles["Normal"])] if shop.tax_id else []),
        *([Paragraph(escape(shop.address), styles["Normal"])] if shop.address else []),
        Paragraph(f"<b>Factura de venta {sale.number}</b>", styles["Heading2"]),
        Paragraph(f"Fecha: {created}", styles["Normal"]),
        Paragraph(f"Cajero: {escape(str(sale.cashier))}", styles["Normal"]),
        Paragraph(
            f"Cliente: {escape(customer.name)} · {escape(customer.document_id)}"
            if customer
            else "Cliente: Consumidor final",
            styles["Normal"],
        ),
        Paragraph("Pagos: " + " · ".join(_payment_line(p) for p in sale.payments.all()), styles["Normal"]),
    ]
    if sale.status == Sale.Status.CANCELLED:
        elements.append(Paragraph("<font color='red'><b>VENTA ANULADA</b></font>", styles["Heading3"]))
    elements.append(Spacer(1, 8 * mm))

    rows = [["SKU", "Producto", "Cant.", "Precio", "Total"]]
    rows += [
        [
            item.product_sku,
            item.product_name,
            str(item.quantity),
            _fmt(item.unit_price),
            _fmt(item.line_total),
        ]
        for item in sale.items.all()
    ]
    table = Table(rows, colWidths=[28 * mm, 72 * mm, 16 * mm, 28 * mm, 30 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))

    tax_pct = f"{shop.tax_rate * 100:.0f}%"
    totals = [
        ["Subtotal", _fmt(sale.subtotal)],
        ["Descuento", f"- {_fmt(sale.discount)}"],
        [f"{settings.INVEXA_TAX_LABEL} ({tax_pct})", _fmt(sale.tax)],
        ["TOTAL", _fmt(sale.total)],
        ["Pagado", _fmt(sale.amount_paid)],
        ["Cambio", _fmt(sale.change)],
    ]
    totals_table = Table(totals, colWidths=[40 * mm, 34 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
                ("LINEABOVE", (0, 3), (-1, 3), 0.75, colors.black),
            ]
        )
    )
    elements.append(totals_table)

    doc.build(elements)
    return buffer.getvalue()
