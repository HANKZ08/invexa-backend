from decimal import Decimal

import pytest
from django.urls import reverse

from apps.sales.services import cancel_sale, create_sale

pytestmark = pytest.mark.django_db

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def sales_data(cashier, admin_user, product_factory):
    a = product_factory(stock=20, cost="1.00", price="2.00", name="A")
    b = product_factory(stock=3, cost="5.00", price="8.00", min_stock=5, name="B")
    create_sale(
        cashier=cashier,
        items=[{"product": a, "quantity": 5}],
        payments=[{"method": "cash", "amount": "1000"}],
    )
    create_sale(
        cashier=cashier,
        items=[{"product": b, "quantity": 1}],
        payments=[{"method": "cash", "amount": "1000"}],
    )
    cancelled = create_sale(
        cashier=cashier,
        items=[{"product": a, "quantity": 1}],
        payments=[{"method": "cash", "amount": "1000"}],
    )
    cancel_sale(sale=cancelled, user=admin_user, reason="test")
    return a, b


def test_dashboard_kpis(client_for, admin_user, sales_data):
    response = client_for(admin_user).get(reverse("report-dashboard"))
    assert response.status_code == 200, response.data
    summary = response.data["summary"]
    assert summary["sales_count"] == 2
    assert summary["cancelled_count"] == 1
    assert summary["units_sold"] == 6
    # (10 + 8) * 1.18 = 21.24
    assert Decimal(summary["revenue"]) == Decimal("21.24")
    # margen: 5 * (2-1) + 1 * (8-5) = 8
    assert Decimal(summary["gross_profit"]) == Decimal("8.00")
    assert response.data["inventory"]["low_stock_count"] == 1
    assert response.data["top_products"][0]["product_name"] == "A"
    assert len(response.data["sales_by_day"]) == 1


def test_dashboard_invalid_range(client_for, admin_user):
    response = client_for(admin_user).get(
        reverse("report-dashboard"), {"date_from": "2026-02-01", "date_to": "2026-01-01"}
    )
    assert response.status_code == 400


def test_dashboard_is_admin_only(client_for, cashier, warehouse_user):
    assert client_for(cashier).get(reverse("report-dashboard")).status_code == 403
    assert client_for(warehouse_user).get(reverse("report-dashboard")).status_code == 403


def test_low_stock_report_for_warehouse(client_for, warehouse_user, sales_data):
    response = client_for(warehouse_user).get(reverse("report-low-stock"))
    assert response.status_code == 200
    assert [p["name"] for p in response.data] == ["B"]


@pytest.mark.parametrize("url_name", ["report-sales-export", "report-inventory-export"])
def test_excel_exports(client_for, admin_user, sales_data, url_name):
    response = client_for(admin_user).get(reverse(url_name))
    assert response.status_code == 200
    assert response["Content-Type"] == XLSX
    assert response.content[:2] == b"PK"  # los .xlsx son archivos zip


def test_openapi_schema_is_served(api_client):
    response = api_client.get(reverse("schema"))
    assert response.status_code == 200
    assert b"Invexa API" in response.content
