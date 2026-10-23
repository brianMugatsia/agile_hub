from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.core.scoping import scope_queryset
from .models import HubResource, ServiceBooking, ServiceType


def get_bookings_for_user(user):
    """Returns service bookings scoped to the user's role and hub memberships."""
    return scope_queryset(
        ServiceBooking.objects.select_related("hub", "resource", "service_type", "member__user", "business"),
        user,
    )


def get_resources_for_user(user):
    """Returns hub equipment/chambers scoped to user's permitted hubs."""
    return scope_queryset(
        HubResource.objects.select_related("hub", "service_type"),
        user,
    )


def get_services_summary(user, hub=None):
    """Returns operational KPIs for hub services."""
    bookings = get_bookings_for_user(user)
    resources = get_resources_for_user(user)

    if hub:
        bookings = bookings.filter(hub=hub)
        resources = resources.filter(hub=hub)

    now = timezone.now()
    return {
        "active_bookings_count": bookings.filter(status=ServiceBooking.Status.IN_PROGRESS).count(),
        "scheduled_bookings_count": bookings.filter(status=ServiceBooking.Status.SCHEDULED).count(),
        "total_revenue": bookings.filter(payment_status=ServiceBooking.PaymentStatus.PAID).aggregate(
            total=Sum("total_amount")
        )["total"] or 0,
        "available_resources_count": resources.filter(status=HubResource.Status.AVAILABLE).count(),
        "in_use_resources_count": resources.filter(status=HubResource.Status.IN_USE).count(),
        "maintenance_resources_count": resources.filter(status=HubResource.Status.MAINTENANCE).count(),
    }
