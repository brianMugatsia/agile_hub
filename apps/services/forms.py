from django import forms
from django.utils import timezone

from apps.hubs.models import Hub
from apps.hubs.permissions import hubs_for_user
from apps.members.models import Business, MemberProfile

from .models import HubResource, ServiceBooking, ServiceType


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
    class Meta:
        model = HubResource
        fields = [
            "hub",
            "service_type",
            "name",
            "code",
            "capacity",
            "capacity_unit",
            "status",
            "operator_name",
            "operator_phone",
            "hourly_or_daily_cost",
            "notes",
        ]

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

    class Meta:
        model = ServiceBooking
        fields = [
            "hub",
            "service_type",
            "resource",
            "member",
            "business",
            "customer_name",
            "customer_phone",
            "start_date",
            "end_date",
            "quantity",
            "unit_rate",
            "notes",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
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
            self.fields["business"].queryset = Business.objects.filter(status=Business.Status.ACTIVE)


class BookingActionForm(forms.Form):
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    payment_reference = forms.CharField(required=False, max_length=80)
