from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.roles import Role


class UserModelTests(TestCase):
    def test_new_user_defaults_to_viewer(self):
        user = User.objects.create_user("jane", "jane@example.com", "StrongPass!234")
        self.assertEqual(user.role, Role.VIEWER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_primary_key_is_uuid(self):
        user = User.objects.create_user("jane", "jane@example.com", "StrongPass!234")
        self.assertEqual(len(str(user.pk)), 36)

    def test_email_is_stored_lowercase(self):
        user = User.objects.create_user("jane", "  Jane@Example.COM ", "StrongPass!234")
        self.assertEqual(user.email, "jane@example.com")

    def test_create_superuser_is_super_admin(self):
        user = User.objects.create_superuser("boss", "boss@example.com", "StrongPass!234")
        self.assertEqual(user.role, Role.SUPER_ADMIN)
        self.assertTrue(user.is_staff and user.is_superuser)

    def test_role_controls_admin_flags(self):
        user = User.objects.create_user("jane", "jane@example.com", "StrongPass!234", role=Role.SUPER_ADMIN)
        self.assertTrue(user.is_staff and user.is_superuser)
        user.role = Role.ADMIN
        user.save()
        user.refresh_from_db()
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_initials_and_display_name(self):
        user = User.objects.create_user(
            "jw", "jw@example.com", "StrongPass!234", first_name="Jane", last_name="Wanjiru"
        )
        self.assertEqual(user.initials, "JW")
        self.assertEqual(user.display_name, "Jane Wanjiru")