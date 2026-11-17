from PIL import Image
from rest_framework.exceptions import ValidationError

from .models import ShopSettings

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
EDITABLE_FIELDS = ("name", "legal_name", "tax_id", "address", "phone", "tax_rate", "currency_symbol")


# Devuelve la configuración vigente de la tienda (la crea si aún no existe).
def get_settings() -> ShopSettings:
    return ShopSettings.load()


# Valida una imagen subida: tamaño, tipo declarado y que realmente sea una imagen.
def validate_image(file) -> None:
    if file.size > MAX_IMAGE_BYTES:
        raise ValidationError("La imagen supera los 10 MB.")
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError("Solo se aceptan imágenes PNG, JPG o WEBP.")
    try:
        with Image.open(file) as img:
            img.verify()
    except Exception as exc:
        raise ValidationError("El archivo no es una imagen válida.") from exc
    finally:
        file.seek(0)


# Aplica los cambios validados. Un logo nuevo reemplaza al anterior, que se borra del disco.
def update_settings(shop: ShopSettings, data: dict) -> ShopSettings:
    for field in EDITABLE_FIELDS:
        if field in data:
            setattr(shop, field, data[field])
    for kind in ("logo", "icon"):
        upload = data.get(kind)
        if data.get(f"remove_{kind}"):
            _delete_file(getattr(shop, kind))
            setattr(shop, kind, None)
        elif upload:
            validate_image(upload)
            _delete_file(getattr(shop, kind))
            setattr(shop, kind, upload)
    shop.save()
    return shop


def _delete_file(field_file) -> None:
    if field_file:
        field_file.delete(save=False)
