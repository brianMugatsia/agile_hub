from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.roles import Role
from apps.hubs.models import Hub, HubMembership
from apps.payroll.models import SalaryRecord, WorkerProfile

pytestmark = pytest.mark.django_db


def test_admin_can_edit_worker_profile_from_worker_list(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    worker_user = make_user(role=Role.WORKER)
    hub = Hub.objects.create(code="WORKER-EDIT", name="Worker edit hub")
    worker = WorkerProfile.objects.create(
        user=worker_user,
        hub=hub,
        employee_code="WORKER-EDIT-1",
        job_title="Storekeeper",
        monthly_salary=Decimal("500.00"),
        hired_on=date(2025, 1, 1),
    )
    client.force_login(admin)

    edit_url = reverse("payroll:worker_edit", args=[worker.pk])
    list_response = client.get(reverse("payroll:worker_list"))
    edit_page = client.get(edit_url)

    assert edit_url.encode() in list_response.content
    assert edit_page.status_code == 200
    assert b'name="user"' not in edit_page.content
    response = client.post(
        edit_url,
        {
            "hub": hub.pk,
            "employee_code": worker.employee_code,
            "job_title": "Senior storekeeper",
            "monthly_salary": "650.00",
            "hired_on": "2025-01-01",
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    worker.refresh_from_db()
    assert worker.user == worker_user
    assert worker.job_title == "Senior storekeeper"
    assert worker.monthly_salary == Decimal("650.00")


def test_worker_edit_is_scoped_to_manager_hubs(client, make_user, roles):
    manager = make_user(role=Role.HUB_MANAGER)
    worker_user = make_user(role=Role.WORKER)
    own_hub = Hub.objects.create(code="WORKER-OWN", name="Manager's hub")
    other_hub = Hub.objects.create(code="WORKER-OTHER", name="Other hub")
    HubMembership.objects.create(hub=own_hub, user=manager)
    worker = WorkerProfile.objects.create(
        user=worker_user,
        hub=other_hub,
        employee_code="WORKER-OUTSIDE",
        job_title="Operator",
        monthly_salary=Decimal("300.00"),
        hired_on=date(2025, 1, 1),
    )
    client.force_login(manager)

    assert client.get(reverse("payroll:worker_edit", args=[worker.pk])).status_code == 404


def test_worker_hub_cannot_change_after_salary_records_exist(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    worker_user = make_user(role=Role.WORKER)
    first_hub = Hub.objects.create(code="WORKER-SALARY-1", name="Current hub")
    second_hub = Hub.objects.create(code="WORKER-SALARY-2", name="New hub")
    worker = WorkerProfile.objects.create(
        user=worker_user,
        hub=first_hub,
        employee_code="WORKER-SALARY",
        job_title="Operator",
        monthly_salary=Decimal("300.00"),
        hired_on=date(2025, 1, 1),
    )
    SalaryRecord.objects.create(
        worker=worker,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        gross_amount=Decimal("300.00"),
    )
    client.force_login(admin)

    response = client.post(
        reverse("payroll:worker_edit", args=[worker.pk]),
        {
            "hub": second_hub.pk,
            "employee_code": worker.employee_code,
            "job_title": worker.job_title,
            "monthly_salary": "300.00",
            "hired_on": "2025-01-01",
            "is_active": "on",
        },
    )

    assert response.status_code == 200
    assert b"cannot be changed after salary records" in response.content
    worker.refresh_from_db()
    assert worker.hub == first_hub