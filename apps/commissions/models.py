from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class CommissionSetting(models.Model):
    sales_agent_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    internal_provider_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    external_provider_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )
    effective_from = models.DateField(db_index=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_from", "-created_at"]

    @property
    def rate(self):
        return self.sales_agent_rate or Decimal("0")

    @rate.setter
    def rate(self, value):
        self.sales_agent_rate = value
        self.internal_provider_rate = value
        self.external_provider_rate = value

    def __str__(self):
        return f"Commissions from {self.effective_from}"


class SalesAgentCommission(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        PAID = "PAID", "Paid"
        REVERSED = "REVERSED", "Reversed"

    sale = models.OneToOneField("sales.Sale", on_delete=models.PROTECT, related_name="commission")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="commissions")
    rate = models.DecimalField(max_digits=5, decimal_places=4)
    base_amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_commissions",
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="paid_commissions",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("approve_salesagentcommission", "Can approve a sales commission"),
            ("reject_salesagentcommission", "Can reject a sales commission"),
            ("pay_salesagentcommission", "Can pay a sales commission"),
            ("reverse_salesagentcommission", "Can reverse a sales commission"),
        ]

    def __str__(self):
        return f"{self.agent}: {self.amount} ({self.get_status_display()})"


class ServiceCommission(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        PAID = "PAID", "Paid"
        REVERSED = "REVERSED", "Reversed"

    provider = models.ForeignKey(
        "services.ServiceProvider",
        on_delete=models.PROTECT,
        related_name="commissions"
    )
    provider_type = models.CharField(max_length=16, blank=True, db_index=True)
    booking = models.ForeignKey(
        "services.ServiceBooking",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="commissions"
    )
    service_type = models.ForeignKey(
        "services.ServiceType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_commissions"
    )
    rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))]
    )
    calculation_basis = models.CharField(max_length=64, blank=True)
    base_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))]
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))]
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_service_commissions"
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paid_service_commissions"
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("approve_servicecommission", "Can approve a service commission"),
            ("reject_servicecommission", "Can reject a service commission"),
            ("pay_servicecommission", "Can pay a service commission"),
            ("reverse_servicecommission", "Can reverse a service commission"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "booking"],
                name="unique_provider_booking_service_commission",
                condition=models.Q(booking__isnull=False)
            )
        ]

    def __str__(self):
        return f"Commission for {self.provider}: {self.amount} ({self.get_status_display()})"


class CommissionPayment(models.Model):
    commissions = models.ManyToManyField(
        ServiceCommission,
        related_name="payments"
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )
    payment_date = models.DateField(db_index=True)
    payment_reference = models.CharField(max_length=80, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commission_payments"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return f"Commission Payment {self.amount} on {self.payment_date}"
