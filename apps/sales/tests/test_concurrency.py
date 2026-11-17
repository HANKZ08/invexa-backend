import threading

import pytest
from django.db import connection

from apps.sales.models import Sale
from apps.sales.services import create_sale


@pytest.mark.django_db(transaction=True)
def test_concurrent_sales_on_different_products_both_succeed(cashier, product_factory):
    """Dos cajas venden a la vez productos distintos: ambas ventas deben guardarse.

    Regresión: ``Sale.number`` era único con valor inicial ``""``; la segunda
    transacción chocaba con la primera antes de que se asignara el número.
    """
    a = product_factory(stock=5)
    b = product_factory(stock=5)
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def sell(product):
        try:
            barrier.wait()
            create_sale(
                cashier=cashier,
                items=[{"product": product, "quantity": 1}],
                payments=[{"method": "cash", "amount": "1000"}],
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=sell, args=(p,)) for p in (a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert Sale.objects.count() == 2
    assert sorted(Sale.objects.values_list("number", flat=True)) == sorted(
        f"V-{pk:06d}" for pk in Sale.objects.values_list("pk", flat=True)
    )
