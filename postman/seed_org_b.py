"""Seeds a second, fixed organization used only as a tenant-isolation target
in the Postman edge-case tests (cross-org project fetch / cross-org share
attempt). Run with: python manage.py shell < postman/seed_org_b.py

Idempotent - safe to re-run after a fresh migrate/flush.
"""

from django.contrib.auth import get_user_model

from organizations.models import Organization
from projects.models import Project

User = get_user_model()

org_b, _ = Organization.objects.get_or_create(
    name="Bravo Inc",
    defaults={"billing_email": "billing@bravoinc.com"},
)

admin_b, created = User.objects.get_or_create(
    email="admin@bravoinc.com",
    defaults={"organization": org_b, "org_role": "ADMIN", "is_active": True},
)
if created:
    admin_b.set_password("Bravo-Demo-2026!")
    admin_b.save()

project_b, _ = Project.objects.get_or_create(
    organization=org_b,
    name="Bravo Confidential Roadmap",
    defaults={
        "description": "Should never be visible to Nimbus Labs.",
        "created_by": admin_b,
    },
)

print("ORG_B_ID:", org_b.pk)
print("ORG_B_ADMIN_USER_ID:", admin_b.pk)
print("ORG_B_PROJECT_ID:", project_b.pk)
