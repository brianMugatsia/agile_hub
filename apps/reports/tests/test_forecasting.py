from decimal import Decimal
import pytest
from django.urls import reverse

from apps.accounts.roles import Role
from apps.hubs.models import Hub, HubMembership
from apps.inventory.models import InventoryTransaction
from apps.inventory.services import record_movement
from apps.products.models import Product
from apps.sales.services import complete_sale
from apps.reports.services import get_sales_demand_forecast, get_inventory_yield_forecast

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _setup_roles(roles):
    pass


def test_forecasting_services_and_view(client, make_user):
    admin = make_user(role=Role.ADMIN)
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="FC-1", name="Forecasting Hub")
    HubMembership.objects.create(hub=hub, user=admin)
    HubMembership.objects.create(hub=hub, user=agent)

    product = Product.objects.create(
        sku="FC-PROD-1",
        name="Maize Seeds",
        selling_price=Decimal("200.00"),
        cost_price=Decimal("150.00"),
    )

    record_movement(
        hub=hub,
        product=product,
        kind=InventoryTransaction.Kind.RECEIPT,
        quantity=50,
        actor=admin,
    )

    complete_sale(
        hub=hub,
        agent=agent,
        actor=admin,
        items=[{"product": product.pk, "quantity": 10}],
        customer_name="Farmer John",
    )

    # Test services directly
    sales_forecast = get_sales_demand_forecast(hub=hub)
    assert len(sales_forecast) == 1
    assert sales_forecast[0]["product_name"] == "Maize Seeds"
    assert sales_forecast[0]["historical_quantity"] == 10
    assert sales_forecast[0]["projected_demand"] == 11  # 10 * 1.10

    yield_forecast = get_inventory_yield_forecast(hub=hub)
    assert len(yield_forecast) == 1
    assert yield_forecast[0]["product_name"] == "Maize Seeds"
    assert yield_forecast[0]["current_stock"] == 40  # 50 - 10

    # Test view
    client.force_login(admin)
    response = client.get(reverse("reports:forecasting"))
    assert response.status_code == 200
    assert b"Predictive Analytics" in response.content
    assert b"Maize Seeds" in response.content
    assert b"Sales Demand Forecasting" in response.content
    assert b"Inventory Yield &amp; Reorder Alerts" in response.content or b"Inventory Yield" in response.content
