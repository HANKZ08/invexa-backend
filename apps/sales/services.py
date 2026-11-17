"""Lógica de negocio de ventas."""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.inventory.models import Product, StockMovement
from apps.inventory.services import apply_stock_change
from apps.shop.services import get_settings

from .models import DebtPayment, Sale, SaleItem, SalePayment

CENT = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


CASH = Sale.PaymentMethod.CASH


def split_payments(
    payments: list[dict], total: Decimal, allow_debt: bool = False
) -> tuple[Decimal, Decimal, str, Decimal]:
    """Valida los pagos contra el total.

    Devuelve (monto recibido, cambio, medio de la venta, saldo pendiente).
    Los pagos no efectivo cubren primero el total y exigen número de operación; la parte
    restante debe pagarse en efectivo, que es el único medio que da cambio. Si ``allow_debt``
    es verdadero, lo que falte queda como saldo pendiente en vez de error.
    """
    if not payments:
        raise ValidationError({"payments": "Agrega al menos un pago."})

    non_cash = Decimal("0")
    cash = Decimal("0")
    for payment in payments:
        amount = money(payment["amount"])
        if amount <= 0:
            raise ValidationError({"payments": "Cada pago debe ser mayor a cero."})
        if payment["method"] == CASH:
            cash += amount
        else:
            if not (payment.get("reference") or "").strip():
                raise ValidationError({"payments": "Escribe el número de operación del pago digital."})
            non_cash += amount

    if non_cash > total:
        raise ValidationError({"payments": "Los pagos digitales superan el total de la venta."})

    cash_needed = total - non_cash
    debt = Decimal("0")
    change = Decimal("0")
    if cash < cash_needed:
        missing = money(cash_needed - cash)
        if not allow_debt:
            raise ValidationError({"payments": f"Falta cubrir S/ {missing} en efectivo."})
        debt = missing
    else:
        change = money(cash - cash_needed)

    received = money(cash + non_cash)
    methods = {p["method"] for p in payments}
    sale_method = methods.pop() if len(methods) == 1 else Sale.PaymentMethod.MIXED
    return received, change, sale_method, debt


@transaction.atomic
def create_sale(
    *,
    cashier,
    items: list[dict],
    payments: list[dict],
    discount: Decimal = Decimal("0"),
    customer=None,
    notes: str = "",
) -> Sale:
    """Crea una venta, descuenta stock y registra el kardex en una sola transacción.

    ``items`` es una lista de ``{"product": Product | id, "quantity": int}``.
    ``payments`` es una lista de ``{"method", "amount", "reference"}``.
    Si un mismo producto aparece varias veces, sus cantidades se suman.
    """
    if not items:
        raise ValidationError({"items": "La venta debe tener al menos un producto."})

    quantities: dict[int, int] = defaultdict(int)
    for item in items:
        product = item["product"]
        quantities[getattr(product, "pk", product)] += item["quantity"]

    # Bloqueo en orden por id para evitar interbloqueos entre cajas.
    products = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=quantities).order_by("pk")}

    errors = []
    for product_id, qty in quantities.items():
        product = products.get(product_id)
        if product is None or not product.is_active:
            errors.append(f"El producto {product_id} no existe o está inactivo.")
        elif product.stock < qty:
            errors.append(
                f"Stock insuficiente para «{product.name}»: disponible {product.stock}, solicitado {qty}."
            )
    if errors:
        raise ValidationError({"items": errors})

    subtotal = money(sum(products[pid].sale_price * qty for pid, qty in quantities.items()))
    discount = money(discount)
    if discount > subtotal:
        raise ValidationError({"discount": "El descuento no puede superar el subtotal."})

    taxable = subtotal - discount
    tax = money(taxable * get_settings().tax_rate)
    total = taxable + tax

    received, change, sale_method, debt = split_payments(payments, total, allow_debt=True)
    if debt > 0 and customer is None:
        raise ValidationError({"customer": "Para dejar una deuda, elige al cliente (DNI o RUC)."})

    sale = Sale.objects.create(
        cashier=cashier,
        customer=customer,
        payment_method=sale_method,
        status=Sale.Status.PENDING if debt > 0 else Sale.Status.COMPLETED,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        total=total,
        amount_paid=received,
        balance=debt,
        change=change,
        notes=notes,
    )
    sale.number = f"V-{sale.pk:06d}"
    sale.save(update_fields=["number"])

    for payment in payments:
        SalePayment.objects.create(
            sale=sale,
            method=payment["method"],
            amount=money(payment["amount"]),
            reference=(payment.get("reference") or "").strip(),
        )

    for product_id, qty in quantities.items():
        product = products[product_id]
        SaleItem.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            product_sku=product.sku,
            quantity=qty,
            unit_price=product.sale_price,
            unit_cost=product.cost_price,
            line_total=money(product.sale_price * qty),
        )
        apply_stock_change(
            product=product,
            quantity=-qty,
            movement_type=StockMovement.MovementType.SALE,
            user=cashier,
            note=f"Venta {sale.number}",
            sale=sale,
            lock=False,
        )

    return sale


@transaction.atomic
def cancel_sale(*, sale: Sale, user, reason: str) -> Sale:
    """Anula una venta y devuelve el stock de cada producto."""
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status == Sale.Status.CANCELLED:
        raise ValidationError("La venta ya está anulada.")

    for item in sale.items.select_related("product").order_by("product_id"):
        apply_stock_change(
            product=item.product,
            quantity=item.quantity,
            movement_type=StockMovement.MovementType.SALE_CANCELLATION,
            user=user,
            note=f"Anulación {sale.number}",
            sale=sale,
        )

    sale.status = Sale.Status.CANCELLED
    sale.cancelled_at = timezone.now()
    sale.cancelled_by = user
    sale.cancellation_reason = reason
    sale.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancellation_reason"])
    return sale


@transaction.atomic
def pay_debt(*, sale: Sale, user, payments: list[dict]) -> Sale:
    """Registra abonos a una venta pendiente. Si se paga todo, la venta pasa a completada."""
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status != Sale.Status.PENDING:
        raise ValidationError("Esta venta no tiene saldo pendiente.")
    if not payments:
        raise ValidationError({"payments": "Agrega al menos un abono."})

    total_abono = Decimal("0")
    rows = []
    for payment in payments:
        amount = money(payment["amount"])
        if amount <= 0:
            raise ValidationError({"payments": "Cada abono debe ser mayor a cero."})
        reference = (payment.get("reference") or "").strip()
        if payment["method"] != CASH and not reference:
            raise ValidationError({"payments": "Escribe el número de operación del abono digital."})
        total_abono += amount
        rows.append((payment["method"], amount, reference))

    if total_abono > sale.balance:
        raise ValidationError({"payments": f"El abono supera el saldo pendiente (S/ {sale.balance})."})

    for method, amount, reference in rows:
        DebtPayment.objects.create(sale=sale, method=method, amount=amount, reference=reference)

    sale.balance = money(sale.balance - total_abono)
    sale.amount_paid = money(sale.amount_paid + total_abono)
    if sale.balance == 0:
        sale.status = Sale.Status.COMPLETED
    sale.save(update_fields=["balance", "amount_paid", "status"])
    return sale
