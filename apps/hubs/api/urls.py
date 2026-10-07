from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly
from apps.hubs.models import Hub, HubMembership

router = DefaultRouter()
register_readonly(router, Hub, "hubs", "hub")
register_readonly(router, HubMembership, "memberships", "hub-membership")
urlpatterns = router.urls