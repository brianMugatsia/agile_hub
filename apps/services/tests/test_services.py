from decimal import Decimal
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.roles import Role
from apps.finance.models import CashFlow
from apps.hubs.models import Hub, HubMembership
from apps.services.models import HubResource, ServiceBooking, ServiceCategory, ServicePricingUnit, ServiceType
from apps.services.services import (
    cancel_service_booking,
    complete_service_booking,
    create_service_booking,
    record_booking_payment,
    start_service_booking,
)

pytestmark = pytest.mark.django_db


def _hub(code="H-SRV-1"):
    return Hub.objects.create(code=code, name=f"Hub {code}")


def _ripening_service():
    return ServiceType.objects.create(
        code="RIP-BANANA",
        name="Banana Ripening Chamber",
        category=ServiceCategory.RIPENING,
        pricing_unit=ServicePricingUnit.PER_KG,
        standard_rate=Decimal("15.00"),
    )


def _harvesting_service():
    return ServiceType.objects.create(
        code="HARV-MAIZE",
        name="Combine Harvester Operation",
        category=ServiceCategory.HARVESTING,
        pricing_unit=ServicePricingUnit.PER_ACRE,
        standard_rate=Decimal("2500.00"),
    )


def test_create_ripening_booking_and_calculate_total(make_user, roles):
    hub = _hub()
    admin = make_user(role=Role.ADMIN)
    HubMembership.objects.create(hub=hub, user=admin)
    service = _ripening_service()

    chamber = HubResource.objects.create(
        hub=hub,
        service_type=service,
        name="Ripening Chamber A",
        code="CHAMBER-A",
        capacity=Decimal("10000.00"),
        capacity_unit="kg",
    )

    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(days=4)

    booking = create_service_booking(
        hub=hub,
        resource=chamber,
        service_type=service,
        start_date=start,
        end_date=end,
        quantity=Decimal("1200.00"),
        customer_name="Farmer Joe",
        customer_phone="0712345678",
        actor=admin,
    )

    assert booking.status == ServiceBooking.Status.SCHEDULED
    assert booking.payment_status == ServiceBooking.PaymentStatus.PENDING
    assert booking.total_amount == Decimal("18000.00")  # 1200 kg * 15.00
    assert booking.resource == chamber


def test_machinery_hire_prevents_overlapping_bookings(make_user, roles):
    hub = _hub()
    admin = make_user(role=Role.ADMIN)
    HubMembership.objects.create(hub=hub, user=admin)
    service = _harvesting_service()

    harvester = HubResource.objects.create(
        hub=hub,
        service_type=service,
        name="Harvester 01",
        code="HARV-01",
        capacity=Decimal("1.00"),
        capacity_unit="machine",
        operator_name="Sam Driver",
    )

    start = timezone.now() + timedelta(days=2)
    end = start + timedelta(days=2)

    # First booking
    create_service_booking(
        hub=hub,
        resource=harvester,
        service_type=service,
        start_date=start,
        end_date=end,
        quantity=Decimal("5.00"),
        customer_name="Farm 1",
        actor=admin,
    )

    # Overlapping booking attempt
    with pytest.raises(ValidationError) as exc_info:
        create_service_booking(
            hub=hub,
            resource=harvester,
            service_type=service,
            start_date=start + timedelta(hours=12),
            end_date=end + timedelta(hours=12),
            quantity=Decimal("3.00"),
            customer_name="Farm 2",
            actor=admin,
        )

    assert "already booked during this timeframe" in str(exc_info.value)


def test_booking_lifecycle_start_complete_pay(make_user, roles):
    hub = _hub()
    admin = make_user(role=Role.ADMIN)
    HubMembership.objects.create(hub=hub, user=admin)
    service = _harvesting_service()

    harvester = HubResource.objects.create(
        hub=hub,
        service_type=service,
        name="Harvester 02",
        code="HARV-02",
        capacity=Decimal("1.00"),
        capacity_unit="machine",
    )

    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(days=1)

    booking = create_service_booking(
        hub=hub,
        resource=harvester,
        service_type=service,
        start_date=start,
        end_date=end,
        quantity=Decimal("4.00"),
        unit_rate=Decimal("2500.00"),
        customer_name="Farmer Sarah",
        actor=admin,
    )

    # 1. Start operation
    start_service_booking(booking_id=booking.pk, actor=admin)
    booking.refresh_from_db()
    harvester.refresh_from_db()
    assert booking.status == ServiceBooking.Status.IN_PROGRESS
    assert harvester.status == HubResource.Status.IN_USE

    # 2. Complete operation
    complete_service_booking(
        booking_id=booking.pk, actor=admin, actual_quantity=Decimal("4.50"), notes="Completed 4.5 acres"
    )
    booking.refresh_from_db()
    harvester.refresh_from_db()
    assert booking.status == ServiceBooking.Status.COMPLETED
    assert booking.quantity == Decimal("4.50")
    assert booking.total_amount == Decimal("11250.00")  # 4.5 * 2500
    assert harvester.status == HubResource.Status.AVAILABLE
    assert "Completed 4.5 acres" in booking.notes

    # 3. Record payment
    record_booking_payment(booking_id=booking.pk, payment_reference="MPESA-9988", actor=admin)
    booking.refresh_from_db()
    assert booking.payment_status == ServiceBooking.PaymentStatus.PAID
    assert booking.payment_reference == "MPESA-9988"

    # Verify CashFlow integration
    cash_flow = CashFlow.objects.get(reference=f"booking:{booking.pk}")
    assert cash_flow.amount == Decimal("11250.00")
    assert cash_flow.hub == hub
    assert cash_flow.direction == CashFlow.Direction.INFLOW


def test_cancel_service_booking_releases_equipment(make_user, roles):
    hub = _hub()
    admin = make_user(role=Role.ADMIN)
    HubMembership.objects.create(hub=hub, user=admin)
    service = _ripening_service()

    chamber = HubResource.objects.create(
        hub=hub,
        service_type=service,
        name="Chamber B",
        code="CHAMBER-B",
        capacity=Decimal("5000.00"),
    )

    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(days=3)

    booking = create_service_booking(
        hub=hub,
        resource=chamber,
        service_type=service,
        start_date=start,
        end_date=end,
        quantity=Decimal("500.00"),
        actor=admin,
    )

    start_service_booking(booking_id=booking.pk, actor=admin)
    chamber.refresh_from_db()
    assert chamber.status == HubResource.Status.IN_USE

    cancel_service_booking(booking_id=booking.pk, actor=admin, reason="Client cancelled batch")
    booking.refresh_from_db()
    chamber.refresh_from_db()

    assert booking.status == ServiceBooking.Status.CANCELLED
    assert chamber.status == HubResource.Status.AVAILABLE
    assert "Client cancelled batch" in booking.notes
