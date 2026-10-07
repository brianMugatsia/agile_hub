from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.roles import Role

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