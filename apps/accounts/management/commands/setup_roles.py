from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from apps.accounts.services import sync_role_permissions, sync_user_group


class Command(BaseCommand):
    help = "Create or refresh one Django Group per role and attach its permissions, and sync all user groups."

    def handle(self, *args, **options):
        summary = sync_role_permissions()
        for role, info in summary.items():
            self.stdout.write(f"{role:<16} {info['assigned']:>3} permissions")
            if options["verbosity"] >= 2 and info["pending"]:
                self.stdout.write(f"    waiting for later stages: {', '.join(info['pending'])}")
        
        User = get_user_model()
        user_count = 0
        for user in User.objects.all():
            sync_user_group(user)
            user_count += 1

        self.stdout.write(self.style.SUCCESS(f"Role groups are up to date and {user_count} user groups synced."))
