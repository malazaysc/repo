"""Create or update the single app user from env vars (idempotent).

Usage:
    python manage.py bootstrap_user

Reads ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD (defaults: admin/admin).
"""
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the single superuser from environment variables."

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get("ADMIN_USERNAME", "admin")
        email = os.environ.get("ADMIN_EMAIL", "admin@example.com")

        # Never bake a default password outside local dev (S6).
        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            if settings.DEBUG:
                password = "admin"
                self.stdout.write(
                    self.style.WARNING(
                        "ADMIN_PASSWORD unset — using insecure 'admin' (DEBUG only)."
                    )
                )
            else:
                raise CommandError("ADMIN_PASSWORD must be set (refusing to create a default user).")

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
