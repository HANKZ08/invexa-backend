"""Carga datos de demostración: usuarios, catálogo, stock, clientes y ventas.

Uso: python manage.py seed_demo [--sales 80] [--reset]
"""

import math
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import Category, Product, StockMovement, Supplier
from apps.inventory.services import apply_stock_change
from apps.sales.models import Customer, Sale
from apps.sales.services import create_sale
from apps.users.models import User

DEMO_PASSWORD = "Invexa2026!"

USERS = [
    ("admin", "admin@invexa.test", "Carmen", "Salazar", User.Role.ADMIN),
    ("cajero", "cajero@invexa.test", "Luis", "Ramírez", User.Role.CASHIER),
    ("bodeguero", "bodega@invexa.test", "Pedro", "Flores", User.Role.WAREHOUSE),
]

CATALOG = {
    "Herramientas manuales": [
        ("HER-001", "Martillo de uña 16 oz mango de fibra", "18.50", "29.90"),
        ("HER-002", "Destornillador plano 1/4 x 6 in", "4.20", "7.50"),
        ("HER-003", "Destornillador estrella PH2 x 6 in", "4.20", "7.50"),
        ("HER-004", "Alicate universal 8 in", "16.80", "27.00"),
        ("HER-005", "Llave francesa ajustable 10 in", "24.00", "38.50"),
        ("HER-006", "Wincha 5 m x 19 mm", "9.50", "16.90"),
    ],
    "Tornillería y fijación": [
        ("TOR-001", "Tornillo autorroscante 8 x 1 in (caja x100)", "6.40", "11.00"),
        ("TOR-002", "Tornillo para drywall 6 x 1-1/4 in (caja x100)", "7.10", "12.50"),
        ("TOR-003", "Perno hexagonal 3/8 x 2 in galvanizado", "0.55", "1.10"),
        ("TOR-004", "Tuerca hexagonal 3/8 in galvanizada", "0.12", "0.30"),
        ("TOR-005", "Tarugo plástico 1/4 in (bolsa x50)", "2.30", "4.50"),
        ("TOR-006", "Clavo para madera 2-1/2 in (kg)", "4.80", "8.00"),
    ],
    "Electricidad": [
        ("ELE-001", "Cable THW 14 AWG rojo (metro)", "1.10", "2.00"),
        ("ELE-002", "Cable THW 12 AWG negro (metro)", "1.60", "2.80"),
        ("ELE-003", "Interruptor simple empotrable", "5.20", "9.50"),
        ("ELE-004", "Tomacorriente doble con línea a tierra", "7.30", "12.90"),
        ("ELE-005", "Cinta aislante 3/4 in x 20 m", "2.40", "4.50"),
    ],
    "Gasfitería": [
        ("GAS-001", "Tubo PVC agua 1/2 in x 5 m", "7.90", "13.50"),
        ("GAS-002", "Codo PVC 1/2 in x 90°", "0.60", "1.20"),
        ("GAS-003", "Cinta teflón 1/2 in x 10 m", "0.90", "2.00"),
        ("GAS-004", "Pegamento PVC 1/32 gal", "6.50", "11.50"),
    ],
    "Pinturas": [
        ("PIN-001", "Pintura látex blanco 1 gal", "32.00", "49.90"),
        ("PIN-002", "Brocha 2 in cerda natural", "3.80", "7.00"),
        ("PIN-003", "Rodillo antigota 9 in", "9.90", "17.50"),
        ("PIN-004", "Lija de agua N.° 120", "0.80", "1.50"),
    ],
}

SUPPLIERS = [
    ("Distribuidora Ferretera del Sur S.A.C.", "20512345678", "Rosa Quispe"),
    ("Importaciones Industriales Lima E.I.R.L.", "20601234561", "Jorge Huamán"),
    ("Eléctricos y Conductores Perú S.A.", "20487654329", "Lucía Mendoza"),
]

CUSTOMERS = [
    ("Juan Pérez Mamani", "45781236"),
    ("Constructora Andina S.A.C.", "20556677881"),
    ("Taller Mecánico Los Olivos", "10457812364"),
    ("María Rojas Cárdenas", "70123458"),
]


def _payments_for(method: str, items) -> list[dict]:
    """Demo: la mitad de las ventas se pagan en dos medios (efectivo y Yape)."""
    from django.conf import settings

    total = sum(i["product"].sale_price * i["quantity"] for i in items) * (
        1 + Decimal(str(settings.INVEXA_TAX_RATE))
    )
    total = Decimal(str(round(total, 2)))
    if method == Sale.PaymentMethod.CASH:
        return [{"method": "cash", "amount": Decimal(math.ceil(total / 10) * 10), "reference": ""}]
    if method == Sale.PaymentMethod.CARD:
        return [{"method": "card", "amount": total, "reference": f"POS-{abs(hash(str(total))) % 10**6:06d}"}]
    if method == Sale.PaymentMethod.TRANSFER:
        return [
            {"method": "transfer", "amount": total, "reference": f"TRF-{abs(hash(str(total))) % 10**6:06d}"}
        ]
    yape = (total / 2).quantize(Decimal("0.01"))
    return [
        {"method": "yape", "amount": yape, "reference": f"YAPE-{abs(hash(str(yape))) % 10**6:06d}"},
        {"method": "cash", "amount": total - yape + Decimal("10"), "reference": ""},
    ]


def _cash_tendered(items) -> Decimal:
    """Monto en efectivo realista: el total redondeado hacia arriba a la decena."""
    from django.conf import settings

    total = sum(i["product"].sale_price * i["quantity"] for i in items) * (
        1 + Decimal(str(settings.INVEXA_TAX_RATE))
    )
    return Decimal(math.ceil(total / 10) * 10)


class Command(BaseCommand):
    help = "Carga datos de demostración para Invexa."

    def add_arguments(self, parser):
        parser.add_argument("--sales", type=int, default=80, help="Número de ventas a generar.")
        parser.add_argument(
            "--reset", action="store_true", help="Borra los datos de negocio antes de cargar."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(42)

        if options["reset"]:
            StockMovement.objects.all().delete()
            Sale.objects.all().delete()
            Customer.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Supplier.objects.all().delete()

        users = {}
        for username, email, first, last, role in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "first_name": first, "last_name": last, "role": role},
            )
            if created:
                user.is_staff = role == User.Role.ADMIN
                user.is_superuser = role == User.Role.ADMIN
                user.set_password(DEMO_PASSWORD)
                user.email_verified_at = timezone.now()
                user.save()
            users[role] = user

        if Product.objects.exists():
            self.stdout.write(self.style.WARNING("Ya hay productos; usa --reset para regenerar."))
            return

        suppliers = [
            Supplier.objects.create(name=n, tax_id=t, contact_name=c, email=f"ventas{i}@proveedor.test")
            for i, (n, t, c) in enumerate(SUPPLIERS, start=1)
        ]

        warehouse = users[User.Role.WAREHOUSE]
        products = []
        for cat_name, items in CATALOG.items():
            category = Category.objects.create(name=cat_name)
            for sku, name, cost, price in items:
                product = Product.objects.create(
                    sku=sku,
                    barcode=f"775{rng.randint(10**9, 10**10 - 1)}",
                    name=name,
                    category=category,
                    supplier=rng.choice(suppliers),
                    cost_price=Decimal(cost),
                    sale_price=Decimal(price),
                    min_stock=rng.choice([5, 10, 15]),
                )
                apply_stock_change(
                    product=product,
                    quantity=rng.randint(40, 150),
                    movement_type=StockMovement.MovementType.IN,
                    user=warehouse,
                    note="Inventario inicial",
                )
                products.append(product)

        customers = [Customer.objects.create(name=n, document_id=d) for n, d in CUSTOMERS]

        cashier = users[User.Role.CASHIER]
        now = timezone.now()
        created_sales = 0
        for _ in range(options["sales"]):
            available = [p for p in Product.objects.filter(stock__gt=3)]
            if not available:
                break
            picks = rng.sample(available, k=min(len(available), rng.randint(1, 4)))
            items = [{"product": p, "quantity": rng.randint(1, 3)} for p in picks]
            method = rng.choice(Sale.PaymentMethod.values)
            sale = create_sale(
                cashier=cashier,
                items=items,
                payments=_payments_for(method, items),
                customer=rng.choice([None, None, *customers]),
            )
            moment = now - timedelta(
                days=rng.randint(0, 29), hours=rng.randint(0, 10), minutes=rng.randint(0, 59)
            )
            Sale.objects.filter(pk=sale.pk).update(created_at=moment)
            StockMovement.objects.filter(sale=sale).update(created_at=moment)
            created_sales += 1

        # Deja algunos productos con stock bajo para que el dashboard muestre alertas
        for product in rng.sample(products, k=3):
            product.refresh_from_db()
            target = rng.randint(0, product.min_stock)
            if product.stock > target:
                apply_stock_change(
                    product=product,
                    quantity=target - product.stock,
                    movement_type=StockMovement.MovementType.OUT,
                    user=warehouse,
                    note="Merma (datos demo)",
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Listo: {len(products)} productos, {len(customers)} clientes, {created_sales} ventas. "
                f"Usuarios: admin / cajero / bodeguero (contraseña: {DEMO_PASSWORD})"
            )
        )
