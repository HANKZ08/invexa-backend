"""Lógica de negocio del inventario.

Toda modificación de stock pasa por ``apply_stock_change`` para garantizar
que se bloquee la fila del producto y quede registrada en el kardex.
"""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Product, StockMovement

MovementType = StockMovement.MovementType


@transaction.atomic
def apply_stock_change(
    *,
    product: Product,
    quantity: int,
    movement_type: str,
    user,
    note: str = "",
    sale=None,
    lock: bool = True,
) -> StockMovement:
    """Suma (o resta, si ``quantity`` es negativo) stock a un producto."""
    if quantity == 0:
        raise ValidationError({"quantity": "La cantidad no puede ser cero."})

    if lock:
        product = Product.objects.select_for_update().get(pk=product.pk)

    stock_before = product.stock
    stock_after = stock_before + quantity
    if stock_after < 0:
        raise ValidationError(
            {
                "quantity": (
                    f"Stock insuficiente para «{product.name}»: "
                    f"disponible {stock_before}, solicitado {abs(quantity)}."
                )
            }
        )

    product.stock = stock_after
    product.save(update_fields=["stock", "updated_at"])

    return StockMovement.objects.create(
        product=product,
        movement_type=movement_type,
        quantity=quantity,
        stock_before=stock_before,
        stock_after=stock_after,
        note=note,
        sale=sale,
        user=user,
    )


def register_manual_movement(
    *, product: Product, movement_type: str, quantity: int, user, note: str = ""
) -> StockMovement:
    """Movimientos manuales desde bodega.

    - ``in``: entrada de mercancía (suma ``quantity``).
    - ``out``: salida por merma, daño, etc. (resta ``quantity``).
    - ``adjustment``: ``quantity`` es el stock contado físicamente; se registra la diferencia.
    """
    if movement_type == MovementType.IN:
        delta = quantity
    elif movement_type == MovementType.OUT:
        delta = -quantity
    elif movement_type == MovementType.ADJUSTMENT:
        with transaction.atomic():
            locked = Product.objects.select_for_update().get(pk=product.pk)
            delta = quantity - locked.stock
            if delta == 0:
                raise ValidationError({"quantity": "El conteo coincide con el stock actual."})
            return apply_stock_change(
                product=locked,
                quantity=delta,
                movement_type=movement_type,
                user=user,
                note=note,
                lock=False,
            )
    else:
        raise ValidationError({"movement_type": "Tipo de movimiento manual no válido."})

    return apply_stock_change(
        product=product, quantity=delta, movement_type=movement_type, user=user, note=note
    )
