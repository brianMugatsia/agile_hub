from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly
from apps.notifications.models import Notification

router = DefaultRouter()
register_readonly(router, Notification, "notifications", "notification")
urlpatterns = router.urls