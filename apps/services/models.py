import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class ServiceCategory(models.TextChoices):
    RIPENING = "RIPENING", "Produce Ripening"
    HARVESTING = "HARVESTING", "Harvesting & Machinery Hire"
    PROCESSING = "PROCESSING", "Processing & Milling"
    STORAGE = "STORAGE", "Cold & Dry Storage"
    TRANSPORT = "TRANSPORT", "Transport & Haulage"
    AGRONOMY = "AGRONOMY", "Agronomy & Soil Testing"
    PACKAGING = "PACKAGING", "Grading, Sorting & Packaging"
    IRRIGATION = "IRRIGATION", "Irrigation & Water Management"
    EXTENSION = "EXTENSION", "Farmer Training & Extension"
    FINANCIAL = "FINANCIAL", "Financial Services & Insurance"
    OTHER = "OTHER", "Other Service"


class ServicePricingUnit(models.TextChoices):
    PER_KG = "PER_KG", "Per Kg"
    PER_CRATE = "PER_CRATE", "Per Crate/Box"
    PER_ACRE = "PER_ACRE", "Per Acre"
    PER_HOUR = "PER_HOUR", "Per Hour"
    PER_DAY = "PER_DAY", "Per Day"
    FIXED = "FIXED", "Fixed Charge"


class ProviderType(models.TextChoices):
    INTERNAL = "INTERNAL", "Internal"
    EXTERNAL = "EXTERNAL", "External"


class ServiceProviderStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    DORMANT = "DORMANT", "Dormant"
    SUSPENDED = "SUSPENDED", "Suspended"
    INACTIVE = "INACTIVE", "Inactive"


class ServiceType(models.Model):
    """Catalog of services offered by hubs (e.g. Banana Ripening, Combine Harvester Hire)."""

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=160)
    category = models.CharField(
        max_length=24, choices=ServiceCategory.choices, default=ServiceCategory.OTHER, db_index=True
    )
    pricing_unit = models.CharField(
        max_length=24, choices=ServicePricingUnit.choices, default=ServicePricingUnit.PER_DAY
    )
    standard_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def get_absolute_url(self):
        return reverse("services:service_type_detail", kwargs={"pk": self.pk})


class ServiceProvider(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_type = models.CharField(
        max_length=16, choices=ProviderType.choices, default=ProviderType.INTERNAL, db_index=True
    )
    member = models.ForeignKey(
        "members.MemberProfile",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="service_providers"
    )
    name = models.CharField(max_length=160)
    phone_number = models.CharField(max_length=24, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    service_category = models.CharField(
        max_length=32, blank=True, db_index=True
    )
    status = models.CharField(
        max_length=16, choices=ServiceProviderStatus.choices, default=ServiceProviderStatus.ACTIVE, db_index=True
    )
    suspension_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        permissions = [
            ("suspend_serviceprovider", "Can suspend a service provider"),
            ("reactivate_serviceprovider", "Can reactivate a service provider"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(provider_type="INTERNAL", member__isnull=False) |
                    models.Q(provider_type="EXTERNAL")
                ),
                name="service_provider_internal_member_required"
            )
        ]
        indexes = [
            models.Index(fields=["provider_type", "status"]),
        ]

    def clean(self):
        super().clean()
        if self.provider_type == ProviderType.INTERNAL and not self.member_id:
            raise ValidationError({"member": "Internal service providers must be associated with an existing member record."})
        if self.provider_type == ProviderType.EXTERNAL and self.member_id:
            raise ValidationError({"member": "External service providers must not be associated with a member record."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()} - {self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("services:provider_detail", kwargs={"pk": self.pk})

    @property
    def provider_type_display(self):
        return self.get_provider_type_display()

    @property
    def service_category_display(self):
        if not self.service_category:
            return "General"
        st = ServiceType.objects.filter(code=self.service_category).first()
        if st:
            return st.name
        cat_choices = dict(ServiceCategory.choices)
        if self.service_category in cat_choices:
            return cat_choices[self.service_category]
        return self.service_category

    @property
    def status_display(self):
        return self.get_status_display()

    @property
    def is_active(self):
        return self.status == ServiceProviderStatus.ACTIVE

    @property
    def is_suspended(self):
        return self.status == ServiceProviderStatus.SUSPENDED

    @property
    def is_dormant(self):
        return self.status == ServiceProviderStatus.DORMANT

    @property
    def payment_status_display(self):
        if hasattr(self, "commissions") and self.commissions.filter(status="PAID").exists():
            return "Paid"
        if hasattr(self, "commissions") and self.commissions.exists():
            return "Partial / Pending"
        return "No Records"


class HubResource(models.Model):
    """Specific physical machine, ripening room, or equipment stationed at a hub."""

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        IN_USE = "IN_USE", "In Use / Booked"
        MAINTENANCE = "MAINTENANCE", "Under Maintenance"
        RETIRED = "RETIRED", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hub = models.ForeignKey("hubs.Hub", on_delete=models.PROTECT, related_name="service_resources")
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name="resources")
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40, blank=True)
    total_count = models.PositiveIntegerField(default=1, help_text="Total number of this equipment.")
    available_count = models.PositiveIntegerField(default=1, help_text="Number of equipment available.")
    in_use_count = models.PositiveIntegerField(default=0, help_text="Number of equipment currently in use.")
    capacity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Maximum batch weight, acreage per day, or volume capacity.",
    )
    capacity_unit = models.CharField(max_length=32, default="units", help_text="e.g. kg, crates, acres/day, units")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    operator_name = models.CharField(max_length=120, blank=True, help_text="Assigned driver, technician, or supervisor.")
    operator_phone = models.CharField(max_length=24, blank=True)
    hourly_or_daily_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Operating or maintenance cost rate.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hub__name", "name"]
        constraints = [
            models.UniqueConstraint(fields=["hub", "code"], name="unique_hub_resource_code")
        ]

    def clean(self):
        super().clean()
        if not self.code and self.hub_id:
            count = HubResource.objects.filter(hub=self.hub).count() + 1
            self.code = f"EQ-{count:03d}"
            while HubResource.objects.filter(hub=self.hub, code=self.code).exists():
                count += 1
                self.code = f"EQ-{count:03d}"
        if self.available_count > self.total_count:
            self.available_count = self.total_count
        if self.in_use_count > self.total_count:
            self.in_use_count = self.total_count
        if (self.available_count + self.in_use_count) > self.total_count:
            self.available_count = max(0, self.total_count - self.in_use_count)

    def __str__(self):
        return f"{self.hub.name}: {self.name} [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def operator_display(self):
        if self.operator_name and self.operator_phone:
            return f"{self.operator_name} ({self.operator_phone})"
        return self.operator_name or self.operator_phone or "—"

    def get_absolute_url(self):
        return reverse("services:resource_detail", kwargs={"pk": self.pk})


class ServiceBooking(models.Model):
    """A scheduled or active service engagement (e.g. banana ripening batch, combine harvester job)."""

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending Payment"
        PAID = "PAID", "Paid"
        INVOICED = "INVOICED", "Invoiced"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hub = models.ForeignKey("hubs.Hub", on_delete=models.PROTECT, related_name="service_bookings")
    resource = models.ForeignKey(HubResource, on_delete=models.PROTECT, related_name="bookings")
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name="bookings")
    service_provider = models.ForeignKey(
        ServiceProvider, on_delete=models.PROTECT, null=True, blank=True, related_name="bookings"
    )
    member = models.ForeignKey(
        "members.MemberProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="service_bookings"
    )
    business = models.ForeignKey(
        "members.Business", on_delete=models.SET_NULL, null=True, blank=True, related_name="service_bookings"
    )
    customer_name = models.CharField(max_length=160, blank=True)
    customer_phone = models.CharField(max_length=24, blank=True)
    start_date = models.DateTimeField(db_index=True)
    end_date = models.DateTimeField(db_index=True)
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Volume, weight (kg), or duration (hours/days/acres) serviced.",
    )
    unit_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    payment_status = models.CharField(
        max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.PENDING, db_index=True
    )
    payment_reference = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_service_bookings",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        permissions = [
            ("can_start_booking", "Can start service booking"),
            ("can_complete_booking", "Can complete service booking"),
            ("can_cancel_booking", "Can cancel service booking"),
            ("can_record_payment", "Can record booking payment"),
        ]
        indexes = [
            models.Index(fields=["hub", "status", "-start_date"]),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError({"end_date": "Booking end time must be after start time."})
        if self.resource_id and self.resource.hub_id != self.hub_id:
            raise ValidationError({"resource": "Selected resource belongs to a different hub."})

    def save(self, *args, **kwargs):
        if self.member and not self.customer_name:
            self.customer_name = self.client_display
        if not self.total_amount:
            raw_total = (self.quantity or Decimal("1.00")) * (self.unit_rate or Decimal("0.00"))
            self.total_amount = raw_total.quantize(Decimal("0.01"))
        elif self.total_amount is not None:
            self.total_amount = self.total_amount.quantize(Decimal("0.01"))
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def client_display(self):
        if self.member:
            if self.member.user:
                return self.member.user.display_name
            return self.member.name or self.member.phone_number or f"Customer #{self.member.pk}"
        if self.business:
            return self.business.name
        return self.customer_name or "Walk-in Farmer/Client"

    def __str__(self):
        return f"{self.service_type.name} - {self.client_display} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("services:booking_detail", kwargs={"pk": self.pk})
