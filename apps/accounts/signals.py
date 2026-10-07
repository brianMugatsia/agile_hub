from django.apps import apps as django_apps
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import sync_role_permissions, sync_user_group


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="accounts_sync_user_group")
def sync_group_on_user_save(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    sync_user_group(instance)


def sync_roles_after_migrate(sender, **kwargs):
    """Refresh role permissions once, after the last app has created its permissions."""
    last = [config for config in django_apps.get_app_configs() if config.models_module][-1]
    if sender.label == last.label:
        sync_role_permissions()