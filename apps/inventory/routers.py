from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, ProductViewSet, StockMovementViewSet, SupplierViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("products", ProductViewSet, basename="product")
router.register("stock-movements", StockMovementViewSet, basename="stock-movement")

urlpatterns = router.urls
