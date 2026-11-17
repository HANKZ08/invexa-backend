from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.inventory.models import Category, Product, StockMovement
from apps.inventory.services import apply_stock_change
from apps.users.models import User

PASSWORD = "Test-Pass-123"


@pytest.fixture(autouse=True)
def _no_https_redirect(settings):
    # Las pruebas llaman a la API por HTTP; la redirección a HTTPS solo aplica en producción.
    settings.SECURE_SSL_REDIRECT = False


@pytest.fixture(autouse=True)
def _tax_rate(settings):
    settings.INVEXA_TAX_RATE = 0.18


@pytest.fixture(autouse=True)
def _clear_cache():
    # El límite de intentos de login se guarda en caché; se limpia entre tests.
    from django.core.cache import cache

    cache.clear()


def make_user(username: str, role: str) -> User:
    return User.objects.create_user(
        username=username, email=f"{username}@test.local", password=PASSWORD, role=role
    )


@pytest.fixture
def admin_user(db):
    return make_user("admin_test", User.Role.ADMIN)


@pytest.fixture
def cashier(db):
    return make_user("cashier_test", User.Role.CASHIER)


@pytest.fixture
def other_cashier(db):
    return make_user("cashier_two", User.Role.CASHIER)


@pytest.fixture
def warehouse_user(db):
    return make_user("warehouse_test", User.Role.WAREHOUSE)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def client_for(api_client):
    def _client(user):
        api_client.force_authenticate(user=user)
        return api_client

    return _client


@pytest.fixture
def category(db):
    return Category.objects.create(name="Bebidas")


@pytest.fixture
def product_factory(db, category, warehouse_user):
    counter = {"n": 0}

    def _make(stock=10, cost="1.00", price="2.00", min_stock=5, **kwargs):
        counter["n"] += 1
        product = Product.objects.create(
            sku=kwargs.pop("sku", f"SKU-{counter['n']:03d}"),
            name=kwargs.pop("name", f"Producto {counter['n']}"),
            category=category,
            cost_price=Decimal(cost),
            sale_price=Decimal(price),
            min_stock=min_stock,
            **kwargs,
        )
        if stock:
            apply_stock_change(
                product=product,
                quantity=stock,
                movement_type=StockMovement.MovementType.IN,
                user=warehouse_user,
            )
            product.refresh_from_db()
        return product

    return _make
