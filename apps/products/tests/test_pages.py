from decimal import Decimal

import pytest

from django.urls import reverse

from apps.accounts.roles import Role
from apps.hubs.models import Hub
from apps.inventory.models import InventoryBalance
from apps.products.models import Product, ProductPriceHistory

pytestmark = pytest.mark.django_db


def test_product_list_links_to_detail_and_product_reports(client, make_user):
    admin = make_user(role=Role.ADMIN)
    hub = Hub.objects.create(code="PRODUCT-PAGE", name="Product page hub")
    product = Product.objects.create(
        sku="PRODUCT-PAGE-1",
        name="Product page item",
        selling_price=Decimal("24.00"),
        reorder_level=5,
    )
    InventoryBalance.objects.create(hub=hub, product=product, quantity=2)
    ProductPriceHistory.objects.create(
        product=product,
        previous_price=Decimal("20.00"),
        new_price=Decimal("24.00"),
        changed_by=admin,
        reason="Updated pricing",
    )
    client.force_login(admin)

    list_response = client.get(reverse("products:list"))
    detail_response = client.get(reverse("products:detail", kwargs={"pk": product.pk}))
    history_response = client.get(reverse("products:price_history", kwargs={"pk": product.pk}))
    low_stock_response = client.get(reverse("products:low_stock_report"))

    assert list_response.status_code == 200
    assert reverse("products:detail", kwargs={"pk": product.pk}).encode() in list_response.content
    assert detail_response.status_code == 200
    assert b"Price history" in detail_response.content
    assert history_response.status_code == 200
    assert history_response.context["price_history"].count() == 1
    assert low_stock_response.status_code == 200
    assert list(low_stock_response.context["low_stock_products"]) == [
        InventoryBalance.objects.get(hub=hub, product=product)
    ]
