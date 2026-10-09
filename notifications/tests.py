from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.tests import AssumeActiveSubscription
from notifications.choices import NotificationVerb
from notifications.constants import NOTIFICATION_RETENTION
from notifications.factories import NotificationFactory
from notifications.models import Notification
from notifications.tasks import remove_expired_notifications_task
from organizations.factories import OrganizationFactory
from projects.choices import AccessLevel, Visibility
from projects.factories import (
    DocumentAccessRequestFactory,
    DocumentFactory,
    DocumentPermissionFactory,
    ProjectFactory,
    ProjectPermissionFactory,
)
from users.factories import AdminUserFactory, UserFactory


class NotifyingTestCase(AssumeActiveSubscription, APITestCase):
    """An organization whose owner has a project and a public document, and
    a member to share them with."""

    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory()
        self.owner = AdminUserFactory(organization=self.org)
        self.member = UserFactory(organization=self.org)
        self.project = ProjectFactory(organization=self.org, created_by=self.owner)
        ProjectPermissionFactory(
            project=self.project, user=self.owner, access_level=AccessLevel.OWNER
        )
        self.document = DocumentFactory(
            project=None,
            organization=self.org,
            created_by=self.owner,
            visibility=Visibility.PUBLIC,
        )
        DocumentPermissionFactory(
            document=self.document, user=self.owner, access_level=AccessLevel.OWNER
        )
        self.client.force_authenticate(self.owner)

    def notifications(self):
        return list(
            Notification.objects.order_by("pk").values_list(
                "recipient", "actor", "verb", "project", "document", "details"
            )
        )


class SharingNotificationTests(NotifyingTestCase):
    def test_sharing_a_project_tells_the_person_shared_with(self):
        with self.assertNumQueries(17):
            response = self.client.post(
                reverse("project_share", args=[self.project.pk]),
                {"user": self.member.pk, "access_level": AccessLevel.VIEWER},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.notifications(),
            [
                (
                    self.member.pk,
                    self.owner.pk,
                    NotificationVerb.ACCESS_GRANTED,
                    self.project.pk,
                    None,
                    {"access_level": AccessLevel.VIEWER},
                )
            ],
        )

    def test_changing_someones_level_tells_them(self):
        DocumentPermissionFactory(
            document=self.document, user=self.member, access_level=AccessLevel.VIEWER
        )

        with self.assertNumQueries(16):
            response = self.client.post(
                reverse("document_share", args=[self.document.pk]),
                {"user": self.member.pk, "access_level": AccessLevel.EDITOR},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.notifications(),
            [
                (
                    self.member.pk,
                    self.owner.pk,
                    NotificationVerb.ACCESS_CHANGED,
                    None,
                    self.document.pk,
                    {"access_level": AccessLevel.EDITOR},
                )
            ],
        )

    def test_sharing_at_the_level_someone_already_has_tells_nobody(self):
        DocumentPermissionFactory(
            document=self.document, user=self.member, access_level=AccessLevel.EDITOR
        )

        with self.assertNumQueries(9):
            self.client.post(
                reverse("document_share", args=[self.document.pk]),
                {"user": self.member.pk, "access_level": AccessLevel.EDITOR},
            )

        self.assertEqual(self.notifications(), [])

    def test_changing_your_own_level_tells_nobody(self):
        co_owner = UserFactory(organization=self.org)
        DocumentPermissionFactory(
            document=self.document, user=co_owner, access_level=AccessLevel.OWNER
        )

        with self.assertNumQueries(16):
            response = self.client.post(
                reverse("document_share", args=[self.document.pk]),
                {"user": self.owner.pk, "access_level": AccessLevel.EDITOR},
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.notifications(), [])

    def test_a_refused_share_tells_nobody(self):
        self.member.is_active = False
        self.member.save()

        with self.assertNumQueries(4):
            response = self.client.post(
                reverse("document_share", args=[self.document.pk]),
                {"user": self.member.pk, "access_level": AccessLevel.EDITOR},
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.notifications(), [])


class AccessRequestNotificationTests(NotifyingTestCase):
    def test_a_request_tells_each_active_owner(self):
        co_owner = UserFactory(organization=self.org)
        departed_owner = UserFactory(organization=self.org, is_active=False)
        for user in (co_owner, departed_owner):
            DocumentPermissionFactory(
                document=self.document, user=user, access_level=AccessLevel.OWNER
            )
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(10):
            response = self.client.post(
                reverse("document_access_request_list_create", args=[self.document.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertCountEqual(
            self.notifications(),
            [
                (
                    owner.pk,
                    self.member.pk,
                    NotificationVerb.ACCESS_REQUESTED,
                    None,
                    self.document.pk,
                    {},
                )
                for owner in (self.owner, co_owner)
            ],
        )

    def test_a_refused_request_tells_nobody(self):
        DocumentAccessRequestFactory(document=self.document, requested_by=self.member)
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(3):
            response = self.client.post(
                reverse("document_access_request_list_create", args=[self.document.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.notifications(), [])

    def test_approving_tells_the_requester(self):
        access_request = DocumentAccessRequestFactory(
            document=self.document, requested_by=self.member
        )

        with self.assertNumQueries(13):
            self.client.post(
                reverse(
                    "document_access_request_approve",
                    args=[self.document.pk, access_request.pk],
                )
            )

        self.assertEqual(
            self.notifications(),
            [
                (
                    self.member.pk,
                    self.owner.pk,
                    NotificationVerb.ACCESS_REQUEST_APPROVED,
                    None,
                    self.document.pk,
                    {},
                )
            ],
        )

    def test_denying_tells_the_requester(self):
        access_request = DocumentAccessRequestFactory(
            document=self.document, requested_by=self.member
        )

        with self.assertNumQueries(9):
            self.client.post(
                reverse(
                    "document_access_request_deny",
                    args=[self.document.pk, access_request.pk],
                )
            )

        self.assertEqual(
            self.notifications(),
            [
                (
                    self.member.pk,
                    self.owner.pk,
                    NotificationVerb.ACCESS_REQUEST_DENIED,
                    None,
                    self.document.pk,
                    {},
                )
            ],
        )


class NotificationAPITests(AssumeActiveSubscription, APITestCase):
    list_url = reverse("notification_list")
    count_url = reverse("notification_unread_count")
    read_all_url = reverse("notification_read_all")

    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory()
        self.user = UserFactory(organization=self.org)
        self.colleague = UserFactory(organization=self.org, name="Cole")
        self.client.force_authenticate(self.user)

    def notify(self, **fields):
        return NotificationFactory(recipient=self.user, actor=self.colleague, **fields)

    def read_url(self, notification):
        return reverse("notification_read", args=[notification.pk])

    def test_lists_the_callers_own_notifications_newest_first(self):
        document = DocumentFactory(project=None, organization=self.org, title="Plan")
        DocumentPermissionFactory(
            document=document, user=self.user, access_level=AccessLevel.EDITOR
        )
        older = self.notify(verb=NotificationVerb.ACCESS_REQUEST_DENIED)
        newer = self.notify(
            verb=NotificationVerb.ACCESS_GRANTED,
            document=document,
            details={"access_level": "EDITOR"},
        )
        NotificationFactory(recipient=self.colleague)

        with self.assertNumQueries(2):
            response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["id"] for row in response.data["results"]], [newer.pk, older.pk]
        )
        self.assertEqual(
            response.data["results"][0],
            {
                "id": newer.pk,
                "created": response.data["results"][0]["created"],
                "verb": NotificationVerb.ACCESS_GRANTED,
                "read": False,
                "actor_email": self.colleague.email,
                "actor_name": "Cole",
                "resource_kind": "DOCUMENT",
                "resource_id": document.pk,
                "resource_name": "Plan",
                "details": {"access_level": "EDITOR"},
            },
        )

    def test_something_the_recipient_can_no_longer_open_goes_unnamed(self):
        project = ProjectFactory(organization=self.org, name="Layoffs")
        self.notify(verb=NotificationVerb.ACCESS_GRANTED, project=project)

        with self.assertNumQueries(2):
            response = self.client.get(self.list_url)

        row = response.data["results"][0]
        self.assertEqual(
            (row["resource_kind"], row["resource_id"], row["resource_name"]),
            ("PROJECT", None, None),
        )

    def test_counts_only_the_callers_unread_notifications(self):
        self.notify()
        self.notify()
        self.notify(read_at=timezone.now())
        NotificationFactory(recipient=self.colleague)

        with self.assertNumQueries(1):
            response = self.client.get(self.count_url)

        self.assertEqual(response.data, {"count": 2})

    def test_marking_one_read(self):
        notification = self.notify()

        with self.assertNumQueries(2):
            response = self.client.post(self.read_url(notification))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        notification.refresh_from_db()
        self.assertTrue(notification.read_at)

    def test_reading_it_again_keeps_when_it_was_first_read(self):
        first_read = timezone.now() - timedelta(days=1)
        notification = self.notify(read_at=first_read)

        with self.assertNumQueries(2):
            self.client.post(self.read_url(notification))

        notification.refresh_from_db()
        self.assertEqual(notification.read_at, first_read)

    def test_someone_elses_notification_is_not_found(self):
        theirs = NotificationFactory(recipient=self.colleague)

        with self.assertNumQueries(1):
            response = self.client.post(self.read_url(theirs))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        theirs.refresh_from_db()
        self.assertIsNone(theirs.read_at)

    def test_marking_all_read_leaves_other_peoples_alone(self):
        self.notify()
        self.notify()
        theirs = NotificationFactory(recipient=self.colleague)

        with self.assertNumQueries(1):
            response = self.client.post(self.read_all_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.for_recipient(self.user).unread())
        theirs.refresh_from_db()
        self.assertIsNone(theirs.read_at)


class NotificationRetentionTests(TestCase):
    def test_notifications_older_than_90_days_are_removed_daily(self):
        now = timezone.now()
        kept, expired = NotificationFactory(), NotificationFactory()
        Notification.objects.filter(pk=kept.pk).update(
            created=now - NOTIFICATION_RETENTION + timedelta(days=1)
        )
        Notification.objects.filter(pk=expired.pk).update(
            created=now - NOTIFICATION_RETENTION - timedelta(days=1)
        )

        with self.assertNumQueries(1):
            remove_expired_notifications_task()

        self.assertQuerySetEqual(Notification.objects.all(), [kept])

    def test_a_notification_reads_as_who_it_is_for_and_what(self):
        notification = NotificationFactory(
            recipient__email="ada@example.com",
            verb=NotificationVerb.ACCESS_REQUEST_APPROVED,
        )

        self.assertEqual(
            str(notification), "ada@example.com - Your request was approved"
        )
