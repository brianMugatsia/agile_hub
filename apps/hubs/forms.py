from django import forms
from django.core.exceptions import ValidationError
from apps.accounts.roles import Role
from apps.accounts.models import User

from .models import Hub, HubMembership


class HubForm(forms.ModelForm):
    manager_password = forms.CharField(
        label="Manager password",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        required=False,
        help_text="Password for the new manager or to update existing manager's password.",
    )
    new_manager_username = forms.CharField(
        label="New manager username",
        required=False,
        help_text="Fill this to create a brand-new manager account for this hub.",
    )
    new_manager_email = forms.EmailField(
        label="New manager email",
        required=False,
    )
    new_manager_first_name = forms.CharField(
        label="New manager first name",
        required=False,
    )
    new_manager_last_name = forms.CharField(
        label="New manager last name",
        required=False,
    )
    new_manager_phone = forms.CharField(
        label="New manager phone number",
        required=False,
    )

    class Meta:
        model = Hub
        fields = [
            "code",
            "name",
            "region",
            "address",
            "phone_number",
            "manager",
            "manager_password",
            "new_manager_username",
            "new_manager_email",
            "new_manager_first_name",
            "new_manager_last_name",
            "new_manager_phone",
            "status",
        ]
        widgets = {
            "address": forms.TextInput(attrs={"autocomplete": "street-address"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        manager = cleaned_data.get("manager")
        new_username = cleaned_data.get("new_manager_username")
        password = cleaned_data.get("manager_password")

        if manager and new_username:
            raise ValidationError("Choose either an existing manager or create a new manager, not both.")

        if new_username:
            if User.objects.filter(username__iexact=new_username).exists():
                self.add_error("new_manager_username", "A user with this username already exists.")
            if not password:
                self.add_error("manager_password", "A password is required for the new manager account.")
            if not cleaned_data.get("new_manager_email"):
                self.add_error("new_manager_email", "Email is required for the new manager.")
            if not cleaned_data.get("new_manager_first_name") or not cleaned_data.get("new_manager_last_name"):
                self.add_error("new_manager_first_name", "First name and last name are required for the new manager.")

        return cleaned_data

    def save(self, commit=True):
        hub = super().save(commit=False)
        new_username = self.cleaned_data.get("new_manager_username")
        password = self.cleaned_data.get("manager_password")

        if new_username:
            new_user = User.objects.create_user(
                username=new_username,
                email=self.cleaned_data.get("new_manager_email", ""),
                first_name=self.cleaned_data.get("new_manager_first_name", ""),
                last_name=self.cleaned_data.get("new_manager_last_name", ""),
                phone_number=self.cleaned_data.get("new_manager_phone", ""),
                role=Role.HUB_MANAGER,
                password=password,
                hub=hub,
            )
            hub.manager = new_user
        elif hub.manager:
            if password:
                hub.manager.set_password(password)
            if hub.manager.role != Role.HUB_MANAGER:
                hub.manager.role = Role.HUB_MANAGER
            if not hub.manager.hub_id:
                hub.manager.hub = hub
            hub.manager.save()

        if commit:
            hub.save()
            self.save_m2m()
            if hub.manager:
                membership, created = HubMembership.objects.get_or_create(
                    hub=hub,
                    user=hub.manager,
                    defaults={"is_active": True, "title": "Hub Manager"}
                )
                if not membership.is_active:
                    membership.is_active = True
                    membership.save()
        return hub
