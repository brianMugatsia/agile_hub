from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class RevenueStream(models.Model):
    business = models.ForeignKey(
        "beneficiaries.Business", on_delete=models.PROTECT, null=True, blank=True, related_name="revenue_streams"
    )
    hub = models.ForeignKey("hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="revenue_streams")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class IncomeStatement(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        FINAL = "FINAL", "Final"

    business = models.ForeignKey(
        "beneficiaries.Business", on_delete=models.PROTECT, null=True, blank=True, related_name="income_statements"
    )
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="income_statements"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_end"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "hub", "period_start", "period_end"],
                name="unique_income_statement_period",
            ),
        ]

    def __str__(self):
        return f"Income statement {self.period_start} to {self.period_end}"


class IncomeStatementItem(models.Model):
    statement = models.ForeignKey(IncomeStatement, on_delete=models.CASCADE, related_name="items")
    stream = models.ForeignKey(RevenueStream, on_delete=models.PROTECT, null=True, blank=True)
    label = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    is_expense = models.BooleanField(default=False)

    class Meta:
        ordering = ["is_expense", "label"]

    def __str__(self):
        return f"{self.label}: {self.amount}"


class CashFlow(models.Model):
    class Direction(models.TextChoices):
        INFLOW = "INFLOW", "Inflow"
        OUTFLOW = "OUTFLOW", "Outflow"

    direction = models.CharField(max_length=8, choices=Direction.choices, db_index=True)
    category = models.CharField(max_length=100)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    transaction_date = models.DateField(db_index=True)
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="cash_flows"
    )
    business = models.ForeignKey(
        "beneficiaries.Business", on_delete=models.PROTECT, null=True, blank=True, related_name="cash_flows"
    )
    reference = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-created_at"]

    def __str__(self):
        return f"{self.get_direction_display()} — {self.category}: {self.amount}"


class Asset(models.Model):
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=100, blank=True)
    acquisition_date = models.DateField(null=True, blank=True)
    cost = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    useful_life_months = models.PositiveIntegerField(default=0)
    hub = models.ForeignKey("hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="assets")
    business = models.ForeignKey(
        "beneficiaries.Business", on_delete=models.PROTECT, null=True, blank=True, related_name="assets"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Liability(models.Model):
    name = models.CharField(max_length=160)
    counterparty = models.CharField(max_length=160, blank=True)
    balance = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    due_date = models.DateField(null=True, blank=True)
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="liabilities"
    )
    business = models.ForeignKey(
        "beneficiaries.Business", on_delete=models.PROTECT, null=True, blank=True, related_name="liabilities"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["due_date", "name"]

    def __str__(self):
        return self.name


class EquityRecord(models.Model):
    name = models.CharField(max_length=160)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    transaction_date = models.DateField(db_index=True)
    description = models.TextField(blank=True)
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="equity_records"
    )
    business = models.ForeignKey(
        "beneficiaries.Business", on_delete=models.PROTECT, null=True, blank=True, related_name="equity_records"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-transaction_date"]

    def __str__(self):
        return f"{self.name}: {self.amount}"


class Projection(models.Model):
    business = models.ForeignKey(
        "beneficiaries.Business", on_delete=models.PROTECT, null=True, blank=True, related_name="projections"
    )
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="projections"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    projected_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    projected_expenses = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    assumptions = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start"]

    def __str__(self):
        return f"Projection {self.period_start} to {self.period_end}"


class StartupCost(models.Model):
    business = models.ForeignKey(
        "beneficiaries.Business", on_delete=models.PROTECT, null=True, blank=True, related_name="startup_costs"
    )
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="startup_costs"
    )
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    incurred_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["incurred_on", "name"]

    def __str__(self):
        return self.name


class FundingSource(models.Model):
    business = models.ForeignKey(
        "beneficiaries.Business", on_delete=models.PROTECT, null=True, blank=True, related_name="funding_sources"
    )
    hub = models.ForeignKey(
        "hubs.Hub", on_delete=models.PROTECT, null=True, blank=True, related_name="funding_sources"
    )
    name = models.CharField(max_length=160)
    source_type = models.CharField(max_length=80, blank=True)
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    received_on = models.DateField(null=True, blank=True)
    terms = models.TextField(blank=True)

    class Meta:
        ordering = ["-received_on", "name"]

    def __str__(self):
        return self.name