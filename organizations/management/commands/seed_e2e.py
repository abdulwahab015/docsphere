import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from organizations.factories import (
    OrganizationFactory,
    StripeCustomerFactory,
    StripePriceFactory,
    StripeProductFactory,
    StripeSubscriptionFactory,
)
from projects.choices import AccessLevel
from projects.factories import (
    AttachmentFactory,
    DocumentFactory,
    DocumentPermissionFactory,
    ProjectFactory,
    ProjectPermissionFactory,
)
from projects.models import DocumentVersion
from subscriptions.choices import SubscriptionStatus
from users.factories import UserFactory


class Command(BaseCommand):
    help = (
        "Creates the plans (prices), organizations, users, subscriptions, projects "
        "and documents described in a JSON seed file, for the frontend's end-to-end "
        "tests. Only runs where E2E_SEEDING_ENABLED is on (never in production)."
    )

    def add_arguments(self, parser):
        parser.add_argument("seed_file", help="Path to the JSON seed file.")

    def handle(self, *args, seed_file, **options):
        if not settings.E2E_SEEDING_ENABLED:
            raise CommandError("E2E seeding is disabled in this environment.")

        with open(seed_file, encoding="utf-8") as seed_json:
            seed = json.load(seed_json)

        with transaction.atomic():
            self._seed_prices(seed.get("prices", []))
            for organization_spec in seed["organizations"]:
                self._seed_organization(organization_spec, seed["password"])

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {len(seed['organizations'])} organizations.")
        )

    def _seed_prices(self, price_specs):
        """The plans an organization can subscribe to - all recurring prices of
        the configured product, as dj-stripe would have synced them from
        Stripe."""
        if not price_specs:
            return
        product = StripeProductFactory(name="DocSphere")
        for spec in price_specs:
            StripePriceFactory(
                product=product,
                nickname=spec["nickname"],
                unit_amount=spec["unit_amount"],
                interval=spec["interval"],
            )

    def _seed_organization(self, spec, password):
        organization = OrganizationFactory(
            name=spec["name"], billing_email=spec.get("billing_email")
        )
        if spec["subscribed"]:
            StripeSubscriptionFactory(
                customer=StripeCustomerFactory(subscriber=organization),
                status=spec.get("subscription_status", SubscriptionStatus.ACTIVE),
            )

        users_by_email = {
            user_spec["email"]: UserFactory(
                email=user_spec["email"],
                name=user_spec.get("name", ""),
                org_role=user_spec["role"],
                # A signup still waiting on the link emailed to it.
                email_verified_at=(
                    timezone.now() if user_spec.get("email_verified", True) else None
                ),
                organization=organization,
                password=password,
            )
            for user_spec in spec["users"]
        }
        UserFactory.create_batch(
            spec.get("extra_members", 0), organization=organization, password=password
        )

        projects_by_name = {
            project_spec["name"]: self._seed_project(
                project_spec, organization, users_by_email
            )
            for project_spec in spec.get("projects", [])
        }
        for document_spec in spec.get("documents", []):
            self._seed_document(
                document_spec, organization, users_by_email, projects_by_name
            )

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
        return project

    def _seed_document(self, spec, organization, users_by_email, projects_by_name):
        """Mirrors document creation through the API: personal, or filed under
        a seeded project by name; the creator gets an Owner permission row and
        the first version of its history, and attaches any listed files (small
        PDFs, by name). Access to the project grants nothing here - only the
        listed shares do."""
        owner = users_by_email[spec["owner"]]
        project_name = spec.get("project")
        document = DocumentFactory(
            organization=organization,
            project=projects_by_name[project_name] if project_name else None,
            created_by=owner,
            title=spec["title"],
            content=spec.get("content", ""),
            visibility=spec["visibility"],
            is_active=not spec.get("in_trash", False),
        )
        DocumentPermissionFactory(
            document=document, user=owner, access_level=AccessLevel.OWNER
        )
        DocumentVersion.objects.record(document, owner)
        for name in spec.get("attachments", []):
            AttachmentFactory(document=document, uploaded_by=owner, name=name)
        for email, access_level in spec.get("shared_with", {}).items():
            DocumentPermissionFactory(
                document=document, user=users_by_email[email], access_level=access_level
            )
