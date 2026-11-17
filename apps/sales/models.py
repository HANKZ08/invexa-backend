from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


# Cliente: comprador al que se le puede asociar una venta (opcional; por defecto es consumidor final).
class Customer(TimeStampedModel):
    name = models.CharField(
        "nombre",
        max_length=150,
        help_text="Nombre completo o razón social del cliente.",
    )
    document_id = models.CharField(
        "documento",
        max_length=30,
        unique=True,
        help_text="DNI (8 dígitos) o RUC (11 dígitos) del cliente. Debe ser único.",
    )
    email = models.EmailField(
        "correo",
        blank=True,
        help_text="Correo electrónico del cliente.",
    )
    phone = models.CharField(
        "teléfono",
        max_length=30,
        blank=True,
        help_text="Teléfono de contacto del cliente.",
    )

    # Configuración: nombres en el admin y orden alfabético.
    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.document_id})"


# Venta: cabecera de una venta del punto de venta, con sus totales y su estado.
class Sale(models.Model):
    # Estados de la venta: completada o anulada.
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completada"
        PENDING = "pending", "Pendiente"
        CANCELLED = "cancelled", "Anulada"

    # Métodos de pago aceptados en caja.
    # Medios de pago. "mixed" aparece solo en la venta cuando se usaron varios medios.
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Efectivo"
        CARD = "card", "Tarjeta"
        TRANSFER = "transfer", "Transferencia"
        YAPE = "yape", "Yape"
        PLIN = "plin", "Plin"
        TUNKI = "tunki", "Tunki"
        OTHER_DIGITAL = "other_digital", "Otra billetera digital"
        MIXED = "mixed", "Pago mixto"

    number = models.CharField(
        "número",
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="Número consecutivo de la venta (ej. V-000001). Se genera automáticamente.",
    )
    customer = models.ForeignKey(
        Customer,
        verbose_name="cliente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales",
        help_text="Cliente de la venta. Vacío significa consumidor final.",
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="cajero",
        on_delete=models.PROTECT,
        related_name="sales",
        help_text="Usuario que registró la venta.",
    )
    status = models.CharField(
        "estado",
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
        help_text="Estado de la venta: completada o anulada.",
    )
    payment_method = models.CharField(
        "método de pago",
        max_length=20,
        choices=PaymentMethod.choices,
        help_text="Medio de pago. Si la venta combina medios, queda como pago mixto (ver pagos).",
    )
    subtotal = models.DecimalField(
        "subtotal",
        max_digits=14,
        decimal_places=2,
        help_text="Suma de las líneas de la venta, antes de descuento e impuestos.",
    )
    discount = models.DecimalField(
        "descuento",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Descuento en dinero aplicado al subtotal.",
    )
    tax = models.DecimalField(
        "impuesto",
        max_digits=14,
        decimal_places=2,
        help_text="Impuesto calculado sobre el subtotal menos el descuento.",
    )
    total = models.DecimalField(
        "total",
        max_digits=14,
        decimal_places=2,
        help_text="Monto final a pagar: subtotal - descuento + impuesto.",
    )
    amount_paid = models.DecimalField(
        "pagado",
        max_digits=14,
        decimal_places=2,
        help_text="Monto recibido del cliente. En pagos que no son en efectivo es igual al total.",
    )
    balance = models.DecimalField(
        "saldo pendiente",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Lo que el cliente todavía debe. Cero si la venta está pagada.",
    )
    change = models.DecimalField(
        "cambio",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Dinero devuelto al cliente: pagado - total.",
    )
    notes = models.CharField(
        "notas",
        max_length=255,
        blank=True,
        help_text="Observaciones opcionales de la venta.",
    )
    created_at = models.DateTimeField(
        "fecha",
        auto_now_add=True,
        db_index=True,
        help_text="Fecha y hora de la venta (automático).",
    )
    cancelled_at = models.DateTimeField(
        "anulada el",
        null=True,
        blank=True,
        help_text="Fecha y hora en que se anuló la venta, si aplica.",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="anulada por",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_sales",
        help_text="Administrador que anuló la venta, si aplica.",
    )
    cancellation_reason = models.CharField(
        "motivo de anulación",
        max_length=255,
        blank=True,
        help_text="Motivo por el que se anuló la venta.",
    )

    # Configuración: las ventas más recientes primero.
    class Meta:
        verbose_name = "venta"
        verbose_name_plural = "ventas"
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return self.number or f"Venta #{self.pk}"


# Detalle de venta: cada producto vendido, con una copia de su nombre, precio y costo en ese momento.
class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale,
        verbose_name="venta",
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Venta a la que pertenece esta línea.",
    )
    product = models.ForeignKey(
        "inventory.Product",
        verbose_name="producto",
        on_delete=models.PROTECT,
        related_name="sale_items",
        help_text="Producto vendido.",
    )
    product_name = models.CharField(
        "producto",
        max_length=200,
        help_text="Nombre del producto al momento de la venta (no cambia si luego se edita el producto).",
    )
    product_sku = models.CharField(
        "SKU",
        max_length=40,
        help_text="SKU del producto al momento de la venta.",
    )
    quantity = models.PositiveIntegerField(
        "cantidad",
        help_text="Unidades vendidas.",
    )
    unit_price = models.DecimalField(
        "precio unitario",
        max_digits=12,
        decimal_places=2,
        help_text="Precio de venta unitario al momento de la venta.",
    )
    unit_cost = models.DecimalField(
        "costo unitario",
        max_digits=12,
        decimal_places=2,
        help_text="Costo unitario al momento de la venta. Se usa para calcular el margen.",
    )
    line_total = models.DecimalField(
        "total línea",
        max_digits=14,
        decimal_places=2,
        help_text="Precio unitario × cantidad.",
    )

    # Configuración: las líneas en el orden en que se agregaron.
    class Meta:
        verbose_name = "detalle de venta"
        verbose_name_plural = "detalles de venta"
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.quantity} × {self.product_name}"


# Pago individual de una venta: una venta puede tener varios (efectivo + Yape, por ejemplo).
class SalePayment(models.Model):
    sale = models.ForeignKey(
        Sale,
        verbose_name="venta",
        on_delete=models.CASCADE,
        related_name="payments",
        help_text="Venta a la que pertenece este pago.",
    )
    method = models.CharField(
        "medio",
        max_length=20,
        choices=[c for c in Sale.PaymentMethod.choices if c[0] != Sale.PaymentMethod.MIXED],
        help_text="Medio con el que se pagó esta parte.",
    )
    amount = models.DecimalField(
        "monto",
        max_digits=14,
        decimal_places=2,
        help_text="Monto recibido con este medio. En efectivo puede superar la parte que cubre (genera cambio).",
    )
    reference = models.CharField(
        "número de operación",
        max_length=60,
        blank=True,
        help_text="Número de operación del pago digital o de tarjeta. Vacío en efectivo.",
    )

    # Configuración: los pagos en el orden en que se registraron.
    class Meta:
        verbose_name = "pago de venta"
        verbose_name_plural = "pagos de venta"
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.get_method_display()} {self.amount}"


# Abono: pago parcial o total de una deuda (venta pendiente).
class DebtPayment(models.Model):
    sale = models.ForeignKey(
        Sale,
        verbose_name="venta",
        on_delete=models.CASCADE,
        related_name="debt_payments",
        help_text="Venta pendiente que se abona.",
    )
    method = models.CharField(
        "medio",
        max_length=20,
        choices=[c for c in Sale.PaymentMethod.choices if c[0] != Sale.PaymentMethod.MIXED],
        help_text="Medio con el que se pagó el abono.",
    )
    amount = models.DecimalField(
        "monto",
        max_digits=14,
        decimal_places=2,
        help_text="Monto abonado. Nunca mayor al saldo pendiente.",
    )
    reference = models.CharField(
        "número de operación",
        max_length=60,
        blank=True,
        help_text="Número de operación del abono digital. Vacío en efectivo.",
    )
    created_at = models.DateTimeField(
        "fecha",
        auto_now_add=True,
        help_text="Fecha y hora del abono (automático).",
    )

    # Configuración: los abonos más recientes primero.
    class Meta:
        verbose_name = "abono"
        verbose_name_plural = "abonos"
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"Abono {self.amount} · {self.sale.number}"
