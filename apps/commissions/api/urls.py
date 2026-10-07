from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly
from apps.commissions.models import CommissionSetting, SalesAgentCommission

router = DefaultRouter()
register_readonly(router, CommissionSetting, "settings", "commission-setting")
register_readonly(router, SalesAgentCommission, "commissions", "agent-commission")
urlpatterns = router.urls