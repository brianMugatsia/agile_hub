import pytest
from django.urls import reverse

from apps.accounts.roles import Role
from apps.members.models import MemberProfile, Business
from apps.hubs.models import Hub, HubMembership

pytestmark = pytest.mark.django_db


def test_admin_can_add_and_edit_members_and_businesses(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    member_user = make_user(role=Role.MEMBER, first_name="Amina", last_name="Njeri")
    hub = Hub.objects.create(code="ADMIN-BEN", name="Admin edit hub")
    member = MemberProfile.objects.create(
        user=member_user, phone_number="0711000000", hub=hub
    )
    business = Business.objects.create(member=member, name="Old name", hub=hub)
    client.force_login(admin)

    member_list = client.get(reverse("members:list"))
    assert member_list.status_code == 200
    assert b"Edit" in member_list.content
    assert reverse("members:detail", args=[member.pk]).encode() in member_list.content

    business_list = client.get(reverse("members:businesses"))
    assert business_list.status_code == 200
    assert b"Add business" in business_list.content
    assert reverse("members:business_edit", args=[business.pk]).encode() in business_list.content

    member_update = client.post(
        reverse("members:edit", args=[member.pk]),
        {
            "user": str(member_user.pk),
            "hub": hub.pk,
            "phone_number": "0722000000",
            "national_id": "",
            "address": "Nairobi",
            "notes": "",
        },
    )
    assert member_update.status_code == 302
    member.refresh_from_db()
    assert member.phone_number == "0722000000"
    assert member.address == "Nairobi"

    business_update = client.post(
        reverse("members:business_edit", args=[business.pk]),
        {
            "member": member.pk,
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


def test_admin_can_edit_profile_with_inactive_member_user(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    inactive_user = make_user(role=Role.MEMBER, is_active=False)
    hub = Hub.objects.create(code="INACTIVE-BEN", name="Inactive user's hub")
    profile = MemberProfile.objects.create(user=inactive_user, hub=hub)
    client.force_login(admin)

    response = client.post(
        reverse("members:edit", args=[profile.pk]),
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


def test_member_can_edit_only_their_own_profile_and_businesses(
    client, make_user, roles
):
    own_user = make_user(role=Role.MEMBER, first_name="Own")
    hub = Hub.objects.create(code="OWN-BEN", name="Own assigned hub")
    own_profile = MemberProfile.objects.create(user=own_user, hub=hub)
    own_business = Business.objects.create(
        member=own_profile, hub=hub, name="Own business"
    )
    other_user = make_user(role=Role.MEMBER, first_name="Other")
    other_profile = MemberProfile.objects.create(user=other_user)
    other_business = Business.objects.create(member=other_profile, name="Other business")
    client.force_login(own_user)

    detail = client.get(reverse("members:detail", args=[own_profile.pk]))
    assert detail.status_code == 200
    assert b"Edit member" in detail.content
    assert b"Add business" in detail.content
    assert reverse("members:business_edit", args=[own_business.pk]).encode() in detail.content
    assert reverse("members:business_edit", args=[other_business.pk]).encode() not in detail.content

    own_update = client.get(reverse("members:edit", args=[own_profile.pk]))
    assert own_update.status_code == 200
    profile_update = client.post(
        reverse("members:edit", args=[own_profile.pk]),
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
        reverse("members:business_edit", args=[own_business.pk]),
        {
            "member": own_profile.pk,
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
    assert client.get(reverse("members:edit", args=[other_profile.pk])).status_code == 404
    assert client.get(reverse("members:business_edit", args=[other_business.pk])).status_code == 404


def test_roles_without_change_permission_do_not_see_edit_buttons(client, make_user, roles):
    viewer = make_user(role=Role.VIEWER)
    member_user = make_user(role=Role.MEMBER)
    hub = Hub.objects.create(code="VIEW-BEN", name="Viewer member hub")
    HubMembership.objects.create(hub=hub, user=viewer)
    member = MemberProfile.objects.create(user=member_user, hub=hub)
    client.force_login(viewer)

    response = client.get(reverse("members:list"))

    assert response.status_code == 200
    assert reverse("members:detail", args=[member.pk]).encode() in response.content
    assert b"Edit</a>" not in response.content


def test_hub_manager_sees_only_businesses_in_their_hub(client, make_user, roles):
    manager = make_user(role=Role.HUB_MANAGER)
    accessible_hub = Hub.objects.create(code="DETAIL-ACCESS", name="Accessible")
    other_hub = Hub.objects.create(code="DETAIL-OTHER", name="Not accessible")
    HubMembership.objects.create(hub=accessible_hub, user=manager)
    member_user = make_user(role=Role.MEMBER)
    member = MemberProfile.objects.create(user=member_user, hub=accessible_hub)
    Business.objects.create(member=member, hub=accessible_hub, name="Visible business")
    Business.objects.create(member=member, hub=other_hub, name="Hidden business")
    client.force_login(manager)

    response = client.get(reverse("members:detail", args=[member.pk]))

    assert response.status_code == 200
    assert b"Visible business" in response.content
    assert b"Hidden business" not in response.content
    assert b"Edit member" in response.content