from django import forms

from apps.accounts.models import User

from .models import SalaryRecord, WorkerProfile


class WorkerProfileForm(forms.ModelForm):
    class Meta:
        model = WorkerProfile
        fields = ["user", "hub", "employee_code", "job_title", "monthly_salary", "hired_on", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(role="WORKER", is_active=True).order_by(
            "last_name", "first_name"
        )


class SalaryRecordForm(forms.ModelForm):
    class Meta:
        model = SalaryRecord
        fields = ["worker", "period_start", "period_end", "gross_amount", "deductions", "notes"]
        widgets = {
            "period_start": forms.DateInput(attrs={"type": "date"}),
            "period_end": forms.DateInput(attrs={"type": "date"}),
        }