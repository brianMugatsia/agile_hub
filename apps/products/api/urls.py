from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly
from apps.products.models import Product, ProductPriceHistory

router = DefaultRouter()
register_readonly(router, Product, "products", "product")
register_readonly(router, ProductPriceHistory, "price-history", "product-price-history")
urlpatterns = router.urls