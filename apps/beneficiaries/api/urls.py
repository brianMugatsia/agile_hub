from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly
from apps.beneficiaries.models import BeneficiaryProfile, Business

router = DefaultRouter()
register_readonly(router, BeneficiaryProfile, "profiles", "beneficiary-profile")
register_readonly(router, Business, "businesses", "beneficiary-business")
urlpatterns = router.urls