from django.core.exceptions import ValidationError


def validate_date_range(start, end):
    if start and end and end < start:
        raise ValidationError({"end": "The end date must be on or after the start date."})
    return start, end