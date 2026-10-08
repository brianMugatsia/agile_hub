import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.urls import reverse

from apps.accounts.roles import Role
from apps.beneficiaries.models import BeneficiaryProfile, Business
from apps.hubs.models import Hub
from apps.inventory.models import InventoryBalance, InventoryTransaction
from apps.inventory.services import record_movement
from apps.payroll.models import SalaryRecord, WorkerProfile
from apps.products.models import Product
from apps.sales.models import Sale
from apps.sales.services import complete_sale

pytestmark = pytest.mark.django_db


def test_public_home_page_shows_platform_sections_and_sign_in(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert b"About" in response.content
    assert b"Contact" in response.content
    assert b"Inventory you can trust" in response.content
    assert b'data-reveal="up"' in response.content
    assert b"js/pages/landing-motion.js" in response.content
    assert b"images/brand/agile-hub-logo.webp" in response.content
    assert b"Footer navigation" in response.content
    assert b"All rights reserved." in response.content
    assert reverse("accounts:login").encode() in response.content


def test_landing_motion_has_pointer_enhancement_and_accessible_css_fallback():
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    script = (root / "static" / "js" / "pages" / "landing-motion.js").read_text(
        encoding="utf-8"
    )
    stylesheet = (root / "static" / "css" / "pages" / "landing.css").read_text(
        encoding="utf-8"
    )

    assert 'pointermove' in script and 'pointerleave' in script
    assert '(hover: hover) and (pointer: fine)' in script
    assert '@media (prefers-reduced-motion: reduce)' in stylesheet
    assert '.landing-card.is-visible .mini-meter__track i' in stylesheet
    assert '.landing-card.is-visible .mini-spark i' in stylesheet


def test_mobile_navigation_controls_are_rendered_for_signed_in_user(client, make_user):
    client.force_login(make_user(role=Role.ADMIN))

    response = client.get(reverse("core:dashboard"))

    assert response.status_code == 200
    assert b'data-sidebar-toggle' in response.content
    assert b'data-sidebar-close' in response.content
    assert b'aria-controls="sidebar"' in response.content


def test_demo_mode_banner_is_present_across_authenticated_pages(client, make_user):
    client.force_login(make_user(role=Role.SUPER_ADMIN))

    with override_settings(DEMO_MODE=True):
        for route in ("core:dashboard", "sales:list", "inventory:list", "products:list"):
            response = client.get(reverse(route))
            assert response.status_code == 200
            assert b"Demo workspace" in response.content


def test_development_pages_explain_demo_data_uses_a_separate_database(client, make_user):
    client.force_login(make_user(role=Role.SUPER_ADMIN))

    with override_settings(DEMO_MODE=False, DEVELOPMENT_MODE=True):
        response = client.get(reverse("core:dashboard"))

    assert response.status_code == 200
    assert b"Development database" in response.content
    assert b"seed_demo_data --sales 30" in response.content
    assert b"separate from production" in response.content


def test_dashboard_and_operational_pages_render_current_demo_records(client, make_user):
    admin = make_user(role=Role.SUPER_ADMIN)
    agent = make_user(role=Role.SALES_AGENT)
    hub = Hub.objects.create(code="LIVE-DEMO", name="Visible demo hub")
    product = Product.objects.create(
        sku="LIVE-DEMO-01",
        name="Dashboard sample product",
        selling_price="75.00",
        cost_price="40.00",
    )
    record_movement(
        hub=hub,
        product=product,
        kind=InventoryTransaction.Kind.RECEIPT,
        quantity=4,
        actor=admin,
    )
    sale = complete_sale(
        hub=hub,
        agent=agent,
        actor=admin,
        items=[{"product": product.pk, "quantity": 1}],
        customer_name="Visible demo customer",
        payment_reference="LIVE-DEMO-SALE-1",
    )
    client.force_login(admin)

    dashboard = client.get(reverse("core:dashboard"))
    assert dashboard.status_code == 200
    assert ("Completed sales", 1) in dashboard.context["dashboard_stats"]
    assert str(sale.total).encode() in dashboard.content
    assert b"Visible demo customer" in dashboard.content
    assert b"Dashboard sample product" in dashboard.content

    sales_page = client.get(reverse("sales:list"))
    assert sales_page.status_code == 200
    assert sales_page.context["page_obj"].paginator.count == 1
    assert b"Visible demo customer" in sales_page.content

    inventory_page = client.get(reverse("inventory:list"))
    assert inventory_page.status_code == 200
    assert inventory_page.context["page_obj"].paginator.count == 2
    assert b"Dashboard sample product" in inventory_page.content

    products_page = client.get(reverse("products:list"))
    assert products_page.status_code == 200
    assert b"Dashboard sample product" in products_page.content

    finance_page = client.get(reverse("finance:income_statement"))
    assert finance_page.status_code == 200
    assert b"75.00" in finance_page.content


def test_demo_seed_creates_real_records_and_is_idempotent(capsys):
    with override_settings(DEMO_DATA_ENABLED=True):
        call_command("seed_demo_data", sales=8, batch="pytest")

    hub = Hub.objects.get(code="DEMO-NAIROBI")
    assert Sale.objects.filter(hub=hub, payment_reference__startswith="DEMO-pytest-").count() == 8
    assert InventoryBalance.objects.filter(hub=hub).count() == 3
    assert Product.objects.filter(sku__startswith="DEMO-").count() == 3
    assert BeneficiaryProfile.objects.filter(user__username__startswith="agilehub-demo-beneficiary-").count() == 3
    assert Business.objects.filter(name__startswith="Demo ").count() == 3
    assert WorkerProfile.objects.filter(employee_code__startswith="DEMO-EMP-").count() == 3
    assert SalaryRecord.objects.filter(
        worker__employee_code__startswith="DEMO-EMP-",
        status=SalaryRecord.Status.PENDING,
    ).count() == 3
    assert "8 created" in capsys.readouterr().out

    with override_settings(DEMO_DATA_ENABLED=True):
        call_command("seed_demo_data", sales=8, batch="pytest")

    assert Sale.objects.filter(hub=hub, payment_reference__startswith="DEMO-pytest-").count() == 8
    assert WorkerProfile.objects.filter(employee_code__startswith="DEMO-EMP-").count() == 3
    assert BeneficiaryProfile.objects.filter(user__username__startswith="agilehub-demo-beneficiary-").count() == 3
    assert Business.objects.filter(name__startswith="Demo ").count() == 3
    assert SalaryRecord.objects.filter(
        worker__employee_code__startswith="DEMO-EMP-",
        status=SalaryRecord.Status.PENDING,
    ).count() == 3
    assert "0 created, 8 already present" in capsys.readouterr().out


def test_demo_seed_is_refused_under_production_settings():
    with override_settings(SETTINGS_MODULE="config.settings.production", DEMO_DATA_ENABLED=True):
        with pytest.raises(CommandError, match="disabled under production settings"):
            call_command("seed_demo_data", sales=1, batch="blocked")


def test_demo_seed_is_disabled_outside_demo_settings():
    with override_settings(DEMO_DATA_ENABLED=False):
        with pytest.raises(CommandError, match="Use development or demo settings"):
            call_command("seed_demo_data", sales=1, batch="blocked")
