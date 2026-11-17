from decimal import Decimal

from django.db import models

DEFAULT_SHOP_NAME = "Ferretería El Tornillo"


# Configuración de la tienda: siempre una sola fila (pk=1), editable por el administrador.
class ShopSettings(models.Model):
    name = models.CharField(
        "nombre comercial",
        max_length=120,
        default=DEFAULT_SHOP_NAME,
        help_text="Nombre que se muestra en la app, la pantalla de ingreso y la factura.",
    )
    legal_name = models.CharField(
        "razón social",
        max_length=160,
        blank=True,
        help_text="Razón social que aparece en la factura. Opcional.",
    )
    tax_id = models.CharField(
        "RUC",
        max_length=11,
        blank=True,
        help_text="RUC de la tienda (11 dígitos). Opcional.",
    )
    address = models.CharField(
        "dirección",
        max_length=200,
        blank=True,
        help_text="Dirección fiscal o del local que aparece en la factura. Opcional.",
    )
    phone = models.CharField(
        "teléfono",
        max_length=30,
        blank=True,
        help_text="Teléfono de contacto que aparece en la factura. Opcional.",
    )
    tax_rate = models.DecimalField(
        "IGV",
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.18"),
        help_text="IGV como fracción (0.18 = 18 %). Solo afecta a las ventas nuevas.",
    )
    currency_symbol = models.CharField(
        "símbolo de moneda",
        max_length=5,
        default="S/",
        help_text="Símbolo que se muestra junto a los montos (por ejemplo S/ o US$).",
    )
    logo = models.ImageField(
        "logo completo",
        upload_to="shop/",
        blank=True,
        null=True,
        help_text="Logo con letras (PNG, JPG o WEBP, máximo 10 MB).",
    )
    icon = models.ImageField(
        "ícono",
        upload_to="shop/",
        blank=True,
        null=True,
        help_text="Solo el símbolo, para el menú contraído y el favicon (PNG, JPG o WEBP, máximo 10 MB).",
    )

    # Configuración: la tabla guarda una sola fila, siempre con pk=1.
    class Meta:
        verbose_name = "configuración de la tienda"
        verbose_name_plural = "configuración de la tienda"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "ShopSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
