import pytest

from apps.accounts.roles import Role
from apps.core.scoping import scope_queryset
from apps.finance.models import IncomeStatement, IncomeStatementItem
from apps.hubs.models import Hub, HubMembership
from apps.sales.models import Sale

pytestmark = pytest.mark.django_db


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