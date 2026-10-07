from rest_framework.routers import DefaultRouter

from apps.core.api.resources import register_readonly
from apps.payroll.models import SalaryRecord, WorkerProfile

router = DefaultRouter()
register_readonly(router, WorkerProfile, "workers", "worker")
register_readonly(router, SalaryRecord, "salaries", "salary-record")
urlpatterns = router.urls