from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from audit.choices import AuditVerb
from audit.constants import AUDIT_EVENT_RETENTION
from audit.factories import AuditEventFactory
from audit.models import AuditEvent
from audit.tasks import remove_expired_audit_events_task
from core.tests import AssumeActiveSubscription
from organizations.factories import OrganizationFactory
from projects.choices import AccessLevel, Visibility
from projects.factories import (
    AttachmentFactory,
    DocumentAccessRequestFactory,
    DocumentFactory,
    DocumentPermissionFactory,
    ProjectFactory,
    ProjectPermissionFactory,
)
from projects.tests import PDF, TemporaryMediaRoot
from users.choices import InvitationStatus, OrganizationRole
from users.factories import AdminUserFactory, InvitationFactory, UserFactory
from users.tests import build_xlsx_upload


class RecordingTestCase(AssumeActiveSubscription, APITestCase):
    """An organization with an admin who owns a project and a personal
    document, and a member to act on."""

    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory()
        self.admin = AdminUserFactory(organization=self.org)
        self.member = UserFactory(organization=self.org, name="Mia")
        self.project = ProjectFactory(organization=self.org, created_by=self.admin)
        ProjectPermissionFactory(
            project=self.project, user=self.admin, access_level=AccessLevel.OWNER
        )
        self.document = DocumentFactory(
            project=None, organization=self.org, created_by=self.admin
        )
        DocumentPermissionFactory(
            document=self.document, user=self.admin, access_level=AccessLevel.OWNER
        )
        self.client.force_authenticate(self.admin)

    def assert_recorded(
        self,
        verb,
        *,
        actor=None,
        target_user=None,
        project=None,
        document=None,
        details=None,
    ):
        """The action recorded exactly one event, with these values."""
        event = AuditEvent.objects.get()
        actor = actor or self.admin
        self.assertEqual(
            (
                event.organization_id,
                event.actor,
                event.verb,
                event.target_user,
                event.project,
                event.document,
                event.details,
            ),
            (
                actor.organization_id,
                actor,
                verb,
                target_user,
                project,
                document,
                details or {},
            ),
        )

    def assert_nothing_recorded(self):
        self.assertFalse(AuditEvent.objects.exists())


class AccessEventTests(RecordingTestCase):
    def test_sharing_a_project_records_the_grant(self):
        with self.assertNumQueries(17):
            response = self.client.post(
                reverse("project_share", args=[self.project.pk]),
                {"user": self.member.pk, "access_level": AccessLevel.EDITOR},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(
            AuditVerb.ACCESS_GRANTED,
            target_user=self.member,
            project=self.project,
            details={"access_level": AccessLevel.EDITOR},
        )

    def test_changing_a_document_level_records_the_old_and_new_levels(self):
        DocumentPermissionFactory(
            document=self.document, user=self.member, access_level=AccessLevel.VIEWER
        )

        with self.assertNumQueries(16):
            response = self.client.post(
                reverse("document_share", args=[self.document.pk]),
                {"user": self.member.pk, "access_level": AccessLevel.EDITOR},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(
            AuditVerb.ACCESS_CHANGED,
            target_user=self.member,
            document=self.document,
            details={
                "access_level": AccessLevel.EDITOR,
                "previous_access_level": AccessLevel.VIEWER,
            },
        )

    def test_sharing_at_the_level_someone_already_has_records_nothing(self):
        DocumentPermissionFactory(
            document=self.document, user=self.member, access_level=AccessLevel.EDITOR
        )

        with self.assertNumQueries(9):
            response = self.client.post(
                reverse("document_share", args=[self.document.pk]),
                {"user": self.member.pk, "access_level": AccessLevel.EDITOR},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_nothing_recorded()

    def test_removing_someone_from_a_project_records_the_level_they_had(self):
        ProjectPermissionFactory(
            project=self.project, user=self.member, access_level=AccessLevel.VIEWER
        )

        with self.assertNumQueries(8):
            response = self.client.delete(
                reverse("project_share_revoke", args=[self.project.pk, self.member.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assert_recorded(
            AuditVerb.ACCESS_REVOKED,
            target_user=self.member,
            project=self.project,
            details={"previous_access_level": AccessLevel.VIEWER},
        )

    def test_removing_someone_from_a_document_records_it(self):
        DocumentPermissionFactory(
            document=self.document, user=self.member, access_level=AccessLevel.EDITOR
        )

        with self.assertNumQueries(8):
            response = self.client.delete(
                reverse(
                    "document_share_revoke", args=[self.document.pk, self.member.pk]
                )
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assert_recorded(
            AuditVerb.ACCESS_REVOKED,
            target_user=self.member,
            document=self.document,
            details={"previous_access_level": AccessLevel.EDITOR},
        )

    def test_a_refused_removal_records_nothing(self):
        with self.assertNumQueries(8):
            response = self.client.delete(
                reverse("project_share_revoke", args=[self.project.pk, self.admin.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_nothing_recorded()

    def test_making_a_project_public_records_it(self):
        with self.assertNumQueries(7):
            response = self.client.patch(
                reverse("project_detail", args=[self.project.pk]),
                {"visibility": Visibility.PUBLIC},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(
            AuditVerb.VISIBILITY_CHANGED,
            project=self.project,
            details={"visibility": Visibility.PUBLIC},
        )

    def test_making_a_document_private_records_it(self):
        self.document.visibility = Visibility.PUBLIC
        self.document.save()

        with self.assertNumQueries(7):
            response = self.client.patch(
                reverse("document_detail", args=[self.document.pk]),
                {"visibility": Visibility.PRIVATE},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(
            AuditVerb.VISIBILITY_CHANGED,
            document=self.document,
            details={"visibility": Visibility.PRIVATE},
        )

    def test_editing_a_document_records_nothing(self):
        with self.assertNumQueries(8):
            response = self.client.patch(
                reverse("document_detail", args=[self.document.pk]),
                {"title": "Renamed", "visibility": Visibility.PRIVATE},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_nothing_recorded()

    def test_a_refused_stale_save_records_nothing(self):
        self.document.revision = 2
        self.document.save()

        with self.assertNumQueries(7):
            response = self.client.patch(
                reverse("document_detail", args=[self.document.pk]),
                {"visibility": Visibility.PUBLIC, "base_revision": 1},
            )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assert_nothing_recorded()

    def test_approving_an_access_request_records_it(self):
        access_request = DocumentAccessRequestFactory(
            document=self.document, requested_by=self.member
        )

        with self.assertNumQueries(13):
            response = self.client.post(
                reverse(
                    "document_access_request_approve",
                    args=[self.document.pk, access_request.pk],
                )
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(
            AuditVerb.ACCESS_REQUEST_APPROVED,
            target_user=self.member,
            document=self.document,
        )

    def test_denying_an_access_request_records_it(self):
        access_request = DocumentAccessRequestFactory(
            document=self.document, requested_by=self.member
        )

        with self.assertNumQueries(9):
            response = self.client.post(
                reverse(
                    "document_access_request_deny",
                    args=[self.document.pk, access_request.pk],
                )
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(
            AuditVerb.ACCESS_REQUEST_DENIED,
            target_user=self.member,
            document=self.document,
        )


class TrashEventTests(RecordingTestCase):
    def test_deleting_a_project_records_it(self):
        with self.assertNumQueries(6):
            response = self.client.delete(
                reverse("project_detail", args=[self.project.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assert_recorded(AuditVerb.DELETED, project=self.project)

    def test_restoring_a_project_records_it(self):
        self.project.is_active = False
        self.project.save()

        with self.assertNumQueries(5):
            response = self.client.post(
                reverse("project_restore", args=[self.project.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(AuditVerb.RESTORED, project=self.project)

    def test_deleting_a_document_records_it(self):
        with self.assertNumQueries(6):
            response = self.client.delete(
                reverse("document_detail", args=[self.document.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assert_recorded(AuditVerb.DELETED, document=self.document)

    def test_restoring_a_document_records_it(self):
        self.document.is_active = False
        self.document.save()

        with self.assertNumQueries(5):
            response = self.client.post(
                reverse("document_restore", args=[self.document.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(AuditVerb.RESTORED, document=self.document)

    def test_a_refused_restore_records_nothing(self):
        document = DocumentFactory(project=self.project, created_by=self.admin)
        DocumentPermissionFactory(
            document=document, user=self.admin, access_level=AccessLevel.OWNER
        )
        document.is_active = False
        document.save()
        self.project.is_active = False
        self.project.save()

        with self.assertNumQueries(1):
            response = self.client.post(reverse("document_restore", args=[document.pk]))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_nothing_recorded()


class AttachmentEventTests(TemporaryMediaRoot, RecordingTestCase):
    def test_attaching_a_file_records_its_name_and_size(self):
        upload = SimpleUploadedFile("minutes.pdf", PDF)

        with self.assertNumQueries(7):
            response = self.client.post(
                reverse("document_attachment_list_create", args=[self.document.pk]),
                {"file": upload},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assert_recorded(
            AuditVerb.ATTACHMENT_ADDED,
            document=self.document,
            details={"file_name": "minutes.pdf", "size": len(PDF)},
        )

    def test_deleting_a_file_records_its_name(self):
        attachment = AttachmentFactory(document=self.document, name="minutes.pdf")

        with self.assertNumQueries(6), self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(
                reverse(
                    "document_attachment_detail",
                    args=[self.document.pk, attachment.pk],
                )
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assert_recorded(
            AuditVerb.ATTACHMENT_DELETED,
            document=self.document,
            details={"file_name": "minutes.pdf"},
        )

    def test_a_refused_file_records_nothing(self):
        upload = SimpleUploadedFile("minutes.pdf", b"not a pdf at all")

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("document_attachment_list_create", args=[self.document.pk]),
                {"file": upload},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_nothing_recorded()


class MembershipEventTests(RecordingTestCase):
    def test_making_a_member_an_admin_records_the_old_and_new_roles(self):
        with self.assertNumQueries(7):
            response = self.client.patch(
                reverse("user_role_update", args=[self.member.pk]),
                {"org_role": OrganizationRole.ADMIN},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(
            AuditVerb.ROLE_CHANGED,
            target_user=self.member,
            details={
                "role": OrganizationRole.ADMIN,
                "previous_role": OrganizationRole.MEMBER,
            },
        )

    def test_giving_someone_the_role_they_have_records_nothing(self):
        with self.assertNumQueries(6):
            response = self.client.patch(
                reverse("user_role_update", args=[self.member.pk]),
                {"org_role": OrganizationRole.MEMBER},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_nothing_recorded()

    def test_deactivating_a_member_records_it(self):
        with self.assertNumQueries(7):
            response = self.client.delete(
                reverse("user_deactivate", args=[self.member.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assert_recorded(AuditVerb.MEMBER_DEACTIVATED, target_user=self.member)

    def test_a_refused_deactivation_records_nothing(self):
        with self.assertNumQueries(1):
            response = self.client.delete(
                reverse("user_deactivate", args=[self.admin.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_nothing_recorded()

    def test_reactivating_a_member_records_it(self):
        self.member.is_active = False
        self.member.save()

        with self.assertNumQueries(5):
            response = self.client.post(
                reverse("user_reactivate", args=[self.member.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(AuditVerb.MEMBER_REACTIVATED, target_user=self.member)

    def test_inviting_someone_records_their_address(self):
        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("invitation_list_create"), {"email": "new@example.com"}
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assert_recorded(
            AuditVerb.INVITATION_SENT, details={"email": "new@example.com"}
        )

    def test_a_spreadsheet_records_one_invitation_per_address_invited(self):
        upload = build_xlsx_upload(
            ["one@example.com", "not-an-email", "two@example.com"]
        )

        with self.assertNumQueries(13):
            response = self.client.post(
                reverse("invitation_bulk_create"), {"file": upload}, format="multipart"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertQuerySetEqual(
            AuditEvent.objects.order_by("pk").values_list(
                "actor", "verb", "details__email"
            ),
            [
                (self.admin.pk, AuditVerb.INVITATION_SENT, "one@example.com"),
                (self.admin.pk, AuditVerb.INVITATION_SENT, "two@example.com"),
            ],
        )

    def test_resending_an_invitation_records_it(self):
        invitation = InvitationFactory(
            organization=self.org, invited_by=self.admin, email="wait@example.com"
        )

        with self.assertNumQueries(8):
            response = self.client.post(
                reverse("invitation_resend", args=[invitation.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_recorded(
            AuditVerb.INVITATION_RESENT, details={"email": "wait@example.com"}
        )

    def test_revoking_an_invitation_records_it(self):
        invitation = InvitationFactory(
            organization=self.org, invited_by=self.admin, email="gone@example.com"
        )

        with self.assertNumQueries(5):
            response = self.client.delete(
                reverse("invitation_revoke", args=[invitation.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assert_recorded(
            AuditVerb.INVITATION_REVOKED, details={"email": "gone@example.com"}
        )

    def test_accepting_an_invitation_records_the_new_member_as_the_actor(self):
        InvitationFactory(
            organization=self.org,
            invited_by=self.admin,
            email="joiner@example.com",
            token="join-token",
        )
        self.client.force_authenticate(None)

        with self.assertNumQueries(10):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "join-token", "password": "Str0ng-New-Pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        joiner = self.org.users.get(email="joiner@example.com")
        self.assert_recorded(
            AuditVerb.INVITATION_ACCEPTED,
            actor=joiner,
            details={"email": "joiner@example.com"},
        )

    def test_a_refused_acceptance_records_nothing(self):
        InvitationFactory(
            organization=self.org,
            invited_by=self.admin,
            token="old-token",
            status=InvitationStatus.REVOKED,
        )
        self.client.force_authenticate(None)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("invitation_accept"),
                {"token": "old-token", "password": "Str0ng-New-Pass!"},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_nothing_recorded()


class AuditEventListAPITests(AssumeActiveSubscription, APITestCase):
    url = reverse("audit_event_list")

    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory()
        self.admin = AdminUserFactory(organization=self.org, name="Ada")
        self.member = UserFactory(
            organization=self.org, name="Mia", email="mia@example.com"
        )
        self.client.force_authenticate(self.admin)

    def event(self, verb=AuditVerb.MEMBER_REACTIVATED, **fields):
        return AuditEventFactory(
            organization=self.org, actor=self.admin, verb=verb, **fields
        )

    def list_events(self, params=None, queries=2):
        with self.assertNumQueries(queries):
            response = self.client.get(self.url, params or {})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["results"]

    def test_admin_sees_who_did_what_to_whom_newest_first(self):
        older = self.event(target_user=self.member)
        newer = self.event(
            AuditVerb.ROLE_CHANGED,
            target_user=self.member,
            details={"role": "ADMIN", "previous_role": "MEMBER"},
        )

        results = self.list_events()

        self.assertEqual([row["id"] for row in results], [newer.pk, older.pk])
        self.assertEqual(
            results[0],
            {
                "id": newer.pk,
                "created": results[0]["created"],
                "verb": AuditVerb.ROLE_CHANGED,
                "actor_email": self.admin.email,
                "actor_name": "Ada",
                "target_user_email": "mia@example.com",
                "target_user_name": "Mia",
                "resource_kind": None,
                "resource_name": None,
                "details": {"role": "ADMIN", "previous_role": "MEMBER"},
            },
        )

    def test_projects_and_documents_the_admin_can_open_are_named(self):
        public_project = ProjectFactory(
            organization=self.org, name="Roadmap", visibility=Visibility.PUBLIC
        )
        shared_document = DocumentFactory(
            project=None, organization=self.org, title="Budget"
        )
        DocumentPermissionFactory(
            document=shared_document, user=self.admin, access_level=AccessLevel.VIEWER
        )
        self.event(AuditVerb.DELETED, project=public_project)
        self.event(
            AuditVerb.ATTACHMENT_ADDED,
            document=shared_document,
            details={"file_name": "figures.xlsx", "size": 10},
        )

        results = self.list_events()

        self.assertEqual(
            [
                (row["resource_kind"], row["resource_name"], row["details"])
                for row in results
            ],
            [
                ("DOCUMENT", "Budget", {"file_name": "figures.xlsx", "size": 10}),
                ("PROJECT", "Roadmap", {}),
            ],
        )

    def test_private_resources_the_admin_cant_open_go_unnamed(self):
        private_project = ProjectFactory(organization=self.org, name="Layoffs")
        private_document = DocumentFactory(
            project=None, organization=self.org, title="Salaries"
        )
        self.event(AuditVerb.ACCESS_GRANTED, project=private_project)
        self.event(
            AuditVerb.ATTACHMENT_DELETED,
            document=private_document,
            details={"file_name": "salaries-2026.xlsx"},
        )

        results = self.list_events()

        self.assertEqual(
            [
                (row["resource_kind"], row["resource_name"], row["details"])
                for row in results
            ],
            [("DOCUMENT", None, {}), ("PROJECT", None, {})],
        )
        self.assertNotIn("Salaries", str(results))
        self.assertNotIn("salaries-2026", str(results))

    def test_only_the_admins_own_organizations_events_are_listed(self):
        mine = self.event()
        AuditEventFactory()

        results = self.list_events()

        self.assertEqual([row["id"] for row in results], [mine.pk])

    def test_events_can_be_narrowed_to_one_kind(self):
        self.event(AuditVerb.ACCESS_GRANTED)
        deleted = self.event(AuditVerb.DELETED)
        restored = self.event(AuditVerb.RESTORED)

        results = self.list_events({"kind": "TRASH"})

        self.assertEqual([row["id"] for row in results], [restored.pk, deleted.pk])

    def test_search_matches_who_did_it_who_it_was_about_or_who_was_invited(self):
        by_member = AuditEventFactory(organization=self.org, actor=self.member)
        about_member = self.event(target_user=self.member)
        self.event(AuditVerb.INVITATION_SENT, details={"email": "mia.b@example.com"})
        self.event()

        results = self.list_events({"search": "mia@"})
        invited = self.list_events({"search": "mia.b"})

        self.assertEqual(
            [row["id"] for row in results], [about_member.pk, by_member.pk]
        )
        self.assertEqual(
            [row["details"] for row in invited], [{"email": "mia.b@example.com"}]
        )

    def test_events_can_be_narrowed_to_a_time_range(self):
        now = timezone.now()
        too_old, inside, too_new = self.event(), self.event(), self.event()
        for event, age in ((too_old, 10), (inside, 5), (too_new, 1)):
            AuditEvent.objects.filter(pk=event.pk).update(
                created=now - timedelta(days=age)
            )

        results = self.list_events(
            {
                "after": (now - timedelta(days=7)).isoformat(),
                "before": (now - timedelta(days=2)).isoformat(),
            }
        )

        self.assertEqual([row["id"] for row in results], [inside.pk])

    def test_an_unknown_kind_or_a_malformed_time_is_refused(self):
        with self.assertNumQueries(0):
            response = self.client.get(self.url, {"kind": "BILLING", "after": "soon"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.data), {"kind", "after"})

    def test_members_cant_read_the_activity(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AuditRetentionTests(TestCase):
    def test_events_older_than_a_year_are_removed_daily(self):
        now = timezone.now()
        kept, expired = AuditEventFactory(), AuditEventFactory()
        AuditEvent.objects.filter(pk=kept.pk).update(
            created=now - AUDIT_EVENT_RETENTION + timedelta(days=1)
        )
        AuditEvent.objects.filter(pk=expired.pk).update(
            created=now - AUDIT_EVENT_RETENTION - timedelta(days=1)
        )

        with self.assertNumQueries(1):
            remove_expired_audit_events_task()

        self.assertQuerySetEqual(AuditEvent.objects.all(), [kept])

    def test_an_event_reads_as_who_did_what(self):
        event = AuditEventFactory(
            actor__email="ada@example.com", verb=AuditVerb.DELETED
        )

        self.assertEqual(str(event), "ada@example.com - Moved to the trash")
