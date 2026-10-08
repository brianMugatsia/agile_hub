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
