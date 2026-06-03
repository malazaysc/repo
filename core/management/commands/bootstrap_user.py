"""Create or update the single app user from env vars (idempotent).

Usage:
    python manage.py bootstrap_user

Reads ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD (defaults: admin/admin).
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the single superuser from environment variables."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("ADMIN_USERNAME", "admin")
        email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        password = os.environ.get("ADMIN_PASSWORD", "admin")

        user, created = User.objects.get_or_create(
            username=username, defaults={"email": email}
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} user '{username}'."))
