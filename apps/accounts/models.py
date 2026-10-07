import uuid

from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models

from .managers import UserManager
from .roles import Role
from .validators import phone_validator, validate_image_size


class User(AbstractUser):
    """Platform user. `role` drives the matching Django Group and the Django admin flags."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email address", unique=True)
    phone_number = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.VIEWER, db_index=True)
    profile_photo = models.ImageField(
        upload_to="profile_photos/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_image_size],
    )
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    class Meta:
        ordering = ["first_name", "last_name", "username"]
        permissions = [
            ("assign_roles", "Can assign user roles"),
            ("export_reports", "Can export reports"),
            ("view_all_hubs", "Can view data for all hubs"),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        parts = [p for p in (self.first_name, self.last_name) if p]
        if parts:
            return "".join(p[0] for p in parts[:2]).upper()
        return self.username[:2].upper()

    def has_role(self, *roles):
        return self.role in roles

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        # Role is the single source of truth: only SUPER_ADMIN may use the Django admin.
        is_super = self.role == Role.SUPER_ADMIN
        self.is_superuser = is_super
        self.is_staff = is_super
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "role" in update_fields:
            kwargs["update_fields"] = {*update_fields, "is_staff", "is_superuser"}
        super().save(*args, **kwargs)