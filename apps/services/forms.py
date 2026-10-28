from django import forms
from django.utils import timezone

from apps.hubs.models import Hub
from apps.hubs.permissions import hubs_for_user
from apps.members.models import Business, MemberProfile

from .models import HubResource, ServiceBooking, ServiceProvider, ServiceProviderStatus, ServiceType, ServiceCategory


class ServiceTypeForm(forms.ModelForm):
    class Meta:
        model = ServiceType
        fields = [
            "code",
            "name",
            "category",
            "pricing_unit",
            "standard_rate",
            "description",
            "is_active",
        ]


class HubResourceForm(forms.ModelForm):
    total_count = forms.IntegerField(
        initial=1,
        min_value=0,
        label="Total Equipment",
        widget=forms.NumberInput(attrs={"class": "input", "placeholder": "e.g. 10"})
    )
    available_count = forms.IntegerField(
        initial=1,
        min_value=0,
        label="Available Equipment",
        widget=forms.NumberInput(attrs={"class": "input", "placeholder": "e.g. 8"})
    )
    in_use_count = forms.IntegerField(
        initial=0,
        min_value=0,
        label="In Use Equipment",
        widget=forms.NumberInput(attrs={"class": "input", "placeholder": "e.g. 2"})
    )

    class Meta:
        model = HubResource
        fields = [
            "hub",
            "service_type",
            "name",
            "total_count",
            "available_count",
            "in_use_count",
            "operator_name",
            "operator_phone",
            "hourly_or_daily_cost",
            "notes",
        ]
        widgets = {
            "hub": forms.Select(attrs={"class": "select"}),
            "service_type": forms.Select(attrs={"class": "select"}),
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Tractor 01"}),
            "operator_name": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. John Doe"}),
            "operator_phone": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. 0712345678"}),
            "hourly_or_daily_cost": forms.NumberInput(attrs={"class": "input", "step": "0.01", "placeholder": "0.00"}),
            "notes": forms.Textarea(attrs={"class": "input", "rows": 3, "placeholder": "Optional notes or equipment details..."}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["hub"].queryset = hubs_for_user(user, active_only=True)
            user_hub = getattr(user, "hub", None)
            if user_hub and not getattr(self.instance, "hub_id", None):
                self.fields["hub"].initial = user_hub



class ServiceBookingForm(forms.ModelForm):
    start_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        initial=timezone.now,
    )
    end_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        initial=lambda: timezone.now() + timezone.timedelta(days=1),
    )
    member = forms.ModelChoiceField(
        queryset=MemberProfile.objects.all(),
        required=True,
        label="Customer / Client",
        help_text="Select a registered customer from the system.",
        widget=forms.Select(attrs={"class": "select", "data-searchable-select": "true"}),
    )
    unit_rate = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label="Unit Rate (per quantity/unit)",
        help_text="The price charged per unit (e.g. per Kg, per Acre, per Day) for this service. Defaults to the service catalogue standard rate.",
        widget=forms.NumberInput(attrs={"class": "input", "step": "0.01"}),
    )

    class Meta:
        model = ServiceBooking
        fields = [
            "hub",
            "service_type",
            "resource",
            "service_provider",
            "member",
            "status",
            "payment_status",
            "start_date",
            "end_date",
            "quantity",
            "unit_rate",
            "notes",
        ]
        widgets = {
            "service_provider": forms.Select(attrs={"class": "select", "data-searchable-select": "true"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get("status"):
            self.initial["status"] = ServiceBooking.Status.SCHEDULED
        if not self.initial.get("payment_status"):
            self.initial["payment_status"] = ServiceBooking.PaymentStatus.PENDING

        if user:
            permitted_hubs = hubs_for_user(user, active_only=True)
            self.fields["hub"].queryset = permitted_hubs
            user_hub = getattr(user, "hub", None)
            if user_hub:
                self.fields["hub"].initial = user_hub
                self.fields["resource"].queryset = HubResource.objects.filter(
                    hub=user_hub, status__in=[HubResource.Status.AVAILABLE, HubResource.Status.IN_USE]
                )
            elif getattr(self.instance, "hub_id", None):
                self.fields["resource"].queryset = HubResource.objects.filter(hub=self.instance.hub_id)
            else:
                self.fields["resource"].queryset = HubResource.objects.filter(hub__in=permitted_hubs)

            self.fields["member"].queryset = MemberProfile.objects.select_related("user").all()
            self.fields["service_provider"].queryset = ServiceProvider.objects.filter(status=ServiceProviderStatus.ACTIVE)


class BookingActionForm(forms.Form):
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    payment_reference = forms.CharField(required=False, max_length=80)


class ServiceProviderForm(forms.ModelForm):
    service_category = forms.ChoiceField(
        choices=[("", "---------")] + list(ServiceCategory.choices),
        required=False,
        label="Service Category",
        widget=forms.Select(attrs={"class": "select"}),
    )

    class Meta:
        model = ServiceProvider
        fields = [
            "provider_type",
            "member",
            "name",
            "phone_number",
            "email",
            "address",
            "service_category",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["member"].queryset = MemberProfile.objects.select_related("user").all()
        self.fields["member"].required = False
        self.fields["name"].required = False

    def clean(self):
        cleaned_data = super().clean()
        provider_type = cleaned_data.get("provider_type")
        member = cleaned_data.get("member")
        name = (cleaned_data.get("name") or "").strip()

        if provider_type == "INTERNAL":
            if not member:
                raise forms.ValidationError({"member": "Internal service providers must be associated with an existing member record."})
            if not name:
                cleaned_data["name"] = member.display_name
            if not cleaned_data.get("phone_number"):
                cleaned_data["phone_number"] = member.phone_number
            if not cleaned_data.get("email") and member.user:
                cleaned_data["email"] = member.user.email
        elif provider_type == "EXTERNAL":
            if member:
                raise forms.ValidationError({"member": "External service providers must not be associated with a member record."})
            if not name:
                raise forms.ValidationError({"name": "Name is required for external service providers."})
        return cleaned_data


class ServiceProviderActionForm(forms.Form):
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
