import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from organizations.factories import (
    OrganizationFactory,
    StripeCustomerFactory,
    StripeSubscriptionFactory,
)
from users.factories import UserFactory


class Command(BaseCommand):
    help = (
        "Creates the organizations, users and subscriptions described in a JSON "
        "seed file, for the frontend's end-to-end tests. Only runs where "
        "E2E_SEEDING_ENABLED is on (never in production)."
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

        for user_spec in spec["users"]:
            UserFactory(
                email=user_spec["email"],
                org_role=user_spec["role"],
                organization=organization,
                password=password,
            )
        UserFactory.create_batch(
            spec.get("extra_members", 0), organization=organization, password=password
        )
