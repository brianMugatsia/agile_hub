from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import Role
from apps.beneficiaries.models import BeneficiaryProfile, Business
from apps.core.scoping import scope_queryset
from apps.finance.forms import CashFlowForm
from apps.finance.models import Asset, CashFlow, IncomeStatement, IncomeStatementItem
from apps.hubs.models import Hub, HubMembership
from apps.payroll.models import SalaryRecord, WorkerProfile
from apps.products.models import Product
from apps.sales.models import Sale, SaleItem

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "route_name",
    ["finance:break_even", "finance:projections", "finance:ratios"],
)
def test_finance_calculator_pages_render_for_authorized_user(client, make_user, route_name):
    client.force_login(make_user(role=Role.SUPER_ADMIN))

    response = client.get(reverse(route_name))

    assert response.status_code == 200


def test_break_even_calculation_is_submitted_and_rendered(client, make_user):
    client.force_login(make_user(role=Role.SUPER_ADMIN))

    response = client.get(
        reverse("finance:break_even"),
        {
            "calculate": "1",
            "fixed_costs": "100.00",
            "selling_price": "20.00",
            "variable_cost_per_unit": "10.00",
        },
    )

    assert response.status_code == 200
    assert response.context["result"]["units"] == 10
    assert "Break-even revenue" in response.content.decode()


def test_projection_calculation_is_submitted_and_rendered(client, make_user):
    client.force_login(make_user(role=Role.SUPER_ADMIN))

    response = client.get(
        reverse("finance:projections"),
        {
            "calculate": "1",
            "starting_revenue": "100.00",
            "starting_expenses": "60.00",
            "revenue_growth_percent": "10",
            "expense_growth_percent": "5",
            "periods": "2",
        },
    )

    assert response.status_code == 200
    assert [period.revenue for period in response.context["periods"]] == [
        Decimal("110.00"),
        Decimal("121.00"),
    ]


def test_financial_overview_scopes_viewer_data_to_accessible_hubs(client, make_user):
    viewer = make_user(role=Role.VIEWER)
    agent = make_user(role=Role.SALES_AGENT)
    visible_hub = Hub.objects.create(code="FIN-VISIBLE", name="Visible finance hub")
    hidden_hub = Hub.objects.create(code="FIN-HIDDEN", name="Hidden finance hub")
    HubMembership.objects.create(hub=visible_hub, user=viewer)
    product = Product.objects.create(
        sku="FIN-COST", name="Finance cost item", selling_price=Decimal("20.00")
    )
    today = timezone.localdate()
    visible_sale = Sale.objects.create(
        hub=visible_hub,
        agent=agent,
        status=Sale.Status.COMPLETED,
        completed_at=timezone.now(),
        total=Decimal("25.00"),
    )
    hidden_sale = Sale.objects.create(
        hub=hidden_hub,
        agent=agent,
        status=Sale.Status.COMPLETED,
        completed_at=timezone.now(),
        total=Decimal("100.00"),
    )
    SaleItem.objects.create(
        sale=visible_sale, product=product, quantity=2, unit_price=Decimal("12.50"),
        unit_cost=Decimal("4.00"),
    )
    SaleItem.objects.create(
        sale=hidden_sale, product=product, quantity=10, unit_price=Decimal("10.00"),
        unit_cost=Decimal("9.00"),
    )
    visible_worker_user = make_user(role=Role.WORKER)
    hidden_worker_user = make_user(role=Role.WORKER)
    visible_worker = WorkerProfile.objects.create(
        user=visible_worker_user,
        hub=visible_hub,
        employee_code="FIN-VISIBLE-WORKER",
        job_title="Operator",
        monthly_salary=Decimal("300.00"),
        hired_on=today,
    )
    hidden_worker = WorkerProfile.objects.create(
        user=hidden_worker_user,
        hub=hidden_hub,
        employee_code="FIN-HIDDEN-WORKER",
        job_title="Operator",
        monthly_salary=Decimal("900.00"),
        hired_on=today,
    )
    for worker, amount in ((visible_worker, Decimal("300.00")), (hidden_worker, Decimal("900.00"))):
        SalaryRecord.objects.create(
            worker=worker,
            period_start=today,
            period_end=today,
            gross_amount=amount,
            status=SalaryRecord.Status.PENDING,
        )
    for hub, amount in ((visible_hub, Decimal("11.00")), (hidden_hub, Decimal("70.00"))):
        statement = IncomeStatement.objects.create(
            hub=hub,
            period_start=today,
            period_end=today,
        )
        IncomeStatementItem.objects.create(
            statement=statement,
            label="Operating cost",
            amount=amount,
            is_expense=True,
        )
    client.force_login(viewer)

    response = client.get(reverse("finance:income_statement"), {"start": today.isoformat()})

    assert response.status_code == 200
    assert response.context["period_start"] == today
    assert response.context["period_end"] == today
    assert response.context["revenue"] == Decimal("25.00")
    assert response.context["cost_of_goods"] == Decimal("8.00")
    assert response.context["payroll"] == Decimal("300.00")
    assert response.context["manual_expenses"] == Decimal("11.00")


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"start": "2026-1-01"}, "start date"),
        ({"end": "2025-02-30"}, "end date"),
        ({"start": "2024-01-01", "end": "2025-01-01"}, "366 days"),
        ({"start": "2025-02-02", "end": "2025-02-01"}, "on or after"),
    ],
)
def test_financial_overview_rejects_invalid_periods(client, make_user, params, message):
    client.force_login(make_user(role=Role.SUPER_ADMIN))

    response = client.get(reverse("finance:income_statement"), params)

    assert response.status_code == 400
    assert message in response.content.decode().lower()


def test_hub_scoping_includes_business_linked_assets_for_assigned_hub(make_user):
    manager = make_user(role=Role.HUB_MANAGER)
    visible_hub = Hub.objects.create(code="ASSET-VISIBLE", name="Visible asset hub")
    hidden_hub = Hub.objects.create(code="ASSET-HIDDEN", name="Hidden asset hub")
    HubMembership.objects.create(hub=visible_hub, user=manager)
    beneficiary_user = make_user(role=Role.BENEFICIARY)
    beneficiary = BeneficiaryProfile.objects.create(user=beneficiary_user)
    visible_business = Business.objects.create(
        beneficiary=beneficiary, hub=visible_hub, name="Visible business"
    )
    hidden_business = Business.objects.create(
        beneficiary=beneficiary, hub=hidden_hub, name="Hidden business"
    )
    visible_asset = Asset.objects.create(
        name="Business-only visible asset", cost=Decimal("100.00"), business=visible_business
    )
    Asset.objects.create(
        name="Hidden business-only asset", cost=Decimal("900.00"), business=hidden_business
    )
    Asset.objects.create(name="Hidden direct hub asset", cost=Decimal("300.00"), hub=hidden_hub)

    assert list(scope_queryset(Asset.objects.all(), manager)) == [visible_asset]


def test_cash_flow_form_rejects_business_from_different_hub(make_user):
    first_hub = Hub.objects.create(code="CASHFLOW-ONE", name="Cash flow hub one")
    second_hub = Hub.objects.create(code="CASHFLOW-TWO", name="Cash flow hub two")
    beneficiary_user = make_user(role=Role.BENEFICIARY)
    beneficiary = BeneficiaryProfile.objects.create(user=beneficiary_user)
    business = Business.objects.create(beneficiary=beneficiary, hub=second_hub, name="Other hub business")

    form = CashFlowForm(data={
        "direction": CashFlow.Direction.INFLOW,
        "category": "Other income",
        "amount": "25.00",
        "transaction_date": "2026-10-09",
        "hub": str(first_hub.pk),
        "business": str(business.pk),
        "reference": "",
        "description": "",
    })

    assert not form.is_valid()
    assert "business" in form.errors


def test_cash_flow_create_limits_hubs_and_businesses_to_manager_scope(
    client, make_user, roles
):
    manager = make_user(role=Role.HUB_MANAGER)
    visible_hub = Hub.objects.create(code="CASHFLOW-VISIBLE", name="Visible cash flow hub")
    hidden_hub = Hub.objects.create(code="CASHFLOW-HIDDEN", name="Hidden cash flow hub")
    HubMembership.objects.create(hub=visible_hub, user=manager)
    beneficiary_user = make_user(role=Role.BENEFICIARY)
    beneficiary = BeneficiaryProfile.objects.create(user=beneficiary_user)
    visible_business = Business.objects.create(
        beneficiary=beneficiary, hub=visible_hub, name="Visible cash flow business"
    )
    hidden_business = Business.objects.create(
        beneficiary=beneficiary, hub=hidden_hub, name="Hidden cash flow business"
    )
    client.force_login(manager)

    response = client.get(reverse("finance:cash_flow_create"))

    assert response.status_code == 200
    form = response.context["form"]
    assert list(form.fields["hub"].queryset) == [visible_hub]
    assert list(form.fields["business"].queryset) == [visible_business]
    assert hidden_business not in form.fields["business"].queryset