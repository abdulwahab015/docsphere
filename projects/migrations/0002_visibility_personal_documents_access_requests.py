import django.db.models.deletion
import django_extensions.db.fields
from django.conf import settings
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def backfill_document_organization(apps, schema_editor):
    Document = apps.get_model("projects", "Document")
    Project = apps.get_model("projects", "Project")
    Document.objects.filter(organization__isnull=True, project__isnull=False).update(
        organization=Subquery(
            Project.objects.filter(pk=OuterRef("project_id")).values("organization_id")[
                :1
            ]
        )
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="visibility",
            field=models.CharField(
                choices=[("PRIVATE", "Private"), ("PUBLIC", "Public")],
                default="PRIVATE",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="documents",
                to="organizations.organization",
            ),
        ),
        migrations.RunPython(backfill_document_organization, noop),
        migrations.AlterField(
            model_name="document",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="documents",
                to="organizations.organization",
            ),
        ),
        migrations.AlterField(
            model_name="document",
            name="project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="documents",
                to="projects.project",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="visibility",
            field=models.CharField(
                choices=[("PRIVATE", "Private"), ("PUBLIC", "Public")],
                default="PRIVATE",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="DocumentAccessRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("APPROVED", "Approved"),
                            ("DENIED", "Denied"),
                        ],
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="access_requests",
                        to="projects.document",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_access_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_document_access_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="documentaccessrequest",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "PENDING")),
                fields=("document", "requested_by"),
                name="unique_pending_access_request_per_user_per_document",
                violation_error_message="You already have a pending request for this document.",
            ),
        ),
    ]
