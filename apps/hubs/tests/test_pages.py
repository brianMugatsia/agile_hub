from datetime import datetime, time
from decimal import Decimal

import pytest

from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role
from apps.hubs.models import Hub, HubMembership
from apps.sales.models import Sale

pytestmark = pytest.mark.django_db


def test_hub_list_links_to_scoped_details_and_performance(client, make_user):
    manager = make_user(role=Role.HUB_MANAGER)
    hub = Hub.objects.create(code="HUB-PAGE", name="Hub page")
    HubMembership.objects.create(hub=hub, user=manager)
    client.force_login(manager)

    list_response = client.get(reverse("hubs:list"))
    detail_response = client.get(reverse("hubs:detail", kwargs={"pk": hub.pk}))
    performance_response = client.get(reverse("hubs:performance", kwargs={"pk": hub.pk}))

    assert list_response.status_code == 200
    assert reverse("hubs:detail", kwargs={"pk": hub.pk}).encode() in list_response.content
    assert detail_response.status_code == 200
    assert b"View performance" in detail_response.content
    assert performance_response.status_code == 200
    assert performance_response.context["sales_count"] == 0


def test_admin_can_edit_hub_from_list_and_detail(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    manager = make_user(role=Role.HUB_MANAGER)
    hub = Hub.objects.create(code="HUB-EDIT", name="Before edit")
    client.force_login(admin)

    hub_list = client.get(reverse("hubs:list"))
    hub_detail = client.get(reverse("hubs:detail", kwargs={"pk": hub.pk}))
    assert reverse("hubs:edit", kwargs={"pk": hub.pk}).encode() in hub_list.content
    assert b"Edit hub" in hub_detail.content

    response = client.post(
        reverse("hubs:edit", kwargs={"pk": hub.pk}),
        {
            "code": hub.code,
            "name": "After edit",
            "region": "Central",
            "address": "Main street",
            "phone_number": "0712345678",
            "manager": str(manager.pk),
            "status": Hub.Status.ACTIVE,
        },
    )

    assert response.status_code == 302
    hub.refresh_from_db()
    assert hub.name == "After edit"
    assert hub.manager == manager


def test_hub_manager_can_edit_only_accessible_hubs(client, make_user, roles):
    manager = make_user(role=Role.HUB_MANAGER)
    assigned_hub = Hub.objects.create(code="HUB-EDIT-OWN", name="Assigned hub", manager=manager)
    hidden_hub = Hub.objects.create(code="HUB-EDIT-HIDDEN", name="Hidden hub")
    HubMembership.objects.create(hub=assigned_hub, user=manager)
    client.force_login(manager)

    own_edit = client.get(reverse("hubs:edit", kwargs={"pk": assigned_hub.pk}))
    hidden_edit = client.get(reverse("hubs:edit", kwargs={"pk": hidden_hub.pk}))
    hub_list = client.get(reverse("hubs:list"))

    assert own_edit.status_code == 200
    assert hidden_edit.status_code == 404
    assert reverse("hubs:edit", kwargs={"pk": assigned_hub.pk}).encode() in hub_list.content
    assert reverse("hubs:edit", kwargs={"pk": hidden_hub.pk}).encode() not in hub_list.content

    response = client.post(
        reverse("hubs:edit", kwargs={"pk": assigned_hub.pk}),
        {
            "code": assigned_hub.code,
            "name": "Updated assigned hub",
            "region": "",
            "address": "",
            "phone_number": "",
            "manager": str(manager.pk),
            "status": Hub.Status.ACTIVE,
        },
    )
    assert response.status_code == 302
    assigned_hub.refresh_from_db()
    assert assigned_hub.name == "Updated assigned hub"


def test_hub_detail_and_performance_hide_unassigned_hubs(client, make_user):
    manager = make_user(role=Role.HUB_MANAGER)
    hub = Hub.objects.create(code="HUB-HIDDEN", name="Hidden hub")
    client.force_login(manager)

    detail_response = client.get(reverse("hubs:detail", kwargs={"pk": hub.pk}))
    performance_response = client.get(reverse("hubs:performance", kwargs={"pk": hub.pk}))

    assert detail_response.status_code == 404
    assert performance_response.status_code == 404


def test_hub_performance_uses_selected_date_period(client, make_user):
    manager = make_user(role=Role.HUB_MANAGER)
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="HUB-PERFORMANCE", name="Performance hub")
    HubMembership.objects.create(hub=hub, user=manager)
    selected_date = timezone.localdate()
    Sale.objects.create(
        hub=hub,
        agent=agent,
        status=Sale.Status.COMPLETED,
        completed_at=timezone.make_aware(datetime.combine(selected_date, time(12))),
        total=Decimal("42.00"),
    )
    client.force_login(manager)

    response = client.get(
        reverse("hubs:performance", kwargs={"pk": hub.pk}),
        {"start": selected_date.isoformat()},
    )

    assert response.status_code == 200
    assert response.context["sales_count"] == 1
    assert response.context["sales_total"] == Decimal("42.00")
    assert response.context["active_agents"] == 1
    assert response.context["period_start"] == selected_date
    assert response.context["period_end"] == selected_date
