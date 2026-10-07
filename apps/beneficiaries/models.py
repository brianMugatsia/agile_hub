from django.conf import settings
from django.db import models


class BeneficiaryProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="beneficiary_profile"
    )
    phone_number = models.CharField(max_length=24, blank=True)
    national_id = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=255, blank=True)
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="beneficiaries"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]

    def __str__(self):
        return self.user.display_name


class Business(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    beneficiary = models.ForeignKey(
        BeneficiaryProfile, on_delete=models.PROTECT, related_name="businesses"
    )
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="businesses"
    )
    name = models.CharField(max_length=180)
    business_type = models.CharField(max_length=100, blank=True)
    registration_number = models.CharField(max_length=80, blank=True)
    phone_number = models.CharField(max_length=24, blank=True)
    address = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name