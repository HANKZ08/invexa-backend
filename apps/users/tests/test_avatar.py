from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

pytestmark = pytest.mark.django_db


def png_bytes(size=(4, 4)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (31, 63, 168)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def test_user_uploads_a_png_photo(client_for, cashier):
    upload = SimpleUploadedFile("foto.png", png_bytes(), content_type="image/png")
    response = client_for(cashier).post(reverse("me_avatar"), {"avatar": upload}, format="multipart")
    assert response.status_code == 200, response.data
    assert response.data["avatar_url"].endswith(".png")
    cashier.refresh_from_db()
    assert cashier.avatar.name.startswith("avatars/")


def test_gif_and_jpeg_are_accepted(client_for, cashier):
    buffer = BytesIO()
    Image.new("RGB", (4, 4), (0, 0, 0)).save(buffer, format="GIF")
    gif = SimpleUploadedFile("foto.gif", buffer.getvalue(), content_type="image/gif")
    assert (
        client_for(cashier).post(reverse("me_avatar"), {"avatar": gif}, format="multipart").status_code == 200
    )


def test_a_non_image_file_is_rejected(client_for, cashier):
    upload = SimpleUploadedFile("nota.png", b"esto no es una imagen", content_type="image/png")
    response = client_for(cashier).post(reverse("me_avatar"), {"avatar": upload}, format="multipart")
    assert response.status_code == 400


def test_a_photo_over_ten_megabytes_is_rejected(client_for, cashier):
    big = png_bytes() + b"0" * (10 * 1024 * 1024 + 1)
    upload = SimpleUploadedFile("grande.png", big, content_type="image/png")
    response = client_for(cashier).post(reverse("me_avatar"), {"avatar": upload}, format="multipart")
    assert response.status_code == 400
    assert "10 MB" in str(response.data)


def test_user_can_remove_the_photo(client_for, cashier):
    upload = SimpleUploadedFile("foto.png", png_bytes(), content_type="image/png")
    client = client_for(cashier)
    client.post(reverse("me_avatar"), {"avatar": upload}, format="multipart")
    response = client.delete(reverse("me_avatar"))
    assert response.status_code == 200
    assert response.data["avatar_url"] is None
