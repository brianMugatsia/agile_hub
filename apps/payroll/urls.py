from django.urls import path

from .views import (
    ApproveSalaryView,
    PaySalaryView,
    SalaryCreateView,
    SalaryListView,
    WorkerCreateView,
    WorkerListView,
)

app_name = "payroll"

urlpatterns = [
    path("workers/", WorkerListView.as_view(), name="worker_list"),
    path("workers/create/", WorkerCreateView.as_view(), name="worker_create"),
    path("salaries/", SalaryListView.as_view(), name="salary_list"),
    path("salaries/create/", SalaryCreateView.as_view(), name="salary_create"),
    path("salaries/<int:pk>/approve/", ApproveSalaryView.as_view(), name="salary_approve"),
    path("salaries/<int:pk>/pay/", PaySalaryView.as_view(), name="salary_pay"),
]