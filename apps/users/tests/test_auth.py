import pytest
from django.urls import reverse

from apps.users.models import User
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_obtain_jwt_and_access_me(api_client, cashier):
    response = api_client.post(
        reverse("token_obtain_pair"), {"username": cashier.username, "password": PASSWORD}
    )
    assert response.status_code == 200
    token = response.data["access"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    me = api_client.get(reverse("me"))
    assert me.status_code == 200
    assert me.data["username"] == cashier.username
    assert me.data["role"] == User.Role.CASHIER


def test_wrong_password_is_rejected(api_client, cashier):
    response = api_client.post(reverse("token_obtain_pair"), {"username": cashier.username, "password": "x"})
    assert response.status_code == 401


def test_login_is_throttled(api_client, cashier):
    url = reverse("token_obtain_pair")
    codes = [
        api_client.post(url, {"username": cashier.username, "password": "x"}).status_code for _ in range(11)
    ]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_anonymous_cannot_access_api(api_client):
    assert api_client.get(reverse("product-list")).status_code == 401


def test_only_admin_can_manage_users(client_for, cashier, admin_user):
    assert client_for(cashier).get(reverse("user-list")).status_code == 403

    response = client_for(admin_user).post(
        reverse("user-list"), {"username": "nuevo", "email": "nuevo@test.local", "role": "warehouse"}
    )
    assert response.status_code == 201
    assert "password" not in response.data
    user = User.objects.get(username="nuevo")
    assert user.is_active is False
    assert not user.has_usable_password()


def test_delete_user_is_soft(client_for, admin_user, cashier):
    response = client_for(admin_user).delete(reverse("user-detail", args=[cashier.pk]))
    assert response.status_code == 204
    cashier.refresh_from_db()
    assert cashier.is_active is False


def test_superuser_is_always_admin(db):
    user = User.objects.create_superuser("root", "root@test.local", "x")
    assert user.role == User.Role.ADMIN
    assert user.is_admin


def test_change_password(client_for, cashier):
    response = client_for(cashier).post(
        reverse("change_password"), {"current_password": PASSWORD, "new_password": "Otra-Clave-987"}
    )
    assert response.status_code == 204
    cashier.refresh_from_db()
    assert cashier.check_password("Otra-Clave-987")
