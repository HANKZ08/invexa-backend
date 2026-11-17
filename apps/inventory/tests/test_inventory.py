import pytest
from django.urls import reverse

from apps.inventory.models import Product, StockMovement

pytestmark = pytest.mark.django_db


def test_warehouse_can_create_product(client_for, warehouse_user, category):
    payload = {
        "sku": "NEW-001",
        "name": "Producto nuevo",
        "category": category.pk,
        "cost_price": "1.50",
        "sale_price": "3.00",
        "min_stock": 4,
    }
    response = client_for(warehouse_user).post(reverse("product-list"), payload)
    assert response.status_code == 201
    assert response.data["stock"] == 0  # el stock no se asigna directamente


def test_stock_is_read_only_in_api(client_for, warehouse_user, product_factory):
    product = product_factory(stock=5)
    response = client_for(warehouse_user).patch(reverse("product-detail", args=[product.pk]), {"stock": 999})
    assert response.status_code == 200
    product.refresh_from_db()
    assert product.stock == 5


def test_sale_price_cannot_be_below_cost(client_for, warehouse_user, category):
    payload = {"sku": "X", "name": "X", "category": category.pk, "cost_price": "5", "sale_price": "4"}
    response = client_for(warehouse_user).post(reverse("product-list"), payload)
    assert response.status_code == 400
    assert "sale_price" in response.data


def test_cashier_can_read_but_not_write_products(client_for, cashier, category, product_factory):
    product_factory()
    client = client_for(cashier)
    assert client.get(reverse("product-list")).status_code == 200
    response = client.post(
        reverse("product-list"),
        {"sku": "Y", "name": "Y", "category": category.pk, "cost_price": "1", "sale_price": "2"},
    )
    assert response.status_code == 403


def test_cashier_cannot_see_suppliers_or_movements(client_for, cashier):
    client = client_for(cashier)
    assert client.get(reverse("supplier-list")).status_code == 403
    assert client.get(reverse("stock-movement-list")).status_code == 403


def test_search_product_by_barcode(client_for, cashier, product_factory):
    product_factory(barcode="7701234567890", name="Leche")
    product_factory(name="Pan")
    response = client_for(cashier).get(reverse("product-list"), {"search": "7701234567890"})
    assert [p["name"] for p in response.data["results"]] == ["Leche"]


def test_low_stock_filter(client_for, warehouse_user, product_factory):
    product_factory(stock=2, min_stock=5, name="Escaso")
    product_factory(stock=50, min_stock=5, name="Abundante")
    response = client_for(warehouse_user).get(reverse("product-list"), {"low_stock": "true"})
    assert [p["name"] for p in response.data["results"]] == ["Escaso"]


@pytest.mark.parametrize(
    ("movement_type", "quantity", "expected_stock", "expected_delta"),
    [("in", 5, 15, 5), ("out", 4, 6, -4), ("adjustment", 7, 7, -3)],
)
def test_manual_stock_movements(
    client_for, warehouse_user, product_factory, movement_type, quantity, expected_stock, expected_delta
):
    product = product_factory(stock=10)
    response = client_for(warehouse_user).post(
        reverse("stock-movement-list"),
        {"product": product.pk, "movement_type": movement_type, "quantity": quantity, "note": "test"},
    )
    assert response.status_code == 201, response.data
    assert response.data["quantity"] == expected_delta
    assert response.data["stock_before"] == 10
    product.refresh_from_db()
    assert product.stock == expected_stock


def test_out_movement_cannot_leave_negative_stock(client_for, warehouse_user, product_factory):
    product = product_factory(stock=3)
    response = client_for(warehouse_user).post(
        reverse("stock-movement-list"), {"product": product.pk, "movement_type": "out", "quantity": 4}
    )
    assert response.status_code == 400
    product.refresh_from_db()
    assert product.stock == 3


def test_sale_movement_type_not_allowed_manually(client_for, warehouse_user, product_factory):
    product = product_factory(stock=3)
    response = client_for(warehouse_user).post(
        reverse("stock-movement-list"), {"product": product.pk, "movement_type": "sale", "quantity": 1}
    )
    assert response.status_code == 400


def test_cannot_delete_product_with_movements(client_for, warehouse_user, product_factory):
    product = product_factory(stock=3)
    response = client_for(warehouse_user).delete(reverse("product-detail", args=[product.pk]))
    assert response.status_code == 400
    assert Product.objects.filter(pk=product.pk).exists()
    assert StockMovement.objects.filter(product=product).count() == 1
