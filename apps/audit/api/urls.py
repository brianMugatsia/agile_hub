from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly
from apps.audit.models import AuditLog

router = DefaultRouter()
register_readonly(router, AuditLog, "events", "audit-event")
urlpatterns = router.urls