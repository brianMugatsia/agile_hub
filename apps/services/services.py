from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record_event
from apps.finance.models import CashFlow
from apps.finance.services.calculations import get_active_financial_setting
from apps.hubs.permissions import user_can_access_hub

from .models import HubResource, ServiceBooking, ServiceProvider, ServiceProviderStatus, ServiceType, ProviderType

CENT = Decimal("0.01")


@transaction.atomic
def create_service_booking(
    *,
    hub,
    resource,
    service_type,
    start_date,
    end_date,
    quantity,
    unit_rate=None,
    service_provider=None,
    member=None,
    business=None,
    customer_name="",
    customer_phone="",
    notes="",
    actor=None,
):
    """Creates a new service booking (e.g. ripening batch or harvesting machine hire)."""
    if actor and not user_can_access_hub(actor, hub):
        raise PermissionDenied("You do not have access to this hub.")

    if resource.hub_id != hub.pk:
        raise ValidationError({"resource": "Selected resource belongs to a different hub."})

    if resource.service_type_id != service_type.pk:
        raise ValidationError({"resource": "Resource type does not match the selected service."})

    if start_date >= end_date:
        raise ValidationError({"end_date": "Booking end time must be strictly after start time."})

    if quantity <= Decimal("0.00"):
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    if resource.status == HubResource.Status.MAINTENANCE:
        raise ValidationError({"resource": "Selected resource is currently under maintenance."})

    if resource.status == HubResource.Status.RETIRED:
        raise ValidationError({"resource": "Selected resource is retired."})

    if service_type.category in (
        service_type.category.HARVESTING,
        service_type.category.TRANSPORT,
    ):
        overlapping = (
            ServiceBooking.objects.filter(
                resource=resource,
                status__in=[ServiceBooking.Status.SCHEDULED, ServiceBooking.Status.IN_PROGRESS],
            )
            .filter(Q(start_date__lt=end_date) & Q(end_date__gt=start_date))
            .exists()
        )
        if overlapping:
            raise ValidationError(
                {"resource": f"Resource '{resource.name}' is already booked during this timeframe."}
            )

    rate = unit_rate if unit_rate is not None else service_type.standard_rate
    total = (quantity * rate).quantize(CENT, rounding=ROUND_HALF_UP)

    booking = ServiceBooking.objects.create(
        hub=hub,
        resource=resource,
        service_type=service_type,
        service_provider=service_provider,
        member=member,
        business=business,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        start_date=start_date,
        end_date=end_date,
        quantity=quantity,
        unit_rate=rate,
        total_amount=total,
        status=ServiceBooking.Status.SCHEDULED,
        payment_status=ServiceBooking.PaymentStatus.PENDING,
        notes=notes.strip(),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )

    record_event(
        action="service_booking.created",
        summary=f"Service booking created: {booking}",
        actor=actor,
        target=booking,
        changes={
            "service": service_type.name,
            "resource": resource.name,
            "quantity": str(quantity),
            "total_amount": str(total),
        },
    )
    return booking


@transaction.atomic
def start_service_booking(*, booking_id, actor=None):
    """Transitions a booking to IN_PROGRESS and marks equipment IN_USE."""
    booking = ServiceBooking.objects.select_for_update().get(pk=booking_id)

    if actor and not user_can_access_hub(actor, booking.hub):
        raise PermissionDenied("You do not have access to this hub.")

    if booking.status != ServiceBooking.Status.SCHEDULED:
        raise ValidationError(f"Cannot start booking in status '{booking.get_status_display()}'.")

    booking.status = ServiceBooking.Status.IN_PROGRESS
    booking.save(update_fields=["status", "updated_at"])

    resource = booking.resource
    resource.status = HubResource.Status.IN_USE
    resource.save(update_fields=["status", "updated_at"])

    record_event(
        action="service_booking.started",
        summary=f"Service booking started: {booking}",
        actor=actor,
        target=booking,
    )
    return booking


@transaction.atomic
def complete_service_booking(*, booking_id, actor=None, actual_quantity=None, notes="", custom_rate=None, custom_amount=None):
    """Marks booking COMPLETED and frees up equipment status."""
    booking = ServiceBooking.objects.select_for_update().get(pk=booking_id)

    if actor and not user_can_access_hub(actor, booking.hub):
        raise PermissionDenied("You do not have access to this hub.")

    if booking.status not in (ServiceBooking.Status.SCHEDULED, ServiceBooking.Status.IN_PROGRESS):
        raise ValidationError(f"Cannot complete booking in status '{booking.get_status_display()}'.")

    was_in_progress = (booking.status == ServiceBooking.Status.IN_PROGRESS)

    if actual_quantity is not None and actual_quantity > Decimal("0.00"):
        booking.quantity = actual_quantity
        booking.total_amount = (booking.quantity * booking.unit_rate).quantize(CENT, rounding=ROUND_HALF_UP)

    booking.status = ServiceBooking.Status.COMPLETED
    if notes.strip():
        booking.notes = f"{booking.notes}\nCompletion Notes: {notes.strip()}".strip()
    booking.save(update_fields=["status", "quantity", "total_amount", "notes", "updated_at"])

    if booking.service_provider:
        from apps.commissions.services import accrue_service_commission
        accrue_service_commission(booking, custom_rate=custom_rate, custom_amount=custom_amount)

    resource = booking.resource
    if was_in_progress:
        resource.status = HubResource.Status.AVAILABLE
        resource.save(update_fields=["status", "updated_at"])

    record_event(
        action="service_booking.completed",
        summary=f"Service booking completed: {booking}",
        actor=actor,
        target=booking,
        changes={"total_amount": str(booking.total_amount)},
    )
    return booking


@transaction.atomic
def cancel_service_booking(*, booking_id, actor=None, reason=""):
    """Cancels a scheduled or in-progress booking and frees up equipment status."""
    booking = ServiceBooking.objects.select_for_update().get(pk=booking_id)

    if actor and not user_can_access_hub(actor, booking.hub):
        raise PermissionDenied("You do not have access to this hub.")

    if booking.status in (ServiceBooking.Status.COMPLETED, ServiceBooking.Status.CANCELLED):
        raise ValidationError(f"Cannot cancel booking with status '{booking.get_status_display()}'.")

    was_in_progress = (booking.status == ServiceBooking.Status.IN_PROGRESS)

    booking.status = ServiceBooking.Status.CANCELLED
    if reason.strip():
        booking.notes = f"{booking.notes}\nCancellation reason: {reason.strip()}".strip()
    booking.save(update_fields=["status", "notes", "updated_at"])

    resource = booking.resource
    if was_in_progress:
        resource.status = HubResource.Status.AVAILABLE
        resource.save(update_fields=["status", "updated_at"])

    record_event(
        action="service_booking.cancelled",
        summary=f"Service booking cancelled: {booking}",
        actor=actor,
        target=booking,
        changes={"reason": reason},
    )
    return booking





@transaction.atomic
def record_booking_payment(*, booking_id, payment_reference="", actor=None):
    """Marks booking PAID and logs a CashFlow inflow for the hub."""
    booking = ServiceBooking.objects.select_for_update().get(pk=booking_id)

    if actor and not user_can_access_hub(actor, booking.hub):
        raise PermissionDenied("You do not have access to this hub.")

    if booking.payment_status == ServiceBooking.PaymentStatus.PAID:
        raise ValidationError("This booking is already marked as paid.")

    booking.payment_status = ServiceBooking.PaymentStatus.PAID
    booking.payment_reference = payment_reference.strip()
    booking.save(update_fields=["payment_status", "payment_reference", "updated_at"])

    CashFlow.objects.create(
        direction=CashFlow.Direction.INFLOW,
        category="Hub Services",
        amount=booking.total_amount,
        transaction_date=timezone.localdate(),
        hub=booking.hub,
        reference=f"booking:{booking.pk}",
        description=f"Payment for {booking.service_type.name} ({booking.client_display})",
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )

    record_event(
        action="service_booking.paid",
        summary=f"Booking payment recorded for {booking}: {booking.total_amount}",
        actor=actor,
        target=booking,
        changes={"amount": str(booking.total_amount), "reference": booking.payment_reference},
    )
    return booking


@transaction.atomic
def register_service_provider(
    *,
    provider_type,
    name,
    member=None,
    phone_number="",
    email="",
    address="",
    service_category="",
    actor=None,
):
    if provider_type == ProviderType.INTERNAL and not member:
        raise ValidationError({"member": "Internal service providers must be linked to an existing member."})
    if provider_type == ProviderType.EXTERNAL and member:
        raise ValidationError({"member": "External service providers must not be linked to a member."})

    provider = ServiceProvider.objects.create(
        provider_type=provider_type,
        member=member,
        name=name.strip(),
        phone_number=phone_number.strip(),
        email=email.strip().lower(),
        address=address.strip(),
        service_category=service_category,
        status=ServiceProviderStatus.ACTIVE,
    )
    record_event(
        action="service_provider.registered",
        summary=f"Registered service provider: {provider}",
        actor=actor,
        target=provider,
        changes={"type": provider_type, "name": provider.name},
    )
    return provider


@transaction.atomic
def suspend_service_provider(*, provider_id, reason="", actor=None):
    if actor and not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentication required.")
    if actor and not actor.has_perm("services.suspend_serviceprovider"):
        raise PermissionDenied("You do not have permission to suspend service providers.")
    provider = ServiceProvider.objects.select_for_update().get(pk=provider_id)
    if provider.status == ServiceProviderStatus.SUSPENDED:
        raise ValidationError("Provider is already suspended.")
    provider.status = ServiceProviderStatus.SUSPENDED
    provider.suspension_reason = reason.strip()
    provider.save(update_fields=["status", "suspension_reason", "updated_at"])
    record_event(
        action="service_provider.suspended",
        summary=f"Service provider suspended: {provider}",
        actor=actor,
        target=provider,
        changes={"reason": reason.strip()},
    )
    return provider


@transaction.atomic
def reactivate_service_provider(*, provider_id, actor=None):
    if actor and not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentication required.")
    if actor and not actor.has_perm("services.reactivate_serviceprovider"):
        raise PermissionDenied("You do not have permission to reactivate service providers.")
    provider = ServiceProvider.objects.select_for_update().get(pk=provider_id)
    if provider.status == ServiceProviderStatus.ACTIVE:
        raise ValidationError("Provider is already active.")
    provider.status = ServiceProviderStatus.ACTIVE
    provider.suspension_reason = ""
    provider.save(update_fields=["status", "suspension_reason", "updated_at"])
    record_event(
        action="service_provider.reactivated",
        summary=f"Service provider reactivated: {provider}",
        actor=actor,
        target=provider,
    )
    return provider


def check_dormant_providers():
    setting = get_active_financial_setting()
    dormancy_days = int(setting.provider_dormancy_days)
    threshold_date = timezone.now() - timezone.timedelta(days=dormancy_days)

    active_providers = ServiceProvider.objects.filter(status=ServiceProviderStatus.ACTIVE)
    dormant_count = 0
    for provider in active_providers:
        latest_booking = provider.bookings.filter(status=ServiceBooking.Status.COMPLETED).order_by("-end_date").first()
        if not latest_booking or latest_booking.end_date < threshold_date:
            provider.status = ServiceProviderStatus.DORMANT
            provider.save(update_fields=["status", "updated_at"])
            dormant_count += 1
    return dormant_count
