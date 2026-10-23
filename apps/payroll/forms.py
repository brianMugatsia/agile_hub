from django import forms
from django.db.models import Q

from apps.accounts.models import User

from .models import SalaryRecord, WorkerProfile


from apps.accounts.roles import Role

class WorkerProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")
    email = forms.EmailField(label="Email")
    phone_number = forms.CharField(max_length=24, required=False, label="Phone number")

    class Meta:
        model = WorkerProfile
        fields = ["hub", "employee_code", "job_title", "monthly_salary", "hired_on", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["phone_number"].initial = self.instance.user.phone_number

    def save(self, commit=True):
        profile = super().save(commit=False)
        if not profile.user_id:
            email = self.cleaned_data["email"].strip().lower()
            username = email
            base_username = email.split("@")[0]
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=self.cleaned_data["first_name"],
                last_name=self.cleaned_data["last_name"],
                phone_number=self.cleaned_data.get("phone_number", ""),
                role=Role.WORKER,
                is_active=True,
            )
            profile.user = user
        else:
            profile.user.first_name = self.cleaned_data["first_name"]
            profile.user.last_name = self.cleaned_data["last_name"]
            profile.user.email = self.cleaned_data["email"]
            if "phone_number" in self.cleaned_data:
                profile.user.phone_number = self.cleaned_data["phone_number"]
            if commit:
                profile.user.save()
        if commit:
            profile.save()
        return profile


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