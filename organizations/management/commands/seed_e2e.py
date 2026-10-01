import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from organizations.factories import (
    OrganizationFactory,
    StripeCustomerFactory,
    StripeSubscriptionFactory,
)
from projects.choices import AccessLevel
from projects.factories import ProjectFactory, ProjectPermissionFactory
from users.factories import UserFactory


class Command(BaseCommand):
    help = (
        "Creates the organizations, users, subscriptions and projects described "
        "in a JSON seed file, for the frontend's end-to-end tests. Only runs "
        "where E2E_SEEDING_ENABLED is on (never in production)."
    )

    def add_arguments(self, parser):
        parser.add_argument("seed_file", help="Path to the JSON seed file.")

    def handle(self, *args, seed_file, **options):
        if not settings.E2E_SEEDING_ENABLED:
            raise CommandError("E2E seeding is disabled in this environment.")

        with open(seed_file, encoding="utf-8") as seed_json:
            seed = json.load(seed_json)

        with transaction.atomic():
            for organization_spec in seed["organizations"]:
                self._seed_organization(organization_spec, seed["password"])

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {len(seed['organizations'])} organizations.")
        )

    def _seed_organization(self, spec, password):
        organization = OrganizationFactory(name=spec["name"])
        if spec["subscribed"]:
            StripeSubscriptionFactory(
                customer=StripeCustomerFactory(subscriber=organization)
            )

        users_by_email = {
            user_spec["email"]: UserFactory(
                email=user_spec["email"],
                org_role=user_spec["role"],
                organization=organization,
                password=password,
            )
            for user_spec in spec["users"]
        }
        UserFactory.create_batch(
            spec.get("extra_members", 0), organization=organization, password=password
        )

        for project_spec in spec.get("projects", []):
            self._seed_project(project_spec, organization, users_by_email)

    def _seed_project(self, spec, organization, users_by_email):
        """Mirrors project creation through the API: the creator gets an Owner
        permission row, then each listed share its own row."""
        owner = users_by_email[spec["owner"]]
        project = ProjectFactory(
            organization=organization,
            created_by=owner,
            name=spec["name"],
            description=spec.get("description", ""),
            visibility=spec["visibility"],
            is_active=not spec.get("in_trash", False),
        )
        ProjectPermissionFactory(
            project=project, user=owner, access_level=AccessLevel.OWNER
        )
        for email, access_level in spec.get("shared_with", {}).items():
            ProjectPermissionFactory(
                project=project, user=users_by_email[email], access_level=access_level
            )
