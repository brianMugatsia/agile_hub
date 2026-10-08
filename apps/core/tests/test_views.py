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
    previous_month = today.replace(day=1) - timedelta(days=1)
    current_month_end = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    current_sale = make_completed_sale(
        hub=hub, agent=agent, completed_on=today.replace(day=1), total=Decimal("20.00")
    )
    make_completed_sale(
        hub=hub, agent=agent, completed_on=previous_month, total=Decimal("10.00")
    )
    client.force_login(admin)

    default_response = client.get(reverse("core:dashboard"))
    assert default_response.status_code == 200
    assert default_response.context["date_start"] == today.replace(day=1)
    assert default_response.context["date_end"] == current_month_end
    assert b'name="start_date"' in default_response.content
    assert b'name="end_date"' in default_response.content
    assert b'class="dash-range"' in default_response.content
    assert b'class="input" id="dashboard-start-date"' in default_response.content
    assert b'aria-label="Filter dashboard activity dates"' in default_response.content
    assert ("Completed sales", 1) in default_response.context["dashboard_stats"]
    assert list(default_response.context["recent_sales"]) == [current_sale]

    filtered_response = client.get(
        reverse("core:dashboard"),
        {"start_date": previous_month.isoformat(), "end_date": previous_month.isoformat()},
    )
    assert ("Completed sales", 1) in filtered_response.context["dashboard_stats"]
    assert ("Sales value", Decimal("10.00")) in filtered_response.context["dashboard_stats"]
    assert [sale.completed_at.date() for sale in filtered_response.context["recent_sales"]] == [
        previous_month
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
    assert response.context["date_start"] == timezone.localdate().replace(day=1)


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

    assert ("Completed sales", 1) in response.context["dashboard_stats"]
    assert ("Sales value", Decimal("12.00")) in response.context["dashboard_stats"]
    assert list(response.context["recent_sales"]) == [included]


def test_dashboard_low_stock_count_excludes_inactive_and_non_reorder_products(client, make_user):
    admin = make_user(role=Role.ADMIN)
    hub = Hub.objects.create(code="DASH-STOCK", name="Stock dashboard")
    low_stock = Product.objects.create(
        sku="DASH-LOW", name="Low stock", selling_price="10.00", reorder_level=4
    )
    no_reorder = Product.objects.create(
        sku="DASH-NOREORDER", name="No reorder", selling_price="10.00"
    )
    inactive = Product.objects.create(
        sku="DASH-INACTIVE",
        name="Inactive",
        selling_price="10.00",
        reorder_level=4,
        is_active=False,
    )
    InventoryBalance.objects.create(hub=hub, product=low_stock, quantity=4)
    InventoryBalance.objects.create(hub=hub, product=no_reorder, quantity=0)
    InventoryBalance.objects.create(hub=hub, product=inactive, quantity=0)
    client.force_login(admin)

    response = client.get(reverse("core:dashboard"))

    assert response.context["low_stock_count"] == 1
    assert ("Low stock items", 1) in response.context["dashboard_stats"]


def test_hub_manager_low_stock_count_is_scoped_to_active_member_hubs(client, make_user):
    manager = make_user(role=Role.HUB_MANAGER)
    visible_hub = Hub.objects.create(code="DASH-STOCK-VISIBLE", name="Visible stock")
    inactive_hub = Hub.objects.create(
        code="DASH-STOCK-INACTIVE", name="Inactive stock", status=Hub.Status.INACTIVE
    )
    hidden_hub = Hub.objects.create(code="DASH-STOCK-HIDDEN", name="Hidden stock")
    HubMembership.objects.create(hub=visible_hub, user=manager)
    product = Product.objects.create(
        sku="DASH-MANAGER-LOW", name="Manager low stock", selling_price="10.00", reorder_level=2
    )
    InventoryBalance.objects.create(hub=visible_hub, product=product, quantity=1)
    InventoryBalance.objects.create(hub=inactive_hub, product=product, quantity=1)
    InventoryBalance.objects.create(hub=hidden_hub, product=product, quantity=1)
    client.force_login(manager)

    response = client.get(reverse("core:dashboard"))

    assert response.context["low_stock_count"] == 1
    assert ("Low stock items", 1) in response.context["dashboard_stats"]


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