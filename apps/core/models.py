import uuid

from django.conf import settings
from django.db import models


class SavedFilter(models.Model):
    model_key = models.CharField(max_length=128, db_index=True)
    name = models.CharField(max_length=80)
    query_params = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_filters")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "-created_at"]

    def __str__(self):
        return self.name


class StagedSpreadsheetImport(models.Model):
    class ImportType(models.TextChoices):
        PRODUCTS = "products", "Products"
        INVENTORY = "inventory", "Inventory movements"

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    import_type = models.CharField(max_length=16, choices=ImportType.choices, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="staged_spreadsheet_imports",
    )
    rows = models.JSONField()
    report_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_import_type_display()} import by {self.created_by}"