"""Consultas agregadas para el dashboard y los reportes."""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from apps.inventory.models import Product
from apps.sales.models import Sale, SaleItem

ZERO = Value(Decimal("0"), output_field=DecimalField(max_digits=14, decimal_places=2))


def default_range() -> tuple[date, date]:
    today = timezone.localdate()
    return today - timedelta(days=29), today


def completed_sales(date_from: date, date_to: date):
    return Sale.objects.filter(
        status=Sale.Status.COMPLETED,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )


def _sales_by_payment(sales, date_from: date, date_to: date) -> list[dict]:
    """Ingresos por medio de pago. El cambio en efectivo no cuenta; los abonos cuentan el día que se pagan."""
    from collections import defaultdict

    from apps.sales.models import DebtPayment

    labels = dict(Sale.PaymentMethod.choices)
    revenue: dict[str, Decimal] = defaultdict(Decimal)
    counted: dict[str, set[int]] = defaultdict(set)
    for sale in sales.prefetch_related("payments"):
        for payment in sale.payments.all():
            applied = payment.amount
            if payment.method == Sale.PaymentMethod.CASH:
                applied -= sale.change
            revenue[payment.method] += applied
            counted[payment.method].add(sale.pk)
    abonos = DebtPayment.objects.filter(
        created_at__date__gte=date_from, created_at__date__lte=date_to
    ).select_related("sale")
    for abono in abonos:
        revenue[abono.method] += abono.amount
        counted[abono.method].add(abono.sale_id)
    rows = [
        {
            "payment_method": method,
            "payment_method_display": labels.get(method, method),
            "sales_count": len(counted[method]),
            "revenue": revenue[method].quantize(Decimal("0.01")),
        }
        for method in revenue
    ]
    return sorted(rows, key=lambda row: row["revenue"], reverse=True)


def dashboard(date_from: date, date_to: date) -> dict:
    sales = completed_sales(date_from, date_to)
    items = SaleItem.objects.filter(sale__in=sales)

    totals = sales.aggregate(
        sales_count=Count("id"),
        revenue=Coalesce(Sum("total"), ZERO),
        tax=Coalesce(Sum("tax"), ZERO),
        discounts=Coalesce(Sum("discount"), ZERO),
    )
    margin_expr = ExpressionWrapper(
        (F("unit_price") - F("unit_cost")) * F("quantity"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    item_totals = items.aggregate(
        units_sold=Coalesce(Sum("quantity"), 0),
        gross_profit=Coalesce(Sum(margin_expr), ZERO),
    )
    count = totals["sales_count"]
    average_ticket = (totals["revenue"] / count).quantize(Decimal("0.01")) if count else Decimal("0")

    by_day = list(
        sales.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(sales_count=Count("id"), revenue=Sum("total"))
        .order_by("day")
    )
    by_payment = _sales_by_payment(sales, date_from, date_to)

    top_products = list(
        items.values("product_id", "product_sku", "product_name")
        .annotate(units_sold=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-units_sold", "-revenue")[:10]
    )

    inventory = Product.objects.filter(is_active=True).aggregate(
        products_count=Count("id"),
        inventory_cost=Coalesce(
            Sum(
                ExpressionWrapper(
                    F("cost_price") * F("stock"),
                    output_field=DecimalField(max_digits=16, decimal_places=2),
                )
            ),
            ZERO,
        ),
    )

    return {
        "date_from": date_from,
        "date_to": date_to,
        "summary": {
            **totals,
            **item_totals,
            "average_ticket": average_ticket,
            "cancelled_count": Sale.objects.filter(
                status=Sale.Status.CANCELLED,
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
            ).count(),
        },
        "inventory": {
            **inventory,
            "low_stock_count": Product.objects.low_stock().count(),
        },
        "sales_by_day": by_day,
        "sales_by_payment_method": by_payment,
        "top_products": top_products,
    }
