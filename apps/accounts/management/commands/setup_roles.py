from django.core.management.base import BaseCommand

from apps.accounts.services import sync_role_permissions


class Command(BaseCommand):
    help = "Create or refresh one Django Group per role and attach its permissions."

    def handle(self, *args, **options):
        summary = sync_role_permissions()
        for role, info in summary.items():
            self.stdout.write(f"{role:<16} {info['assigned']:>3} permissions")
            if options["verbosity"] >= 2 and info["pending"]:
                self.stdout.write(f"    waiting for later stages: {', '.join(info['pending'])}")
        self.stdout.write(self.style.SUCCESS("Role groups are up to date."))