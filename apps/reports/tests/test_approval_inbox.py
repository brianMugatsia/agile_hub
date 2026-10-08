from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.roles import Role
from apps.commissions.models import SalesAgentCommission
from apps.hubs.models import Hub, HubMembership
from apps.payroll.models import SalaryRecord, WorkerProfile
from apps.sales.models import Sale

pytestmark = pytest.mark.django_db


def _salary(*, hub, make_user, code):
    worker_user = make_user(role=Role.WORKER)
    worker = WorkerProfile.objects.create(
        user=worker_user,
        hub=hub,
        employee_code=code,
        job_title="Field officer",
        monthly_salary=Decimal("1500.00"),
        hired_on=date(2024, 1, 1),
    )
    return SalaryRecord.objects.create(
        worker=worker,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        gross_amount=Decimal("1500.00"),
        deductions=Decimal("100.00"),
        status=SalaryRecord.Status.PENDING,
    )


def _commission(*, hub, make_user):
    agent = make_user(role=Role.SALES_AGENT)
    sale = Sale.objects.create(
        hub=hub,
        agent=agent,
        total=Decimal("200.00"),
        status=Sale.Status.COMPLETED,
    )
    return SalesAgentCommission.objects.create(
        sale=sale,
        agent=agent,
        rate=Decimal("0.0500"),
        base_amount=Decimal("200.00"),
        amount=Decimal("10.00"),
        status=SalesAgentCommission.Status.PENDING,
    )


def test_approval_inbox_shows_pending_salary_and_commission(client, make_user, roles):
    hub = Hub.objects.create(code="APR-1", name="North Hub")
    finance = make_user(role=Role.FINANCE_OFFICER)
    HubMembership.objects.create(hub=hub, user=finance)
    _salary(hub=hub, make_user=make_user, code="APR-EMP-1")
    _commission(hub=hub, make_user=make_user)

    client.force_login(finance)
    response = client.get(reverse("reports:approvals"))

    assert response.status_code == 200
    assert b"Pending salaries" in response.content
    assert b"Pending sales-agent commissions" in response.content
    assert b"North Hub" in response.content
    assert b"Approval inbox" in response.content
    assert response.content.count(b">Approve</button>") == 2
    assert reverse("reports:approvals").encode() in response.content


def test_approval_inbox_is_scoped_to_finance_users_hubs(client, make_user, roles):
    in_scope_hub = Hub.objects.create(code="APR-2", name="In-scope Hub")
    out_of_scope_hub = Hub.objects.create(code="APR-3", name="Out-of-scope Hub")
    finance = make_user(role=Role.FINANCE_OFFICER)
    HubMembership.objects.create(hub=in_scope_hub, user=finance)
    _salary(hub=in_scope_hub, make_user=make_user, code="APR-EMP-2")
    _commission(hub=in_scope_hub, make_user=make_user)
    _salary(hub=out_of_scope_hub, make_user=make_user, code="APR-EMP-3")
    _commission(hub=out_of_scope_hub, make_user=make_user)

    client.force_login(finance)
    response = client.get(reverse("reports:approvals"))

    assert response.status_code == 200
    assert b"In-scope Hub" in response.content
    assert b"Out-of-scope Hub" not in response.content


def test_approval_inbox_and_actions_require_approval_permissions(client, make_user, roles):
    hub = Hub.objects.create(code="APR-4", name="Restricted Hub")
    salary = _salary(hub=hub, make_user=make_user, code="APR-EMP-4")
    commission = _commission(hub=hub, make_user=make_user)
    worker = make_user(role=Role.WORKER)
    client.force_login(worker)

    assert client.get(reverse("reports:approvals")).status_code == 403
    assert client.post(reverse("reports:approve_salary", args=[salary.pk])).status_code == 403
    assert client.post(reverse("reports:approve_commission", args=[commission.pk])).status_code == 403


def test_inbox_approvals_call_existing_lifecycle_services(client, make_user, roles):
    hub = Hub.objects.create(code="APR-5", name="Approvals Hub")
    finance = make_user(role=Role.FINANCE_OFFICER)
    HubMembership.objects.create(hub=hub, user=finance)
    salary = _salary(hub=hub, make_user=make_user, code="APR-EMP-5")
    commission = _commission(hub=hub, make_user=make_user)
    client.force_login(finance)

    salary_response = client.post(reverse("reports:approve_salary", args=[salary.pk]))
    commission_response = client.post(reverse("reports:approve_commission", args=[commission.pk]))

    salary.refresh_from_db()
    commission.refresh_from_db()
    assert salary_response.status_code == 302
    assert commission_response.status_code == 302
    assert salary.status == SalaryRecord.Status.APPROVED
    assert salary.approved_by == finance
    assert commission.status == SalesAgentCommission.Status.APPROVED
    assert commission.approved_by == finance


def test_approval_actions_are_post_only(client, make_user, roles):
    finance = make_user(role=Role.FINANCE_OFFICER)
    client.force_login(finance)

    assert client.get(reverse("reports:approve_salary", args=[1])).status_code == 405
    assert client.get(reverse("reports:approve_commission", args=[1])).status_code == 405


def test_approval_action_rejects_records_outside_actor_hub_scope(client, make_user, roles):
    assigned_hub = Hub.objects.create(code="APR-6", name="Assigned Hub")
    other_hub = Hub.objects.create(code="APR-7", name="Other Hub")
    finance = make_user(role=Role.FINANCE_OFFICER)
    HubMembership.objects.create(hub=assigned_hub, user=finance)
    salary = _salary(hub=other_hub, make_user=make_user, code="APR-EMP-6")
    client.force_login(finance)

    response = client.post(reverse("reports:approve_salary", args=[salary.pk]))
    assert response.status_code == 403
    salary.refresh_from_db()
    assert salary.status == SalaryRecord.Status.PENDING
