from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Product(models.Model):
    sku = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=32, default="each")
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    selling_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    stock_on_hand = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.sku} — {self.name}"

    def get_absolute_url(self):
        return reverse("products:detail", kwargs={"pk": self.pk})


class ProductPriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="price_history")
    previous_price = models.DecimalField(max_digits=12, decimal_places=2)
    new_price = models.DecimalField(max_digits=12, decimal_places=2)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="product_price_changes"
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.product} price changed at {self.changed_at:%Y-%m-%d}"