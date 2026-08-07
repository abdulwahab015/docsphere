from django.core.management.base import BaseCommand
from django.db import transaction

from organizations.models import Organization, User


class Command(BaseCommand):
    help = "Creates a platform organization and a superuser in one step."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--org-name", default="Platform")

    def handle(self, *args, **options):
        with transaction.atomic():
            org, _ = Organization.objects.get_or_create(name=options["org_name"])
            user = User.objects.create_superuser(
                email=options["email"],
                username=options["email"],
                password=options["password"],
                organization=org,
                org_role=User.OrgRole.ADMIN,
            )
        self.stdout.write(
            self.style.SUCCESS(f"Created superuser {user.email} in {org.name}")
        )
