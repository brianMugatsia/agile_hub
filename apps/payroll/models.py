from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class WorkerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="worker_profile"
    )
    hub = models.ForeignKey("hubs.Hub", on_delete=models.PROTECT, related_name="workers")
    employee_code = models.CharField(max_length=32, unique=True)
    job_title = models.CharField(max_length=100)
    monthly_salary = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    hired_on = models.DateField()
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]

    def __str__(self):
        return f"{self.employee_code} — {self.user.display_name}"


class SalaryRecord(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        PAID = "PAID", "Paid"
        REJECTED = "REJECTED", "Rejected"

    worker = models.ForeignKey(WorkerProfile, on_delete=models.PROTECT, related_name="salary_records")
    period_start = models.DateField()
    period_end = models.DateField()
    gross_amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    deductions = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_salary_records",
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="paid_salary_records",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start", "worker__employee_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["worker", "period_start", "period_end"], name="unique_worker_salary_period"
            ),
            models.CheckConstraint(condition=Q(period_end__gte=F("period_start")), name="salary_period_ordered"),
            models.CheckConstraint(condition=Q(deductions__lte=F("gross_amount")), name="salary_deductions_within_gross"),
        ]
        permissions = [
            ("approve_salaryrecord", "Can approve a salary record"),
            ("pay_salaryrecord", "Can pay an approved salary record"),
        ]

    def save(self, *args, **kwargs):
        self.net_amount = self.gross_amount - self.deductions
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.worker} — {self.period_start:%Y-%m}"