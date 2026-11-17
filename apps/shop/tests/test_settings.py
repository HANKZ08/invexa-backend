from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.shop.models import ShopSettings
from apps.shop.services import get_settings

pytestmark = pytest.mark.django_db


def png_bytes(size=(4, 4)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (31, 63, 168)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def test_anonymous_sees_only_public_fields(api_client):
    response = api_client.get(reverse("shop_settings"))
    assert response.status_code == 200
    assert response.data["name"] == "Ferretería El Tornillo"
    assert "tax_id" not in response.data
    assert response.data["logo_url"] is None


def test_admin_sees_full_settings(client_for, admin_user):
    response = client_for(admin_user).get(reverse("shop_settings"))
    assert response.status_code == 200
    assert "tax_rate" in response.data
    assert "tax_id" in response.data


def test_cashier_cannot_change_settings(client_for, cashier):
    response = client_for(cashier).patch(reverse("shop_settings"), {"name": "Otra"}, format="json")
    assert response.status_code == 403
    assert get_settings().name == "Ferretería El Tornillo"


def test_admin_changes_name_and_tax_data(client_for, admin_user):
    response = client_for(admin_user).patch(
        reverse("shop_settings"),
        {"name": "Ferretería Central", "tax_id": "20123456789", "currency_symbol": "US$"},
        format="json",
    )
    assert response.status_code == 200, response.data
    shop = ShopSettings.load()
    assert shop.name == "Ferretería Central"
    assert shop.tax_id == "20123456789"
    assert shop.currency_symbol == "US$"


@pytest.mark.parametrize(
    "payload",
    [
        {"tax_id": "123"},
        {"tax_id": "2012345678A"},
        {"tax_rate": "1.5"},
        {"tax_rate": "-0.1"},
    ],
)
def test_invalid_tax_data_is_rejected(client_for, admin_user, payload):
    response = client_for(admin_user).patch(reverse("shop_settings"), payload, format="json")
    assert response.status_code == 400


def test_admin_uploads_a_logo(client_for, admin_user):
    upload = SimpleUploadedFile("logo.png", png_bytes(), content_type="image/png")
    response = client_for(admin_user).patch(reverse("shop_settings"), {"logo": upload}, format="multipart")
    assert response.status_code == 200, response.data
    assert response.data["logo_url"].endswith(".png")
    assert get_settings().logo.name.startswith("shop/")


def test_a_text_file_is_not_a_logo(client_for, admin_user):
    upload = SimpleUploadedFile("logo.png", b"esto no es una imagen", content_type="image/png")
    response = client_for(admin_user).patch(reverse("shop_settings"), {"logo": upload}, format="multipart")
    assert response.status_code == 400


def test_a_logo_over_ten_megabytes_is_rejected(client_for, admin_user):
    big = png_bytes() + b"0" * (10 * 1024 * 1024 + 1)
    upload = SimpleUploadedFile("grande.png", big, content_type="image/png")
    response = client_for(admin_user).patch(reverse("shop_settings"), {"icon": upload}, format="multipart")
    assert response.status_code == 400
    assert "10 MB" in str(response.data)


def test_admin_can_remove_the_logo(client_for, admin_user):
    client = client_for(admin_user)
    upload = SimpleUploadedFile("logo.png", png_bytes(), content_type="image/png")
    client.patch(reverse("shop_settings"), {"logo": upload}, format="multipart")
    response = client.patch(reverse("shop_settings"), {"remove_logo": "true"}, format="multipart")
    assert response.status_code == 200
    assert response.data["logo_url"] is None
