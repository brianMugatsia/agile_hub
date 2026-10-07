from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class CommissionSetting(models.Model):
    rate = models.DecimalField(
        max_digits=5, decimal_places=4,
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

    def __str__(self):
        return f"{self.rate:.2%} from {self.effective_from}"


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