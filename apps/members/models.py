from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class MemberProfile(models.Model):
    class CustomerType(models.TextChoices):
        LEAD = "LEAD", "Lead"
        FARMER = "FARMER", "Farmer"
        ORGANIZATION = "ORGANIZATION", "Organization"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="member_profile"
    )
    name = models.CharField(max_length=160, blank=True, help_text="Full name for leads without user account")
    customer_type = models.CharField(
        max_length=20, choices=CustomerType.choices, default=CustomerType.FARMER, db_index=True
    )
    crops = models.CharField(max_length=255, blank=True, help_text="Crops grown e.g. Maize, Beans, Coffee")
    phone_number = models.CharField(max_length=24, blank=True)
    national_id = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=255, blank=True)
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="members"
    )
    services = models.ManyToManyField(
        "services.ServiceType", blank=True, related_name="members"
    )
    notes = models.TextField(blank=True)
    loop_feedback = models.TextField(blank=True, help_text="Feedback loop notes and follow-ups")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["customer_type", "user__last_name", "user__first_name", "name"]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        if self.user:
            return self.user.display_name
        return self.name or self.phone_number or f"Customer #{self.pk}"

    @property
    def is_lead(self):
        return self.customer_type == self.CustomerType.LEAD

    @property
    def is_farmer(self):
        return self.customer_type == self.CustomerType.FARMER

    @property
    def is_organization(self):
        return self.customer_type == self.CustomerType.ORGANIZATION

    def get_absolute_url(self):
        if self.is_lead or self.customer_type == self.CustomerType.ORGANIZATION:
            return reverse("members:customer_detail", args=[self.pk])
        return reverse("members:detail", args=[self.pk])


class Business(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    member = models.ForeignKey(
        MemberProfile, on_delete=models.PROTECT, related_name="businesses"
    )
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="businesses"
    )
    name = models.CharField(max_length=180)
    business_type = models.CharField(max_length=100, blank=True)
    registration_number = models.CharField(max_length=80, blank=True)
    phone_number = models.CharField(max_length=24, blank=True)
    address = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))]
    )
    is_paid = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def payment_status_display(self):
        if self.is_paid:
            return "Paid"
        return "Not Paid"
