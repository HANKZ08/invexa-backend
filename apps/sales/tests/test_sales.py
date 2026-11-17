from decimal import Decimal

import pytest
from django.urls import reverse

from apps.inventory.models import StockMovement
from apps.sales.models import Sale

pytestmark = pytest.mark.django_db


def sale_payload(*items, payments=None, **extra):
    """Por defecto paga con efectivo de sobra; cada prueba puede pasar sus propios pagos."""
    return {
        "payments": payments or [{"method": "cash", "amount": "1000"}],
        "items": [{"product": p.pk, "quantity": q} for p, q in items],
        **extra,
    }


def test_create_sale_computes_totals_and_discounts_stock(client_for, cashier, product_factory):
    a = product_factory(stock=10, price="2.00")
    b = product_factory(stock=5, price="3.50")

    response = client_for(cashier).post(
        reverse("sale-list"),
        sale_payload((a, 3), (b, 2), payments=[{"method": "cash", "amount": "20.00"}], discount="1.00"),
        format="json",
    )
    assert response.status_code == 201, response.data
    data = response.data
    # subtotal 6 + 7 = 13; base 12; IGV 18% = 2.16; total 14.16
    assert Decimal(data["subtotal"]) == Decimal("13.00")
    assert Decimal(data["tax"]) == Decimal("2.16")
    assert Decimal(data["total"]) == Decimal("14.16")
    assert Decimal(data["change"]) == Decimal("5.84")
    assert data["number"].startswith("V-")
    assert len(data["items"]) == 2

    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.stock, b.stock) == (7, 3)
    assert StockMovement.objects.filter(sale_id=data["id"], movement_type="sale").count() == 2


def test_repeated_product_lines_are_merged(client_for, cashier, product_factory):
    a = product_factory(stock=10)
    response = client_for(cashier).post(reverse("sale-list"), sale_payload((a, 2), (a, 3)), format="json")
    assert response.status_code == 201
    assert response.data["items"][0]["quantity"] == 5


def test_insufficient_stock_rolls_back_everything(client_for, cashier, product_factory):
    a = product_factory(stock=10)
    b = product_factory(stock=1)
    response = client_for(cashier).post(reverse("sale-list"), sale_payload((a, 2), (b, 5)), format="json")
    assert response.status_code == 400
    assert "items" in response.data
    a.refresh_from_db()
    assert a.stock == 10
    assert Sale.objects.count() == 0


def test_partial_payment_without_customer_is_rejected(client_for, cashier, product_factory):
    a = product_factory(stock=10, price="10.00")
    response = client_for(cashier).post(
        reverse("sale-list"),
        sale_payload((a, 1), payments=[{"method": "cash", "amount": "5.00"}]),
        format="json",
    )
    assert response.status_code == 400
    assert "customer" in response.data


def test_inactive_product_cannot_be_sold(client_for, cashier, product_factory):
    a = product_factory(stock=10, is_active=False)
    response = client_for(cashier).post(reverse("sale-list"), sale_payload((a, 1)), format="json")
    assert response.status_code == 400


def test_warehouse_cannot_sell(client_for, warehouse_user, product_factory):
    a = product_factory(stock=10)
    response = client_for(warehouse_user).post(reverse("sale-list"), sale_payload((a, 1)), format="json")
    assert response.status_code == 403


def test_cashier_only_sees_own_sales(client_for, cashier, other_cashier, admin_user, product_factory):
    a = product_factory(stock=10)
    client_for(cashier).post(reverse("sale-list"), sale_payload((a, 1)), format="json")
    client_for(other_cashier).post(reverse("sale-list"), sale_payload((a, 1)), format="json")

    assert client_for(cashier).get(reverse("sale-list")).data["count"] == 1
    assert client_for(admin_user).get(reverse("sale-list")).data["count"] == 2


def test_admin_can_cancel_sale_and_stock_is_restored(client_for, cashier, admin_user, product_factory):
    a = product_factory(stock=10)
    sale_id = client_for(cashier).post(reverse("sale-list"), sale_payload((a, 4)), format="json").data["id"]

    url = reverse("sale-cancel", args=[sale_id])
    assert client_for(cashier).post(url, {"reason": "error"}).status_code == 403

    response = client_for(admin_user).post(url, {"reason": "Cliente devolvió"})
    assert response.status_code == 200
    assert response.data["status"] == "cancelled"
    a.refresh_from_db()
    assert a.stock == 10

    # No se puede anular dos veces
    assert client_for(admin_user).post(url, {"reason": "otra vez"}).status_code == 400


def test_invoice_pdf(client_for, cashier, product_factory):
    a = product_factory(stock=10, name="Café & Té")
    sale_id = client_for(cashier).post(reverse("sale-list"), sale_payload((a, 1)), format="json").data["id"]
    response = client_for(cashier).get(reverse("sale-invoice", args=[sale_id]))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_customer_crud_by_cashier(client_for, cashier):
    response = client_for(cashier).post(
        reverse("customer-list"), {"name": "Juan", "document_id": "123", "email": "juan@test.local"}
    )
    assert response.status_code == 201


def test_mixed_payment_gives_change_only_from_cash(client_for, cashier, product_factory):
    a = product_factory(stock=10, price="10.00")  # total con IGV 18 %: 11.80
    response = client_for(cashier).post(
        reverse("sale-list"),
        sale_payload(
            (a, 1),
            payments=[
                {"method": "yape", "amount": "5.00", "reference": "OP-778812"},
                {"method": "cash", "amount": "10.00"},
            ],
        ),
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["payment_method"] == "mixed"
    assert Decimal(response.data["change"]) == Decimal("3.20")  # cash 10 - faltante 6.80
    methods = sorted(p["method"] for p in response.data["payments"])
    assert methods == ["cash", "yape"]


def test_digital_payment_needs_operation_number(client_for, cashier, product_factory):
    a = product_factory(stock=10, price="10.00")
    response = client_for(cashier).post(
        reverse("sale-list"),
        sale_payload((a, 1), payments=[{"method": "yape", "amount": "11.80"}]),
        format="json",
    )
    assert response.status_code == 400
    assert "número de operación" in str(response.data)


def test_digital_payment_cannot_exceed_total(client_for, cashier, product_factory):
    a = product_factory(stock=10, price="10.00")
    response = client_for(cashier).post(
        reverse("sale-list"),
        sale_payload((a, 1), payments=[{"method": "tunki", "amount": "50.00", "reference": "T1"}]),
        format="json",
    )
    assert response.status_code == 400
    assert "superan el total" in str(response.data)


def test_not_enough_cash_for_the_rest_is_rejected(client_for, cashier, product_factory):
    a = product_factory(stock=10, price="10.00")
    response = client_for(cashier).post(
        reverse("sale-list"),
        sale_payload((a, 1), payments=[{"method": "plin", "amount": "5.00", "reference": "P1"}]),
        format="json",
    )
    assert response.status_code == 400
    assert "customer" in response.data


def make_customer(client_for, cashier):
    response = client_for(cashier).post(
        reverse("customer-list"), {"name": "Constructora Andina", "document_id": "20556677881"}
    )
    return response.data["id"]


def test_partial_payment_with_customer_leaves_pending_balance(client_for, cashier, product_factory):
    a = product_factory(stock=10, price="10.00")  # total 11.80
    customer = make_customer(client_for, cashier)
    response = client_for(cashier).post(
        reverse("sale-list"),
        sale_payload((a, 1), customer=customer, payments=[{"method": "cash", "amount": "5.00"}]),
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["status"] == "pending"
    assert Decimal(response.data["balance"]) == Decimal("6.80")
    assert Decimal(response.data["change"]) == Decimal("0")


def test_debt_payments_reduce_balance_until_completed(client_for, cashier, admin_user, product_factory):
    a = product_factory(stock=10, price="10.00")
    customer = make_customer(client_for, cashier)
    sale_id = (
        client_for(cashier)
        .post(
            reverse("sale-list"),
            sale_payload((a, 1), customer=customer, payments=[{"method": "cash", "amount": "5.00"}]),
            format="json",
        )
        .data["id"]
    )
    url = reverse("sale-pay-debt", args=[sale_id])

    partial = client_for(cashier).post(
        url, {"payments": [{"method": "yape", "amount": "2.00", "reference": "OP-1"}]}, format="json"
    )
    assert partial.status_code == 200, partial.data
    assert partial.data["status"] == "pending"
    assert Decimal(partial.data["balance"]) == Decimal("4.80")
    assert len(partial.data["debt_payments"]) == 1

    done = client_for(cashier).post(url, {"payments": [{"method": "cash", "amount": "4.80"}]}, format="json")
    assert done.data["status"] == "completed"
    assert Decimal(done.data["balance"]) == Decimal("0")


def test_debt_payment_cannot_exceed_balance(client_for, cashier, product_factory):
    a = product_factory(stock=10, price="10.00")
    customer = make_customer(client_for, cashier)
    sale_id = (
        client_for(cashier)
        .post(
            reverse("sale-list"),
            sale_payload((a, 1), customer=customer, payments=[{"method": "cash", "amount": "5.00"}]),
            format="json",
        )
        .data["id"]
    )
    response = client_for(cashier).post(
        reverse("sale-pay-debt", args=[sale_id]),
        {"payments": [{"method": "cash", "amount": "50.00"}]},
        format="json",
    )
    assert response.status_code == 400
    assert "supera el saldo" in str(response.data)


def test_customers_list_shows_debt_and_can_filter_debtors(client_for, cashier, product_factory):
    a = product_factory(stock=10, price="10.00")
    customer = make_customer(client_for, cashier)
    client_for(cashier).post(
        reverse("sale-list"),
        sale_payload((a, 1), customer=customer, payments=[{"method": "cash", "amount": "5.00"}]),
        format="json",
    )
    everyone = client_for(cashier).get(reverse("customer-list")).data["results"]
    assert Decimal(next(c for c in everyone if c["id"] == customer)["debt"]) == Decimal("6.80")

    debtors = client_for(cashier).get(reverse("customer-list"), {"has_debt": "1"}).data["results"]
    assert [c["id"] for c in debtors] == [customer]
