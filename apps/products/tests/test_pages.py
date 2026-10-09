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


def test_admin_can_edit_product_without_changing_stock_and_tracks_price_change(
    client, make_user, roles
):
    admin = make_user(role=Role.ADMIN)
    hub = Hub.objects.create(code="PRODUCT-EDIT", name="Product edit hub")
    product = Product.objects.create(
        sku="PRODUCT-EDIT-1",
        name="Editable item",
        selling_price=Decimal("24.00"),
        stock_on_hand=7,
        reorder_level=3,
    )
    InventoryBalance.objects.create(hub=hub, product=product, quantity=7)
    client.force_login(admin)

    list_response = client.get(reverse("products:list"))
    edit_url = reverse("products:edit", kwargs={"pk": product.pk})
    edit_page = client.get(edit_url)

    assert b"Edit" in list_response.content
    assert edit_url.encode() in list_response.content
    assert edit_page.status_code == 200
    assert b'name="stock_on_hand"' not in edit_page.content
    response = client.post(
        edit_url,
        {
            "sku": product.sku,
            "name": "Updated item",
            "category": "Food",
            "description": "Updated description",
            "unit": "each",
            "cost_price": "10.00",
            "selling_price": "28.00",
            "reorder_level": "4",
            "is_active": "on",
            "price_change_reason": "Supplier price increase",
        },
    )

    assert response.status_code == 302
    product.refresh_from_db()
    assert product.name == "Updated item"
    assert product.selling_price == Decimal("28.00")
    assert product.stock_on_hand == 7
    assert InventoryBalance.objects.get(hub=hub, product=product).quantity == 7
    history = ProductPriceHistory.objects.get(product=product, new_price=Decimal("28.00"))
    assert history.previous_price == Decimal("24.00")
    assert history.changed_by == admin
    assert history.reason == "Supplier price increase"
