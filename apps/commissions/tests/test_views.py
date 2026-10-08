from decimal import Decimal
from pathlib import Path

import pytest

from django.urls import reverse

from apps.accounts.roles import Role
from apps.commissions.models import CommissionSetting, SalesAgentCommission
from apps.hubs.models import Hub, HubMembership
from apps.sales.models import Sale

pytestmark = pytest.mark.django_db


def test_main_stylesheet_loads_commission_overrides_after_shared_page_styles():
    stylesheet = Path(__file__).resolve().parents[3] / "static" / "css" / "main.css"
    imports = stylesheet.read_text(encoding="utf-8")

    assert imports.index('url("pages/dashboard.css")') < imports.index(
        'url("pages/commissions.css")'
    )
    assert imports.index('url("pages/hub.css")') < imports.index(
        'url("pages/commissions.css")'
    )


def test_commission_list_renders_one_pair_of_export_buttons(client, make_user):
    admin = make_user(role=Role.ADMIN, is_superuser=True)
    client.force_login(admin)

    response = client.get(reverse("commissions:list"))

    assert response.status_code == 200
    assert response.content.count(b"Download CSV") == 1
    assert response.content.count(b"Download Excel") == 1
    assert reverse("commissions:export", args=["csv"]).encode() in response.content
    assert reverse("commissions:export", args=["xlsx"]).encode() in response.content


def test_commission_list_shows_table_empty_state_and_permission_links(
    client, make_user, roles
):
    admin = make_user(role=Role.ADMIN)
    client.force_login(admin)

    response = client.get(reverse("commissions:list"))

    assert response.status_code == 200
    for heading in (b"Created", b"Agent", b"Sale", b"Rate", b"Amount", b"Status"):
        assert heading in response.content
    assert b"No commissions yet" in response.content
    assert reverse("commissions:pending").encode() in response.content
    assert reverse("commissions:settings").encode() in response.content
    assert b'<section class="card dashboard-section dash-panel" data-spot>' in response.content


def test_commission_links_remain_hidden_without_their_permissions(client, make_user, roles):
    agent = make_user(role=Role.SALES_AGENT)
    client.force_login(agent)

    response = client.get(reverse("commissions:list"))

    assert response.status_code == 200
    assert b"No commissions yet" in response.content
    assert reverse("commissions:pending").encode() not in response.content
    assert reverse("commissions:settings").encode() not in response.content


def test_commission_search_matches_agent_first_and_last_name(client, make_user):
    admin = make_user(role=Role.ADMIN, is_superuser=True)
    agent = make_user(role=Role.SALES_AGENT, first_name="Jane", last_name="Doe")
    other_agent = make_user(role=Role.SALES_AGENT, first_name="Alex", last_name="Kim")
    hub = Hub.objects.create(code="COM-SEARCH", name="Commission search")
    matching_sale = Sale.objects.create(
        hub=hub, agent=agent, status=Sale.Status.COMPLETED, total="100.00"
    )
    other_sale = Sale.objects.create(
        hub=hub, agent=other_agent, status=Sale.Status.COMPLETED, total="50.00"
    )
    matching = SalesAgentCommission.objects.create(
        sale=matching_sale, agent=agent, rate="0.1000", base_amount="100.00", amount="10.00"
    )
    SalesAgentCommission.objects.create(
        sale=other_sale, agent=other_agent, rate="0.1000", base_amount="50.00", amount="5.00"
    )
    client.force_login(admin)

    response = client.get(reverse("commissions:list"), {"q": "Jane Doe"})

    assert response.status_code == 200
    assert str(matching.pk).encode() in response.content
    assert str(other_sale.pk).encode() not in response.content


def test_commission_detail_and_agent_statement_render_and_link_from_list(client, make_user):
    admin = make_user(role=Role.ADMIN, is_superuser=True)
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="COM-PAGES", name="Commission pages")
    HubMembership.objects.create(hub=hub, user=agent)
    sale = Sale.objects.create(
        hub=hub,
        agent=agent,
        status=Sale.Status.COMPLETED,
        total="100.00",
    )
    commission = SalesAgentCommission.objects.create(
        sale=sale,
        agent=agent,
        rate="0.1000",
        base_amount="100.00",
        amount="10.00",
    )
    client.force_login(admin)

    list_response = client.get(reverse("commissions:list"))
    detail_response = client.get(reverse("commissions:detail", kwargs={"pk": commission.pk}))
    sale_detail_response = client.get(reverse("sales:detail", kwargs={"pk": sale.pk}))
    statement_response = client.get(
        reverse("commissions:agent_statement", kwargs={"agent_id": agent.pk})
    )

    assert list_response.status_code == 200
    assert reverse("commissions:detail", kwargs={"pk": commission.pk}).encode() in list_response.content
    assert reverse("commissions:agent_statement", kwargs={"agent_id": agent.pk}).encode() in list_response.content
    assert reverse("sales:detail", kwargs={"pk": sale.pk}).encode() in detail_response.content
    assert detail_response.status_code == 200
    assert b"Commission details" in detail_response.content
    assert b'class="com-detail-list"' in detail_response.content
    assert b'class="com-detail-row"><dt>Agent</dt><dd>' in detail_response.content
    commission_css = (
        Path(__file__).resolve().parents[3]
        / "static"
        / "css"
        / "pages"
        / "commissions.css"
    ).read_text(encoding="utf-8")
    assert ".com-detail-row {" in commission_css
    assert b"Approve" in detail_response.content
    assert sale_detail_response.status_code == 200
    assert b"Sale ID" in sale_detail_response.content
    assert b"Items" in sale_detail_response.content
    assert b'data-reveal="up"' not in detail_response.content
    assert statement_response.status_code == 200
    assert statement_response.context["earned_total"] == Decimal("10.00")
    assert statement_response.context["pending_total"] == Decimal("10.00")


def test_agent_cannot_view_another_agents_statement(client, make_user):
    agent = make_user(role=Role.SALES_AGENT)
    other_agent = make_user(role=Role.SALES_AGENT)
    client.force_login(agent)

    response = client.get(
        reverse("commissions:agent_statement", kwargs={"agent_id": other_agent.pk})
    )

    assert response.status_code == 403


def test_sale_detail_link_respects_hub_scope(client, make_user, roles):
    manager = make_user(role=Role.HUB_MANAGER)
    agent = make_user(role=Role.SALES_AGENT)
    manager_hub = Hub.objects.create(code="SALE-ALLOWED", name="Manager hub")
    other_hub = Hub.objects.create(code="SALE-OTHER", name="Other hub")
    HubMembership.objects.create(hub=manager_hub, user=manager)
    sale = Sale.objects.create(
        hub=other_hub, agent=agent, status=Sale.Status.COMPLETED, total="50.00"
    )
    client.force_login(manager)

    response = client.get(reverse("sales:detail", kwargs={"pk": sale.pk}))

    assert response.status_code == 404


def test_pending_and_commission_settings_pages_render(client, make_user):
    admin = make_user(role=Role.SUPER_ADMIN)
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="COM-SETTINGS", name="Commission settings")
    sale = Sale.objects.create(hub=hub, agent=agent, status=Sale.Status.COMPLETED, total="50.00")
    commission = SalesAgentCommission.objects.create(
        sale=sale,
        agent=agent,
        rate="0.1000",
        base_amount="50.00",
        amount="5.00",
    )
    client.force_login(admin)

    pending_response = client.get(reverse("commissions:pending"))
    settings_response = client.get(reverse("commissions:settings"))
    create_response = client.post(
        reverse("commissions:settings"),
        {"rate": "0.1250", "effective_from": "2026-10-01"},
    )

    assert pending_response.status_code == 200
    assert str(commission.pk).encode() in pending_response.content
    assert b"?status=PENDING" in pending_response.content
    assert settings_response.status_code == 200
    assert b"Set a new rate" in settings_response.content
    assert create_response.status_code == 302
    assert CommissionSetting.objects.filter(
        rate="0.1250", effective_from="2026-10-01", created_by=admin
    ).exists()