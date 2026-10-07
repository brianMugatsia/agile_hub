import uuid

from django.conf import settings
from django.db import models


class Hub(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=24, unique=True)
    name = models.CharField(max_length=160)
    region = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=24, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_hubs",
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class HubMembership(models.Model):
    hub = models.ForeignKey(Hub, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hub_memberships")
    title = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["hub__name", "user__last_name"]
        constraints = [
            models.UniqueConstraint(fields=["hub", "user"], name="unique_hub_membership"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.hub}"