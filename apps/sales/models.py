import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Sale(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        REFUNDED = "REFUNDED", "Refunded"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile money"
        BANK = "BANK", "Bank transfer"
        CREDIT = "CREDIT", "Credit"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hub = models.ForeignKey("hubs.Hub", on_delete=models.PROTECT, related_name="sales")
    business = models.ForeignKey(
        "beneficiaries.Business", on_delete=models.PROTECT, null=True, blank=True, related_name="sales"
    )
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales")
    customer_name = models.CharField(max_length=160, blank=True)
    customer_phone = models.CharField(max_length=24, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    payment_method = models.CharField(max_length=16, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    payment_reference = models.CharField(max_length=80, blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_sales"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [
            ("cancel_sale", "Can cancel a sale"),
            ("refund_sale", "Can refund a completed sale"),
        ]
        indexes = [models.Index(fields=["hub", "status", "-created_at"])]

    def __str__(self):
        return f"Sale {self.pk}"

    def get_absolute_url(self):
        return reverse("sales:detail", kwargs={"pk": self.pk})


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="sale_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(fields=["sale", "product"], name="unique_product_per_sale"),
        ]

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.quantity} × {self.product}"