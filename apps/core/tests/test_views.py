from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role
from apps.commissions.models import SalesAgentCommission
from apps.core.scoping import scope_queryset
from apps.finance.models import IncomeStatement, IncomeStatementItem
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import InventoryBalance
from apps.payroll.models import SalaryRecord, WorkerProfile
from apps.products.models import Product
from apps.sales.models import Sale

pytestmark = pytest.mark.django_db


def make_completed_sale(*, hub, agent, completed_on, total):
    return Sale.objects.create(
        hub=hub,
        agent=agent,
        status=Sale.Status.COMPLETED,
        completed_at=timezone.make_aware(datetime.combine(completed_on, time(12))),
        total=total,
    )


def test_viewer_is_scoped_to_active_hub_memberships(make_user):
    viewer = make_user(role=Role.VIEWER)
    agent = make_user(role=Role.SALES_AGENT)
    visible_hub = Hub.objects.create(code="VIEW-1", name="Visible")
    hidden_hub = Hub.objects.create(code="VIEW-2", name="Hidden")
    HubMembership.objects.create(hub=visible_hub, user=viewer)
    visible_sale = Sale.objects.create(hub=visible_hub, agent=agent)
    Sale.objects.create(hub=hidden_hub, agent=agent)

    scoped_sales = scope_queryset(Sale.objects.all(), viewer)

    assert list(scoped_sales) == [visible_sale]


def test_finance_user_is_scoped_through_statement_items(make_user):
    finance = make_user(role=Role.FINANCE_OFFICER)
    visible_hub = Hub.objects.create(code="FIN-1", name="Visible finance")
    hidden_hub = Hub.objects.create(code="FIN-2", name="Hidden finance")
    HubMembership.objects.create(hub=visible_hub, user=finance)
    visible_statement = IncomeStatement.objects.create(
        hub=visible_hub,
        period_start="2025-01-01",
        period_end="2025-01-31",
    )
    hidden_statement = IncomeStatement.objects.create(
        hub=hidden_hub,
        period_start="2025-01-01",
        period_end="2025-01-31",
        business=None,
    )
    visible_item = IncomeStatementItem.objects.create(statement=visible_statement, label="Expense", amount="12.00")
    IncomeStatementItem.objects.create(statement=hidden_statement, label="Other expense", amount="15.00")

    scoped_items = scope_queryset(IncomeStatementItem.objects.all(), finance)

    assert list(scoped_items) == [visible_item]


def test_dashboard_defaults_to_current_month_and_filters_sales_by_dates(client, make_user):
    admin = make_user(role=Role.ADMIN)
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="DASH-DATE", name="Dashboard dates")
    today = timezone.localdate()
    default_end = today
    default_start = today - timedelta(days=29)
    old_date = default_start - timedelta(days=5)
    current_sale = make_completed_sale(
        hub=hub, agent=agent, completed_on=today, total=Decimal("20.00")
    )
    make_completed_sale(
        hub=hub, agent=agent, completed_on=old_date, total=Decimal("10.00")
    )
    client.force_login(admin)

    default_response = client.get(reverse("core:dashboard"))
    assert default_response.status_code == 200
    assert default_response.context["date_start"] == default_start
    assert default_response.context["date_end"] == default_end
    assert b'name="start_date"' in default_response.content
    assert b'name="end_date"' in default_response.content
    assert b'class="dash-range"' in default_response.content
    assert b'class="input" id="dashboard-start-date"' in default_response.content
    assert b'aria-label="Filter dashboard activity dates"' in default_response.content
    assert ("Total Sales value", Decimal("20.00")) in default_response.context["dashboard_stats"]
    assert list(default_response.context["recent_sales"]) == [current_sale]

    filtered_response = client.get(
        reverse("core:dashboard"),
        {"start_date": old_date.isoformat(), "end_date": old_date.isoformat()},
    )
    assert ("Total Sales value", Decimal("10.00")) in filtered_response.context["dashboard_stats"]
    assert [sale.completed_at.date() for sale in filtered_response.context["recent_sales"]] == [
        old_date
    ]


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"start_date": "not-a-date", "end_date": "2025-01-31"}, "valid start date"),
        ({"start_date": "2025-02-01", "end_date": "2025-01-31"}, "end date must"),
        ({"start_date": "2024-01-01", "end_date": "2025-01-01"}, "no more than 366 days"),
    ],
)
def test_dashboard_reports_invalid_date_ranges_and_falls_back_to_default(
    client, make_user, params, message
):
    admin = make_user(role=Role.ADMIN)
    client.force_login(admin)

    response = client.get(reverse("core:dashboard"), params)

    assert response.status_code == 200
    assert response.context["date_errors"]
    assert message in response.content.decode().lower()
    assert response.context["date_start"] == timezone.localdate() - timedelta(days=29)


def test_dashboard_date_filter_preserves_hub_scope(client, make_user):
    manager = make_user(role=Role.HUB_MANAGER)
    agent = make_user(role=Role.SALES_AGENT)
    visible_hub = Hub.objects.create(code="DASH-VISIBLE", name="Visible")
    hidden_hub = Hub.objects.create(code="DASH-HIDDEN", name="Hidden")
    HubMembership.objects.create(hub=visible_hub, user=manager)
    included = make_completed_sale(
        hub=visible_hub, agent=agent, completed_on=date(2025, 4, 15), total=Decimal("12.00")
    )
    make_completed_sale(
        hub=hidden_hub, agent=agent, completed_on=date(2025, 4, 15), total=Decimal("50.00")
    )
    make_completed_sale(
        hub=visible_hub, agent=agent, completed_on=date(2025, 3, 31), total=Decimal("25.00")
    )
    client.force_login(manager)

    response = client.get(
        reverse("core:dashboard"),
        {"start_date": "2025-04-01", "end_date": "2025-04-30"},
    )

    assert ("Total Sales value", Decimal("12.00")) in response.context["dashboard_stats"]
    assert list(response.context["recent_sales"]) == [included]


def test_dashboard_approval_badges_show_totals_not_preview_lengths(client, make_user):
    admin = make_user(role=Role.ADMIN)
    agent = make_user(role=Role.SALES_AGENT)
    worker_user = make_user(role=Role.WORKER)
    hub = Hub.objects.create(code="DASH-APPROVALS", name="Approval dashboard")
    worker = WorkerProfile.objects.create(
        user=worker_user,
        hub=hub,
        employee_code="DASH-WORKER",
        job_title="Operator",
        monthly_salary="1000.00",
        hired_on=date(2025, 1, 1),
    )
    for index in range(9):
        sale = Sale.objects.create(hub=hub, agent=agent, total="10.00")
        SalesAgentCommission.objects.create(
            sale=sale,
            agent=agent,
            rate="0.1000",
            base_amount="10.00",
            amount="1.00",
        )
        period_start = date(2025, 1, 1) + timedelta(days=index)
        SalaryRecord.objects.create(
            worker=worker,
            period_start=period_start,
            period_end=period_start + timedelta(days=27),
            gross_amount=Decimal("1000.00"),
            deductions=Decimal("0.00"),
            status=SalaryRecord.Status.PENDING,
        )
    client.force_login(admin)

    response = client.get(reverse("core:dashboard"))

    assert response.context["pending_commission_count"] == 9
    assert response.context["pending_salary_count"] == 9
    assert len(response.context["pending_commissions"]) == 8
    assert len(response.context["pending_salaries"]) == 8
    assert b'<span class="dash-count">9</span>' in response.content


def test_dashboard_commission_earned_cards(client, make_user):
    admin = make_user(role=Role.ADMIN)
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="DASH-COMM", name="Commission Hub")
    HubMembership.objects.create(hub=hub, user=admin)
    HubMembership.objects.create(hub=hub, user=agent)

    sale = make_completed_sale(hub=hub, agent=agent, completed_on=timezone.localdate(), total=Decimal("100.00"))
    SalesAgentCommission.objects.create(
        sale=sale,
        agent=agent,
        rate=Decimal("0.1000"),
        base_amount=Decimal("100.00"),
        amount=Decimal("10.00"),
        status=SalesAgentCommission.Status.APPROVED,
    )

    from apps.members.models import MemberProfile
    member_user = make_user(role=Role.MEMBER)
    member = MemberProfile.objects.create(hub=hub, user=member_user, phone_number="0711223344")
    sale_member = Sale.objects.create(
        hub=hub,
        member=member,
        agent=None,
        status=Sale.Status.COMPLETED,
        completed_at=timezone.make_aware(datetime.combine(timezone.localdate(), time(12))),
        total=Decimal("200.00"),
    )
    SalesAgentCommission.objects.create(
        sale=sale_member,
        agent=member_user,
        rate=Decimal("0.1000"),
        base_amount=Decimal("200.00"),
        amount=Decimal("20.00"),
        status=SalesAgentCommission.Status.APPROVED,
    )

    from apps.services.models import ServiceProvider, HubResource, ServiceType, ServiceBooking
    from apps.commissions.models import ServiceCommission
    provider = ServiceProvider.objects.create(name="Service Pro", provider_type="EXTERNAL")
    service_type = ServiceType.objects.create(code="SRV-01", name="Service 1")
    resource = HubResource.objects.create(hub=hub, service_type=service_type, name="Resource 1", code="RES-1")
    booking = ServiceBooking.objects.create(
        hub=hub,
        resource=resource,
        service_type=service_type,
        service_provider=provider,
        start_date=timezone.make_aware(datetime.combine(timezone.localdate(), time(10))),
        end_date=timezone.make_aware(datetime.combine(timezone.localdate(), time(12))),
        quantity=Decimal("4.00"),
        unit_rate=Decimal("50.00"),
        total_amount=Decimal("200.00"),
        status=ServiceBooking.Status.COMPLETED,
    )
    ServiceCommission.objects.create(
        provider=provider,
        booking=booking,
        rate=Decimal("0.1500"),
        base_amount=Decimal("200.00"),
        amount=Decimal("30.00"),
        status=ServiceCommission.Status.APPROVED,
    )

    client.force_login(admin)
    response = client.get(reverse("core:dashboard"))
    assert response.status_code == 200
    assert ("Commission Earned by Sales Agents", Decimal("10.00")) in response.context["dashboard_stats"]
    assert ("Commission Earned by Members (Sales Agents)", Decimal("20.00")) in response.context["dashboard_stats"]
    assert ("Commission Earned by Service Providers", Decimal("30.00")) in response.context["dashboard_stats"]


def test_health_check_endpoint(client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"

    response2 = client.get("/health/")
    assert response2.status_code == 200
    assert response2.json()["status"] == "ok"

