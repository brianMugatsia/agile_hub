from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r"^\+?[0-9]{9,15}$",
    message="Enter a valid phone number, e.g. +254712345678 or 0712345678.",
)

MAX_PHOTO_BYTES = 2 * 1024 * 1024


def validate_image_size(file):
    if file.size > MAX_PHOTO_BYTES:
        raise ValidationError("Profile photos must be 2 MB or smaller.")