import pytest
from django.urls import reverse

from apps.accounts.roles import Role
from apps.members.models import MemberProfile, Business
from apps.hubs.models import Hub, HubMembership
from apps.services.models import ServiceType, ServiceCategory

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

    business_list = client.get(reverse("members:contributions"))
    assert business_list.status_code == 200
    assert b"Add contribution" in business_list.content
    assert reverse("members:contribution_edit", args=[business.pk]).encode() in business_list.content

    member_update = client.post(
        reverse("members:edit", args=[member.pk]),
        {
            "first_name": "Amina Updated",
            "last_name": "Njeri Updated",
            "phone_number": "0722000000",
            "national_id": "",
            "location": "Nairobi",
            "notes": "",
        },
    )
    assert member_update.status_code == 302
    member.refresh_from_db()
    assert member.phone_number == "0722000000"
    assert member.location == "Nairobi"
    assert member.user.first_name == "Amina Updated"
    assert member.user.last_name == "Njeri Updated"

    business_update = client.post(
        reverse("members:contribution_edit", args=[business.pk]),
        {
            "member": member.pk,
            "hub": hub.pk,
            "name": "New name",
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
    inactive_user = make_user(role=Role.MEMBER, is_active=False, first_name="Inactive", last_name="User")
    hub = Hub.objects.create(code="INACTIVE-BEN", name="Inactive user's hub")
    profile = MemberProfile.objects.create(user=inactive_user, hub=hub)
    client.force_login(admin)

    response = client.post(
        reverse("members:edit", args=[profile.pk]),
        {
            "first_name": "Inactive",
            "last_name": "User",
            "phone_number": "0712345678",
            "national_id": "",
            "location": "",
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
    assert b"Add contribution" in detail.content
    assert reverse("members:contribution_edit", args=[own_business.pk]).encode() in detail.content
    assert reverse("members:contribution_edit", args=[other_business.pk]).encode() not in detail.content

    own_update = client.get(reverse("members:edit", args=[own_profile.pk]))
    assert own_update.status_code == 200
    profile_update = client.post(
        reverse("members:edit", args=[own_profile.pk]),
        {
            "first_name": "Own",
            "last_name": "User",
            "phone_number": "0700000000",
            "national_id": "",
            "location": "",
            "notes": "",
        },
    )
    assert profile_update.status_code == 302
    business_update = client.post(
        reverse("members:contribution_edit", args=[own_business.pk]),
        {
            "member": own_profile.pk,
            "hub": hub.pk,
            "name": "Own business updated",
            "phone_number": "",
            "address": "",
            "status": Business.Status.ACTIVE,
        },
    )
    assert business_update.status_code == 302
    own_business.refresh_from_db()
    assert own_business.name == "Own business updated"
    assert client.get(reverse("members:edit", args=[other_profile.pk])).status_code == 404
    assert client.get(reverse("members:contribution_edit", args=[other_business.pk])).status_code == 404


def test_contribution_form_has_contribution_name_label_and_placeholder(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    client.force_login(admin)
    response = client.get(reverse("members:contribution_create"))
    assert response.status_code == 200
    assert b"Contribution Name" in response.content
    assert b'placeholder="Enter contribution name"' in response.content
    assert b"business_type" not in response.content
    assert b"registration_number" not in response.content


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


def test_member_excel_upload_previews_then_creates_only_after_confirmation(
    client, make_user, roles
):
    from io import BytesIO
    from django.core.files.uploadedfile import SimpleUploadedFile
    from openpyxl import Workbook
    from apps.core.models import StagedSpreadsheetImport

    def _xlsx(headers, rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        output = BytesIO()
        workbook.save(output)
        return SimpleUploadedFile(
            "import.xlsx",
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    admin = make_user(role=Role.ADMIN)
    hub = Hub.objects.create(code="IMP-HUB", name="Import Hub")
    client.force_login(admin)
    uploaded = _xlsx(
        ["username", "first_name", "last_name", "phone_number"],
        [["johndoe", "John", "Doe", "0712345678"]],
    )
    preview = client.post(
        reverse("members:import"),
        {"file": uploaded},
    )

    assert preview.status_code == 200
    assert b"John" in preview.content
    assert not MemberProfile.objects.filter(user__username="johndoe").exists()
    staged = StagedSpreadsheetImport.objects.get(import_type="members")
    response = client.post(
        reverse("members:import"),
        {"confirm_import": "1", "stage_token": str(staged.token)},
    )

    assert response.status_code == 302
    profile = MemberProfile.objects.get(user__username="johndoe")
    assert profile.user.first_name == "John"
    assert profile.phone_number == "0712345678"
    assert profile.hub == hub
    staged.refresh_from_db()
    assert staged.consumed_at is not None
    assert staged.rows == []


def test_business_excel_upload_previews_then_creates_only_after_confirmation(
    client, make_user, roles
):
    from io import BytesIO
    from django.core.files.uploadedfile import SimpleUploadedFile
    from openpyxl import Workbook
    from apps.core.models import StagedSpreadsheetImport

    def _xlsx(headers, rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        output = BytesIO()
        workbook.save(output)
        return SimpleUploadedFile(
            "import.xlsx",
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    admin = make_user(role=Role.ADMIN)
    hub = Hub.objects.create(code="BIZ-HUB", name="Biz Hub")
    member_user = make_user(role=Role.MEMBER, username="bizowner")
    MemberProfile.objects.create(user=member_user, hub=hub)
    client.force_login(admin)

    uploaded = _xlsx(
        ["member_username", "name", "business_type", "status"],
        [["bizowner", "Super Shop", "Retail", "ACTIVE"]],
    )
    preview = client.post(
        reverse("members:contribution_import"),
        {"file": uploaded},
    )

    assert preview.status_code == 200
    assert b"Super Shop" in preview.content
    assert not Business.objects.filter(name="Super Shop").exists()
    staged = StagedSpreadsheetImport.objects.get(import_type="businesses")
    response = client.post(
        reverse("members:contribution_import"),
        {"confirm_import": "1", "stage_token": str(staged.token)},
    )

    assert response.status_code == 302
    biz = Business.objects.get(name="Super Shop")
    assert biz.member.user.username == "bizowner"
    assert biz.business_type == "Retail"
    assert biz.hub == hub
    staged.refresh_from_db()
    assert staged.consumed_at is not None


def test_download_member_and_business_import_templates(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    client.force_login(admin)

    res_member = client.get(reverse("members:import_template"))
    assert res_member.status_code == 200
    assert res_member["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    res_biz = client.get(reverse("members:contribution_import_template"))
    assert res_biz.status_code == 200
    assert res_biz["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_admin_can_add_member_with_location_and_services(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    hub = Hub.objects.create(code="NEW-HUB", name="New Hub")
    admin.hub = hub
    admin.save()
    service1 = ServiceType.objects.create(code="SRV-1", name="Ripening Service", category=ServiceCategory.RIPENING)
    service2 = ServiceType.objects.create(code="SRV-2", name="Transport Service", category=ServiceCategory.TRANSPORT)
    client.force_login(admin)

    response = client.get(reverse("members:create"))
    assert response.status_code == 200
    assert b"Assigned Services" in response.content
    assert b"Location" in response.content

    create_res = client.post(
        reverse("members:create"),
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane@example.com",
            "phone_number": "0799999999",
            "national_id": "12345678",
            "location": "Test Location",
            "services": [str(service1.pk), str(service2.pk)],
            "notes": "Test Notes",
        },
    )
    assert create_res.status_code == 302
    profile = MemberProfile.objects.get(user__email="jane@example.com")
    assert profile.phone_number == "0799999999"
    assert profile.location == "Test Location"
    assert profile.hub == hub
    assert set(profile.services.all()) == {service1, service2}

    detail_res = client.get(reverse("members:detail", args=[profile.pk]))
    assert detail_res.status_code == 200
    assert b"Test Location" in detail_res.content
    assert b"Ripening Service" in detail_res.content
    assert b"Transport Service" in detail_res.content


def test_contribution_list_has_search_bar_without_shard_or_hub_filters(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    client.force_login(admin)

    response = client.get(reverse("members:contributions"))
    assert response.status_code == 200
    assert b"record-search" in response.content
    assert b"All hubs" not in response.content
    assert b"Total Contribution Expected" in response.content
    assert b"Total Collected" in response.content
    assert b"Number of Members Paid" in response.content
    assert b"Number of Members Not Paid" in response.content


def test_customer_leads_and_categories_and_upgrade(client, make_user, roles):
    admin = make_user(role=Role.ADMIN)
    hub = Hub.objects.create(code="CUST-HUB", name="Customer Hub")
    client.force_login(admin)

    lead = MemberProfile.objects.create(
        customer_type=MemberProfile.CustomerType.LEAD,
        name="Prospective Customer",
        phone_number="0700000000",
        national_id="999999",
        location="Farm Valley",
        crops="Maize, Beans, Coffee",
        hub=hub,
    )

    # Test customers list with category=lead
    res = client.get(reverse("members:customers_list") + "?category=lead")
    assert res.status_code == 200
    assert b"Prospective Customer" in res.content
    assert b"Maize, Beans, Coffee" in res.content

    # Test upgrade lead to farmer
    upgrade_res = client.post(reverse("members:customer_upgrade", args=[lead.pk]))
    assert upgrade_res.status_code == 302
    lead.refresh_from_db()
    assert lead.customer_type == MemberProfile.CustomerType.FARMER

