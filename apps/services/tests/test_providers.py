from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.contrib.auth.models import Permission

from apps.accounts.roles import Role
from apps.members.models import MemberProfile
from apps.services.models import ServiceProvider, ProviderType, ServiceProviderStatus
from apps.services.services import (
    register_service_provider,
    suspend_service_provider,
    reactivate_service_provider,
    check_dormant_providers,
)

pytestmark = pytest.mark.django_db


def test_internal_provider_must_have_member(make_user, roles):
    user = make_user(role=Role.MEMBER)
    member = MemberProfile.objects.create(user=user)

    provider = register_service_provider(
        provider_type=ProviderType.INTERNAL,
        name="Internal Provider 1",
        member=member,
    )
    assert provider.pk is not None
    assert provider.provider_type == ProviderType.INTERNAL
    assert provider.member == member

    with pytest.raises(ValidationError):
        register_service_provider(
            provider_type=ProviderType.INTERNAL,
            name="Invalid Internal",
            member=None,
        )


def test_external_provider_does_not_require_member(make_user, roles):
    provider = register_service_provider(
        provider_type=ProviderType.EXTERNAL,
        name="External Expert",
        member=None,
    )
    assert provider.pk is not None
    assert provider.provider_type == ProviderType.EXTERNAL
    assert provider.member is None


def test_provider_suspension_and_reactivation(make_user, roles):
    admin = make_user(role=Role.ADMIN)
    admin.user_permissions.add(
        Permission.objects.get(codename="suspend_serviceprovider"),
        Permission.objects.get(codename="reactivate_serviceprovider"),
    )
    admin.refresh_from_db()

    provider = register_service_provider(
        provider_type=ProviderType.EXTERNAL,
        name="External Consultant",
    )
    assert provider.status == ServiceProviderStatus.ACTIVE

    suspended = suspend_service_provider(provider_id=provider.pk, reason="Policy violation", actor=admin)
    assert suspended.status == ServiceProviderStatus.SUSPENDED
    assert suspended.suspension_reason == "Policy violation"

    reactivated = reactivate_service_provider(provider_id=provider.pk, actor=admin)
    assert reactivated.status == ServiceProviderStatus.ACTIVE
    assert reactivated.suspension_reason == ""


def test_dormancy_check():
    provider = register_service_provider(
        provider_type=ProviderType.EXTERNAL,
        name="Dormant Provider",
    )
    assert provider.status == ServiceProviderStatus.ACTIVE
    dormant_count = check_dormant_providers()
    assert dormant_count >= 1
    provider.refresh_from_db()
    assert provider.status == ServiceProviderStatus.DORMANT


def test_service_provider_form_service_catalogue_choices_and_display():
    from apps.services.forms import ServiceProviderForm
    from apps.services.models import ServiceCategory

    form = ServiceProviderForm()
    choices = dict(form.fields["service_category"].choices)
    assert ServiceCategory.RIPENING in choices
    assert choices[ServiceCategory.RIPENING] == "Produce Ripening"

    provider = ServiceProvider(
        provider_type=ProviderType.EXTERNAL,
        name="External Cat Provider",
        service_category=ServiceCategory.RIPENING,
    )
    assert provider.service_category_display == "Produce Ripening"

