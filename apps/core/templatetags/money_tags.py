from decimal import Decimal, InvalidOperation

from django import template
from django.conf import settings

register = template.Library()


@register.filter
def kes(value, places=2):
    """{{ amount|kes }} -> 'KES 12,500.00'. Uses CURRENCY_CODE from settings."""
    if value in (None, ""):
        return "—"
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    return f"{settings.CURRENCY_CODE} {amount:,.{int(places)}f}"