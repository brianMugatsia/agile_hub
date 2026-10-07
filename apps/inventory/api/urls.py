from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly
from apps.inventory.models import InventoryBalance, InventoryTransaction

router = DefaultRouter()
register_readonly(router, InventoryBalance, "balances", "inventory-balance")
register_readonly(router, InventoryTransaction, "movements", "inventory-movement")
urlpatterns = router.urls