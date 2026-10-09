import pytest
from django.urls import reverse

from apps.accounts.roles import Role
from apps.beneficiaries.models import BeneficiaryProfile, Business
from apps.hubs.models import Hub, HubMembership

pytestmark = pytest.mark.django_db


def test_admin_can_add_and_edit_beneficiaries_and_businesses(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    beneficiary_user = make_user(role=Role.BENEFICIARY, first_name="Amina", last_name="Njeri")
    hub = Hub.objects.create(code="ADMIN-BEN", name="Admin edit hub")
    beneficiary = BeneficiaryProfile.objects.create(
        user=beneficiary_user, phone_number="0711000000", hub=hub
    )
    business = Business.objects.create(beneficiary=beneficiary, name="Old name", hub=hub)
    client.force_login(admin)

    beneficiary_list = client.get(reverse("beneficiaries:list"))
    assert beneficiary_list.status_code == 200
    assert b"Edit" in beneficiary_list.content
    assert reverse("beneficiaries:detail", args=[beneficiary.pk]).encode() in beneficiary_list.content

    business_list = client.get(reverse("beneficiaries:businesses"))
    assert business_list.status_code == 200
    assert b"Add business" in business_list.content
    assert reverse("beneficiaries:business_edit", args=[business.pk]).encode() in business_list.content

    beneficiary_update = client.post(
        reverse("beneficiaries:edit", args=[beneficiary.pk]),
        {
            "user": str(beneficiary_user.pk),
            "hub": hub.pk,
            "phone_number": "0722000000",
            "national_id": "",
            "address": "Nairobi",
            "notes": "",
        },
    )
    assert beneficiary_update.status_code == 302
    beneficiary.refresh_from_db()
    assert beneficiary.phone_number == "0722000000"
    assert beneficiary.address == "Nairobi"

    business_update = client.post(
        reverse("beneficiaries:business_edit", args=[business.pk]),
        {
            "beneficiary": beneficiary.pk,
            "hub": hub.pk,
            "name": "New name",
            "business_type": "Retail",
            "registration_number": "",
            "phone_number": "",
            "address": "",
            "status": Business.Status.ACTIVE,
        },
    )
    assert business_update.status_code == 302
    business.refresh_from_db()
    assert business.name == "New name"


def test_admin_can_edit_profile_with_inactive_beneficiary_user(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    inactive_user = make_user(role=Role.BENEFICIARY, is_active=False)
    hub = Hub.objects.create(code="INACTIVE-BEN", name="Inactive user's hub")
    profile = BeneficiaryProfile.objects.create(user=inactive_user, hub=hub)
    client.force_login(admin)

    response = client.post(
        reverse("beneficiaries:edit", args=[profile.pk]),
        {
            "user": str(inactive_user.pk),
            "hub": hub.pk,
            "phone_number": "0712345678",
            "national_id": "",
            "address": "",
            "notes": "",
        },
    )

    assert response.status_code == 302
    profile.refresh_from_db()
    assert profile.phone_number == "0712345678"


def test_beneficiary_can_edit_only_their_own_profile_and_businesses(
    client, make_user, roles
):
    own_user = make_user(role=Role.BENEFICIARY, first_name="Own")
    hub = Hub.objects.create(code="OWN-BEN", name="Own assigned hub")
    own_profile = BeneficiaryProfile.objects.create(user=own_user, hub=hub)
    own_business = Business.objects.create(
        beneficiary=own_profile, hub=hub, name="Own business"
    )
    other_user = make_user(role=Role.BENEFICIARY, first_name="Other")
    other_profile = BeneficiaryProfile.objects.create(user=other_user)
    other_business = Business.objects.create(beneficiary=other_profile, name="Other business")
    client.force_login(own_user)

    detail = client.get(reverse("beneficiaries:detail", args=[own_profile.pk]))
    assert detail.status_code == 200
    assert b"Edit beneficiary" in detail.content
    assert b"Add business" in detail.content
    assert reverse("beneficiaries:business_edit", args=[own_business.pk]).encode() in detail.content
    assert reverse("beneficiaries:business_edit", args=[other_business.pk]).encode() not in detail.content

    own_update = client.get(reverse("beneficiaries:edit", args=[own_profile.pk]))
    assert own_update.status_code == 200
    profile_update = client.post(
        reverse("beneficiaries:edit", args=[own_profile.pk]),
        {
            "user": str(own_user.pk),
            "hub": hub.pk,
            "phone_number": "0700000000",
            "national_id": "",
            "address": "",
            "notes": "",
        },
    )
    assert profile_update.status_code == 302
    business_update = client.post(
        reverse("beneficiaries:business_edit", args=[own_business.pk]),
        {
            "beneficiary": own_profile.pk,
            "hub": hub.pk,
            "name": "Own business updated",
            "business_type": "",
            "registration_number": "",
            "phone_number": "",
            "address": "",
            "status": Business.Status.ACTIVE,
        },
    )
    assert business_update.status_code == 302
    own_business.refresh_from_db()
    assert own_business.name == "Own business updated"
    assert client.get(reverse("beneficiaries:edit", args=[other_profile.pk])).status_code == 404
    assert client.get(reverse("beneficiaries:business_edit", args=[other_business.pk])).status_code == 404


def test_roles_without_change_permission_do_not_see_edit_buttons(client, make_user, roles):
    viewer = make_user(role=Role.VIEWER)
    beneficiary_user = make_user(role=Role.BENEFICIARY)
    hub = Hub.objects.create(code="VIEW-BEN", name="Viewer beneficiary hub")
    HubMembership.objects.create(hub=hub, user=viewer)
    beneficiary = BeneficiaryProfile.objects.create(user=beneficiary_user, hub=hub)
    client.force_login(viewer)

    response = client.get(reverse("beneficiaries:list"))

    assert response.status_code == 200
    assert reverse("beneficiaries:detail", args=[beneficiary.pk]).encode() in response.content
    assert b"Edit</a>" not in response.content


def test_hub_manager_sees_only_businesses_in_their_hub(client, make_user, roles):
    manager = make_user(role=Role.HUB_MANAGER)
    accessible_hub = Hub.objects.create(code="DETAIL-ACCESS", name="Accessible")
    other_hub = Hub.objects.create(code="DETAIL-OTHER", name="Not accessible")
    HubMembership.objects.create(hub=accessible_hub, user=manager)
    beneficiary_user = make_user(role=Role.BENEFICIARY)
    beneficiary = BeneficiaryProfile.objects.create(user=beneficiary_user, hub=accessible_hub)
    Business.objects.create(beneficiary=beneficiary, hub=accessible_hub, name="Visible business")
    Business.objects.create(beneficiary=beneficiary, hub=other_hub, name="Hidden business")
    client.force_login(manager)

    response = client.get(reverse("beneficiaries:detail", args=[beneficiary.pk]))

    assert response.status_code == 200
    assert b"Visible business" in response.content
    assert b"Hidden business" not in response.content
    assert b"Edit beneficiary" not in response.content