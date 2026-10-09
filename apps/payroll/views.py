from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from apps.audit.services import record_event
from apps.core.generic import (
    ProtectedCreateView,
    ProtectedUpdateView,
    ScopedModelListView,
    hubs_for_user,
)
from apps.core.exports import ScopedModelExportView
from apps.payroll.services import approve_salary, pay_salary

from .forms import SalaryRecordForm, WorkerProfileForm, WorkerUpdateForm
from .models import SalaryRecord, WorkerProfile


class WorkerListView(ScopedModelListView):
    model = WorkerProfile
    page_title = "Workers"
    columns = (
        {"label": "Employee ID", "field": "employee_code"},
        {"label": "Name", "field": "user__display_name"},
        {"label": "Hub", "field": "hub__name"},
        {"label": "Position", "field": "job_title"},
        {"label": "Status", "field": "is_active"},
    )
    search_fields = ("employee_code", "user__first_name", "user__last_name", "job_title")
    create_url_name = "payroll:worker_create"
    create_label = "Add worker"
    create_permission = "payroll.add_workerprofile"
    row_edit_url_name = "payroll:worker_edit"
    row_edit_permission = "payroll.change_workerprofile"
    filter_hub = True


class WorkerCreateView(ProtectedCreateView):
    model = WorkerProfile
    form_class = WorkerProfileForm
    page_title = "Add worker"
    success_url_name = "payroll:worker_list"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["hub"].queryset = hubs_for_user(self.request.user)
        return form


class WorkerUpdateView(ProtectedUpdateView):
    model = WorkerProfile
    form_class = WorkerUpdateForm
    page_title = "Edit worker"
    success_url_name = "payroll:worker_list"
    cancel_url_name = "payroll:worker_list"

    def get_queryset(self):
        return WorkerProfile.objects.filter(hub__in=hubs_for_user(self.request.user))

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["hub"].queryset = hubs_for_user(self.request.user)
        return form


class SalaryListView(ScopedModelListView):
    model = SalaryRecord
    template_name = "payroll/salary_list.html"
    page_title = "Workers' salaries"
    columns = (
        {"label": "Worker", "field": "worker__user__display_name"},
        {"label": "Period", "field": "period_start"},
        {"label": "Gross", "field": "gross_amount"},
        {"label": "Net", "field": "net_amount"},
        {"label": "Status", "field": "status"},
    )
    date_filter_field = "period_start"
    filter_fields = (("status", SalaryRecord.Status.choices),)
    filter_hub = True
    create_url_name = "payroll:salary_create"
    create_label = "Prepare salary"
    create_permission = "payroll.add_salaryrecord"
    export_url_name = "payroll:salary_export"


class SalaryExportView(ScopedModelExportView):
    list_view_class = SalaryListView


class SalaryCreateView(ProtectedCreateView):
    model = SalaryRecord
    form_class = SalaryRecordForm
    page_title = "Prepare salary"
    success_url_name = "payroll:salary_list"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["worker"].queryset = WorkerProfile.objects.filter(
            hub__in=hubs_for_user(self.request.user)
        ).order_by("employee_code")
        return form

    def form_valid(self, form):
        form.instance.status = SalaryRecord.Status.PENDING
        self.object = form.save()
        record_event(
            action="payroll.salary_submitted",
            summary=f"Salary submitted for approval: {self.object.worker}",
            actor=self.request.user,
            target=self.object,
            changes={"net_amount": str(self.object.net_amount)},
        )
        messages.success(self.request, "Salary submitted for approval.")
        return redirect(self.get_success_url())


class SalaryActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    service = None
    permission_required = ""
    success_message = "Salary record updated."

    def post(self, request, pk):
        try:
            self.service(salary_id=pk, actor=request.user)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, self.success_message)
        return redirect("payroll:salary_list")


class ApproveSalaryView(SalaryActionView):
    service = staticmethod(approve_salary)
    permission_required = "payroll.approve_salaryrecord"
    success_message = "Salary approved."


class PaySalaryView(SalaryActionView):
    service = staticmethod(pay_salary)
    permission_required = "payroll.pay_salaryrecord"
    success_message = "Salary marked as paid."