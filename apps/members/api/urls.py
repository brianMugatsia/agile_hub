from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly
from apps.members.models import MemberProfile, Business

router = DefaultRouter()
register_readonly(router, MemberProfile, "profiles", "member-profile")
register_readonly(router, Business, "businesses", "member-business")
urlpatterns = router.urls