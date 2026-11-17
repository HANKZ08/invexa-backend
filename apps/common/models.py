from django.db import models


# Modelo abstracto base: agrega fechas de creación y actualización a los modelos que lo heredan.
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(
        "creado",
        auto_now_add=True,
        help_text="Fecha y hora en que se creó el registro (automático).",
    )
    updated_at = models.DateTimeField(
        "actualizado",
        auto_now=True,
        help_text="Fecha y hora de la última modificación del registro (automático).",
    )

    # Configuración: no crea tabla propia, solo comparte sus campos.
    class Meta:
        abstract = True
