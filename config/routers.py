from importlib import import_module

from django.conf import settings


# Reúne las rutas de <app>.routers de cada app listada en settings.ROUTER_APPS.
# Cada routers.py debe exponer urlpatterns o un router de DRF.
def load_router_urls(apps: list[str]) -> list:
    patterns = []
    for app in apps:
        try:
            module = import_module(f"{app}.routers")
        except ModuleNotFoundError as exc:
            if exc.name == f"{app}.routers":
                continue
            raise

        if hasattr(module, "urlpatterns"):
            patterns += module.urlpatterns
            continue

        router = getattr(module, "router", None)
        if router is not None and hasattr(router, "urls"):
            patterns += router.urls
            continue

        raise RuntimeError(f"{app}.routers debe definir urlpatterns o router")
    return patterns


api_urlpatterns = load_router_urls(settings.ROUTER_APPS)
