from decimal import Decimal
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role
from apps.hubs.models import Hub, HubMembership
from apps.services.models import HubResource, ServiceBooking, ServiceCategory, ServicePricingUnit, ServiceType, ServiceProvider, ProviderType, ServiceProviderStatus

pytestmark = pytest.mark.django_db


def test_service_views_permissions_and_workflow(client, make_user, roles):
    hub = Hub.objects.create(code="H-VIEW-1", name="Service Hub")
    manager = make_user(role=Role.HUB_MANAGER)
    viewer = make_user(role=Role.VIEWER)
    HubMembership.objects.create(hub=hub, user=manager)
    HubMembership.objects.create(hub=hub, user=viewer)

    service = ServiceType.objects.create(
        code="SRV-RIPEN",
        name="Mango Ripening Chamber",
        category=ServiceCategory.RIPENING,
        pricing_unit=ServicePricingUnit.PER_KG,
        standard_rate=Decimal("12.00"),
    )
    resource = HubResource.objects.create(
        hub=hub,
        service_type=service,
        name="Chamber Alpha",
        code="CH-ALPHA",
        capacity=Decimal("5000.00"),
    )

    client.force_login(manager)

    # 1. Access booking list
    response = client.get(reverse("services:booking_list"))
    assert response.status_code == 200

    # 2. Access equipment list
    response = client.get(reverse("services:resource_list"))
    assert response.status_code == 200

    # 3. Access provider lists (Internal, External, All, Status filtered)
    response = client.get(reverse("services:provider_list"))
    assert response.status_code == 200

    response = client.get(reverse("services:internal_provider_list"))
    assert response.status_code == 200

    response = client.get(reverse("services:external_provider_list"))
    assert response.status_code == 200

    response = client.get(reverse("services:provider_list") + "?status=ACTIVE")
    assert response.status_code == 200

    response = client.get(reverse("members:service_providers"))
    assert response.status_code == 200

    response = client.get(reverse("members:sales_agents"))
    assert response.status_code == 200

    # 4. Create booking through POST
    start_date = timezone.now() + timedelta(days=1)
    end_date = start_date + timedelta(days=2)
    response = client.post(
        reverse("services:booking_create"),
        data={
            "hub": hub.pk,
            "service_type": service.pk,
            "resource": resource.pk,
            "start_date": start_date.strftime("%Y-%m-%dT%H:%M"),
            "end_date": end_date.strftime("%Y-%m-%dT%H:%M"),
            "quantity": "800.00",
            "unit_rate": "12.00",
            "customer_name": "Farmer John",
            "customer_phone": "0700000000",
            "notes": "Premium mangoes",
        },
    )
    assert response.status_code == 302
    booking = ServiceBooking.objects.get(customer_name="Farmer John")
    assert booking.total_amount == Decimal("9600.00")

    # 5. Detail view
    response = client.get(reverse("services:booking_detail", kwargs={"pk": booking.pk}))
    assert response.status_code == 200
    assert b"Chamber Alpha" in response.content

    # 6. Start action
    response = client.post(
        reverse("services:booking_action", kwargs={"pk": booking.pk}),
        data={"action": "start"},
    )
    assert response.status_code == 302
    booking.refresh_from_db()
    assert booking.status == ServiceBooking.Status.IN_PROGRESS

    # 7. Complete action
    response = client.post(
        reverse("services:booking_action", kwargs={"pk": booking.pk}),
        data={"action": "complete", "actual_quantity": "850.00"},
    )
    assert response.status_code == 302
    booking.refresh_from_db()
    assert booking.status == ServiceBooking.Status.COMPLETED
    assert booking.total_amount == Decimal("10200.00")

    # 8. Pay action
    response = client.post(
        reverse("services:booking_action", kwargs={"pk": booking.pk}),      
        data={"action": "pay", "payment_reference": "MPESA-TEST-123"},      
    )
    assert response.status_code == 302
    booking.refresh_from_db()
    assert booking.payment_status == ServiceBooking.PaymentStatus.PAID

    # 9. Provider detail view
    provider = ServiceProvider.objects.create(
        provider_type=ProviderType.EXTERNAL,
        name="Test Provider Detail",
        service_category="SRV-RIPEN",
    )
    response = client.get(reverse("services:provider_detail", kwargs={"pk": provider.pk}))
    assert response.status_code == 200
