# Invexa · Backend

API REST de **inventario y punto de venta (POS)** para pequeños comercios: catálogo de productos, control de stock con kardex, ventas con factura en PDF, roles de usuario y dashboard de métricas.

> Frontend (Vue.js): [`invexa-frontend`](../invexa-frontend)

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2_LTS-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.18-A30000)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/tests-37_passing-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-97%25-brightgreen)

## Funcionalidades

- **Autenticación JWT** (access + refresh con rotación), límite de intentos de login y cambio de contraseña.
- **Verificación de correo por código de 6 dígitos** (Gmail SMTP): el admin crea la cuenta inactiva y el dueño del correo la activa con el código y su contraseña. El código se guarda como HMAC, vence en 10 minutos y se invalida tras 5 intentos.
- **Roles con permisos distintos:**

  | Acción | Administrador | Cajero | Bodeguero |
  |---|:-:|:-:|:-:|
  | Ver productos y categorías | ✅ | ✅ | ✅ |
  | Crear y editar productos, categorías y proveedores | ✅ | ❌ | ✅ |
  | Registrar entradas, salidas y ajustes de stock | ✅ | ❌ | ✅ |
  | Registrar ventas y clientes | ✅ | ✅ | ❌ |
  | Ver ventas | Todas | Solo las suyas | ❌ |
  | Anular ventas | ✅ | ❌ | ❌ |
  | Dashboard y exportación de ventas | ✅ | ❌ | ❌ |
  | Reporte de stock bajo y exportación de inventario | ✅ | ❌ | ✅ |
  | Gestión de usuarios | ✅ | ❌ | ❌ |

- **Inventario con kardex:** cada cambio de stock queda registrado como movimiento inmutable (stock anterior y posterior, usuario y nota). El stock no se puede editar directamente.
- **Ventas transaccionales:** bloqueo de filas (`select_for_update`) para que dos cajas no vendan el mismo stock; si falla un producto, se revierte toda la venta.
- **Cálculo de totales:** subtotal, descuento, IGV configurable (18 % por defecto) y cambio en pagos en efectivo.
- **Anulación de ventas** con devolución automática de stock.
- **Factura en PDF** (ReportLab) y **exportación a Excel** (openpyxl) de ventas e inventario.
- **Dashboard:** ingresos, ticket promedio, margen bruto, ventas por día y por método de pago, top 10 de productos, valor del inventario y alertas de stock bajo.
- **Búsqueda, filtros, ordenamiento y paginación** en todos los listados (por ejemplo, buscar por código de barras).
- **Documentación OpenAPI** con DRF-Spectacular (Swagger UI y Redoc).

## Stack

Django 5.2 LTS · Django REST Framework · SimpleJWT · DRF-Spectacular · django-filter · PostgreSQL · ReportLab · openpyxl · pytest · Ruff · GitHub Actions

## Puesta en marcha

Requisitos: Python 3.12+ y PostgreSQL 14+.

1. Crea la base de datos:

   ```sql
   CREATE DATABASE invexa;
   ```

2. Configura el entorno e instala dependencias:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   # source .venv/bin/activate     # Linux / macOS
   pip install -r requirements/dev.txt
   cp .env.example .env            # completa DB_PASSWORD y, si aplica, DB_PORT
   ```

3. Migra, carga datos de ejemplo y levanta el servidor:

   ```bash
   python manage.py migrate
   python manage.py seed_demo
   python manage.py runserver      # 0.0.0.0:3000 por defecto
   ```

La API queda en `http://localhost:3000`.

| Recurso | URL |
|---|---|
| Swagger UI | http://localhost:3000/api/schema/docs/ |
| Redoc | http://localhost:3000/api/schema/redoc/ |
| Esquema OpenAPI | http://localhost:3000/api/schema/ |
| Admin de Django | http://localhost:3000/admin/ |
| Health check | http://localhost:3000/api/health/ |

### Usuarios de demostración

`seed_demo` crea estos usuarios, todos con la contraseña `Invexa2026!`:

| Usuario | Rol |
|---|---|
| `admin` | Administrador |
| `cajero` | Cajero |
| `bodeguero` | Bodeguero |

Para regenerar los datos: `python manage.py seed_demo --reset`.

## Endpoints principales

Todos bajo `/api/`:

| Método | Ruta | Descripción |
|---|---|---|
| POST | `auth/token/` | Obtener access y refresh token |
| POST | `auth/token/refresh/` | Renovar el access token |
| POST | `auth/verify-email/` | Activar cuenta con el código de 6 dígitos y definir contraseña |
| POST | `auth/resend-code/` | Reenviar el código (respuesta genérica) |
| GET / PATCH | `auth/me/` | Perfil del usuario autenticado |
| CRUD | `users/` | Usuarios (solo administrador) |
| CRUD | `categories/`, `suppliers/`, `products/` | Catálogo |
| GET / POST | `stock-movements/` | Kardex y movimientos manuales (`in`, `out`, `adjustment`) |
| CRUD | `customers/` | Clientes |
| GET / POST | `sales/` | Listar y registrar ventas |
| POST | `sales/{id}/cancel/` | Anular venta |
| GET | `sales/{id}/invoice/` | Factura en PDF |
| GET | `reports/dashboard/?date_from=&date_to=` | KPIs |
| GET | `reports/low-stock/` | Productos con stock bajo |
| GET | `reports/sales/export/` | Ventas en Excel |
| GET | `reports/inventory/export/` | Inventario en Excel |

### Ejemplo: registrar una venta

```http
POST /api/sales/
Authorization: Bearer <access>
Content-Type: application/json

{
  "payment_method": "cash",
  "amount_paid": "50.00",
  "discount": "2.00",
  "customer": 1,
  "items": [
    { "product": 3, "quantity": 2 },
    { "product": 7, "quantity": 1 }
  ]
}
```

## Arquitectura

```
config/
  settings.py      Configuración por variables de entorno; ROUTER_APPS
  routers.py       Carga automática del routers.py de cada app (ROUTER_APPS)
  urls.py          URLs principales: admin, /api/ (desde config/routers.py) y docs
apps/
  common/          Modelos abstractos compartidos
  users/           Usuario con rol, permisos por rol, JWT
  inventory/       Categorías, proveedores, productos, kardex
    services.py    ← única vía para modificar stock
  sales/           Clientes, ventas, factura PDF, comando seed_demo
    services.py    ← creación y anulación transaccional de ventas
  reports/         Dashboard y exportaciones a Excel
```

**Rutas:** cada app declara sus endpoints en `routers.py` (con `urlpatterns` o un `router` de DRF). `config/routers.py` recorre `settings.ROUTER_APPS` y los monta bajo `/api/`. Para agregar una app nueva basta con crear su `routers.py` y añadirla a `ROUTER_APPS`.

La lógica de negocio vive en `services.py` y no en las vistas ni en los serializers. Así se puede probar de forma aislada y reutilizar (por ejemplo, desde `seed_demo`).

## Calidad

```bash
pytest --cov            # 37 tests, ~97 % de cobertura
ruff check . && ruff format --check .
python manage.py spectacular --validate --fail-on-warn --file schema.yml
```

El pipeline de GitHub Actions ejecuta lint, verificación de migraciones, validación del esquema OpenAPI y los tests contra PostgreSQL en cada push.
