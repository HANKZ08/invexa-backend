from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.common.models import TimeStampedModel


# Categoría: agrupa los productos del catálogo (Bebidas, Snacks, Aseo, etc.).
class Category(TimeStampedModel):
    name = models.CharField(
        "nombre",
        max_length=100,
        unique=True,
        help_text="Nombre de la categoría. Debe ser único.",
    )
    description = models.TextField(
        "descripción",
        blank=True,
        help_text="Descripción opcional de la categoría.",
    )
    is_active = models.BooleanField(
        "activa",
        default=True,
        help_text="Desmárcalo para ocultar la categoría sin borrarla.",
    )

    # Configuración: nombres en el admin y orden alfabético.
    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


# Proveedor: empresa que abastece los productos.
class Supplier(TimeStampedModel):
    name = models.CharField(
        "nombre",
        max_length=150,
        help_text="Razón social o nombre comercial del proveedor.",
    )
    tax_id = models.CharField(
        "RUC",
        max_length=30,
        unique=True,
        help_text="RUC del proveedor (11 dígitos). Debe ser único.",
    )
    contact_name = models.CharField(
        "contacto",
        max_length=150,
        blank=True,
        help_text="Persona de contacto con el proveedor.",
    )
    email = models.EmailField(
        "correo",
        blank=True,
        help_text="Correo electrónico del proveedor.",
    )
    phone = models.CharField(
        "teléfono",
        max_length=30,
        blank=True,
        help_text="Teléfono de contacto del proveedor.",
    )
    address = models.CharField(
        "dirección",
        max_length=255,
        blank=True,
        help_text="Dirección física del proveedor.",
    )
    is_active = models.BooleanField(
        "activo",
        default=True,
        help_text="Desmárcalo para dejar de trabajar con el proveedor sin borrarlo.",
    )

    # Configuración: nombres en el admin y orden alfabético.
    class Meta:
        verbose_name = "proveedor"
        verbose_name_plural = "proveedores"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


# QuerySet de productos: consultas reutilizables, como los productos con stock bajo.
class ProductQuerySet(models.QuerySet):
    def low_stock(self):
        return self.filter(is_active=True, stock__lte=F("min_stock"))


# Producto: artículo del catálogo con precios y stock. El stock solo cambia mediante movimientos.
class Product(TimeStampedModel):
    sku = models.CharField(
        "SKU",
        max_length=40,
        unique=True,
        help_text="Código interno único del producto (ej. BEB-001).",
    )
    barcode = models.CharField(
        "código de barras",
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text="Código de barras (EAN/UPC) para buscar el producto con lector. Opcional y único.",
    )
    name = models.CharField(
        "nombre",
        max_length=200,
        help_text="Nombre del producto tal como se muestra en ventas y facturas.",
    )
    description = models.TextField(
        "descripción",
        blank=True,
        help_text="Descripción opcional del producto.",
    )
    category = models.ForeignKey(
        Category,
        verbose_name="categoría",
        on_delete=models.PROTECT,
        related_name="products",
        help_text="Categoría a la que pertenece el producto.",
    )
    supplier = models.ForeignKey(
        Supplier,
        verbose_name="proveedor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        help_text="Proveedor habitual del producto. Opcional.",
    )
    cost_price = models.DecimalField(
        "precio de costo",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Precio de compra unitario, sin impuestos. Se usa para calcular el margen.",
    )
    sale_price = models.DecimalField(
        "precio de venta",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Precio de venta unitario, sin impuestos. No puede ser menor al costo.",
    )
    stock = models.PositiveIntegerField(
        "stock",
        default=0,
        editable=False,
        help_text="Unidades disponibles. Solo cambia mediante movimientos de stock o ventas.",
    )
    min_stock = models.PositiveIntegerField(
        "stock mínimo",
        default=5,
        help_text="Cuando el stock llega a este valor o menos, el producto aparece con stock bajo.",
    )
    is_active = models.BooleanField(
        "activo",
        default=True,
        help_text="Desmárcalo para que el producto no se pueda vender, sin borrarlo.",
    )

    objects = ProductQuerySet.as_manager()

    # Configuración: orden alfabético y regla de que el precio de venta no sea menor al costo.
    class Meta:
        verbose_name = "producto"
        verbose_name_plural = "productos"
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(
                condition=Q(sale_price__gte=F("cost_price")),
                name="product_sale_price_gte_cost_price",
                violation_error_message="El precio de venta no puede ser menor al costo.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.sku} · {self.name}"

    @property
    def is_low_stock(self) -> bool:
        return self.stock <= self.min_stock


# Movimiento de stock (kardex): registro inmutable de cada entrada, salida, ajuste o venta.
class StockMovement(models.Model):
    # Tipos de movimiento: los tres primeros son manuales; los de venta los genera el sistema.
    class MovementType(models.TextChoices):
        IN = "in", "Entrada"
        OUT = "out", "Salida"
        ADJUSTMENT = "adjustment", "Ajuste por conteo"
        SALE = "sale", "Venta"
        SALE_CANCELLATION = "sale_cancellation", "Anulación de venta"

    product = models.ForeignKey(
        Product,
        verbose_name="producto",
        on_delete=models.PROTECT,
        related_name="movements",
        help_text="Producto cuyo stock cambió.",
    )
    movement_type = models.CharField(
        "tipo",
        max_length=20,
        choices=MovementType.choices,
        help_text="Motivo del movimiento: entrada, salida, ajuste, venta o anulación de venta.",
    )
    quantity = models.IntegerField(
        "cantidad",
        help_text="Unidades que cambiaron. Positivo suma stock, negativo resta.",
    )
    stock_before = models.PositiveIntegerField(
        "stock anterior",
        help_text="Stock del producto justo antes del movimiento.",
    )
    stock_after = models.PositiveIntegerField(
        "stock posterior",
        help_text="Stock del producto justo después del movimiento.",
    )
    note = models.CharField(
        "nota",
        max_length=255,
        blank=True,
        help_text="Detalle opcional (ej. número de factura del proveedor o motivo de la merma).",
    )
    sale = models.ForeignKey(
        "sales.Sale",
        verbose_name="venta",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="stock_movements",
        help_text="Venta que originó el movimiento, si aplica.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        on_delete=models.PROTECT,
        related_name="stock_movements",
        help_text="Usuario que registró el movimiento.",
    )
    created_at = models.DateTimeField(
        "fecha",
        auto_now_add=True,
        help_text="Fecha y hora del movimiento (automático).",
    )

    # Configuración: los movimientos más recientes primero.
    class Meta:
        verbose_name = "movimiento de stock"
        verbose_name_plural = "movimientos de stock"
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"{self.get_movement_type_display()} {self.quantity:+d} · {self.product.sku}"
