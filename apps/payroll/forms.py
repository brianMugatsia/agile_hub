from django import forms
from django.db.models import Q

from apps.accounts.models import User

from .models import SalaryRecord, WorkerProfile


class WorkerProfileForm(forms.ModelForm):
    class Meta:
        model = WorkerProfile
        fields = ["user", "hub", "employee_code", "job_title", "monthly_salary", "hired_on", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "user" in self.fields:
            eligible_workers = User.objects.filter(role="WORKER", is_active=True)
            if self.instance.pk:
                eligible_workers = User.objects.filter(
                    Q(pk=self.instance.user_id) | Q(role="WORKER", is_active=True)
                )
            self.fields["user"].queryset = eligible_workers.order_by("last_name", "first_name")


class WorkerUpdateForm(WorkerProfileForm):
    class Meta(WorkerProfileForm.Meta):
        fields = ["hub", "employee_code", "job_title", "monthly_salary", "hired_on", "is_active"]

    def clean_hub(self):
        hub = self.cleaned_data["hub"]
        if self.instance.pk and self.instance.salary_records.exists() and hub.pk != self.instance.hub_id:
            raise forms.ValidationError(
                "A worker's hub cannot be changed after salary records have been created."
            )
        return hub


class SalaryRecordForm(forms.ModelForm):
    class Meta:
        model = SalaryRecord
        fields = ["worker", "period_start", "period_end", "gross_amount", "deductions", "notes"]
        widgets = {
            "period_start": forms.DateInput(attrs={"type": "date"}),
            "period_end": forms.DateInput(attrs={"type": "date"}),
        }