from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class InventoryBalance(models.Model):
    hub = models.ForeignKey("hubs.Hub", on_delete=models.CASCADE, related_name="stock_balances")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="stock_balances")
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hub__name", "product__name"]
        constraints = [
            models.UniqueConstraint(fields=["hub", "product"], name="unique_hub_product_stock"),
            models.CheckConstraint(condition=Q(quantity__gte=0), name="inventory_balance_nonnegative"),
        ]

    def __str__(self):
        return f"{self.hub}: {self.product} ({self.quantity})"


class InventoryTransaction(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = "RECEIPT", "Stock received"
        ISSUE = "ISSUE", "Stock issued"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"
        SALE = "SALE", "Sale"
        REFUND = "REFUND", "Refund"

    class Direction(models.TextChoices):
        IN = "IN", "In"
        OUT = "OUT", "Out"

    hub = models.ForeignKey("hubs.Hub", on_delete=models.PROTECT, related_name="inventory_transactions")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="inventory_transactions")
    kind = models.CharField(max_length=12, choices=Kind.choices, db_index=True)
    direction = models.CharField(max_length=3, choices=Direction.choices, default=Direction.IN)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reference = models.CharField(max_length=80, blank=True, db_index=True)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="inventory_transactions"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["hub", "product", "-created_at"])]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.quantity} {self.product.unit} {self.product}"