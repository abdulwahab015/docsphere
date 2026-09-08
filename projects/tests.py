from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from projects.choices import AccessLevel
from projects.factories import (
    DocumentFactory,
    DocumentPermissionFactory,
    ProjectFactory,
    ProjectPermissionFactory,
)
from projects.permissions import (
    Action,
    HasDocumentAccess,
    access_permits,
    resolve_access,
)
from users.factories import UserFactory


class ModelStrTests(TestCase):
    def test_project_str_is_the_name(self):
        project = ProjectFactory(name="Marketing")

        self.assertEqual(str(project), "Marketing")

    def test_document_str_is_the_title(self):
        document = DocumentFactory(title="Q3 Plan")

        self.assertEqual(str(document), "Q3 Plan")

    def test_project_permission_str_names_user_project_and_level(self):
        perm = ProjectPermissionFactory(access_level=AccessLevel.EDITOR)

        rendered = str(perm)
        self.assertIn(str(perm.user), rendered)
        self.assertIn(str(perm.project), rendered)
        self.assertIn(AccessLevel.EDITOR, rendered)

    def test_document_permission_str_names_user_document_and_level(self):
        perm = DocumentPermissionFactory(access_level=AccessLevel.VIEWER)

        rendered = str(perm)
        self.assertIn(str(perm.user), rendered)
        self.assertIn(str(perm.document), rendered)
        self.assertIn(AccessLevel.VIEWER, rendered)


class ResolveAccessTests(TestCase):
    """DocumentPermission first, then ProjectPermission fallback, else no
    access. The document-level grant is a strict override."""

    def setUp(self):
        self.project = ProjectFactory()
        self.document = DocumentFactory(project=self.project)
        self.user = UserFactory(organization=self.project.organization)

    def test_document_permission_is_used_when_present(self):
        DocumentPermissionFactory(
            document=self.document,
            user=self.user,
            access_level=AccessLevel.EDITOR,
        )

        with self.assertNumQueries(1):
            self.assertEqual(
                resolve_access(self.user, self.document), AccessLevel.EDITOR
            )

    def test_falls_back_to_project_permission_when_no_document_permission(self):
        ProjectPermissionFactory(
            project=self.project,
            user=self.user,
            access_level=AccessLevel.OWNER,
        )

        with self.assertNumQueries(2):
            self.assertEqual(
                resolve_access(self.user, self.document), AccessLevel.OWNER
            )

    def test_document_permission_overrides_even_when_it_grants_less(self):
        ProjectPermissionFactory(
            project=self.project,
            user=self.user,
            access_level=AccessLevel.OWNER,
        )
        DocumentPermissionFactory(
            document=self.document,
            user=self.user,
            access_level=AccessLevel.VIEWER,
        )

        with self.assertNumQueries(1):
            self.assertEqual(
                resolve_access(self.user, self.document), AccessLevel.VIEWER
            )

    def test_no_permission_anywhere_means_no_access(self):
        with self.assertNumQueries(2):
            self.assertIsNone(resolve_access(self.user, self.document))

    def test_document_permission_on_another_document_does_not_leak(self):
        other_document = DocumentFactory(project=self.project)
        DocumentPermissionFactory(
            document=other_document,
            user=self.user,
            access_level=AccessLevel.OWNER,
        )

        with self.assertNumQueries(2):
            self.assertIsNone(resolve_access(self.user, self.document))


class AccessPermitsTests(TestCase):
    """Owner > Editor > Viewer. Pure hierarchy check, no DB."""

    def test_viewer_can_only_read(self):
        self.assertTrue(access_permits(AccessLevel.VIEWER, Action.READ))
        self.assertFalse(access_permits(AccessLevel.VIEWER, Action.WRITE))
        self.assertFalse(access_permits(AccessLevel.VIEWER, Action.DELETE))
        self.assertFalse(access_permits(AccessLevel.VIEWER, Action.RESHARE))

    def test_editor_can_read_and_write_but_not_delete_or_reshare(self):
        self.assertTrue(access_permits(AccessLevel.EDITOR, Action.READ))
        self.assertTrue(access_permits(AccessLevel.EDITOR, Action.WRITE))
        self.assertFalse(access_permits(AccessLevel.EDITOR, Action.DELETE))
        self.assertFalse(access_permits(AccessLevel.EDITOR, Action.RESHARE))

    def test_owner_can_do_everything(self):
        self.assertTrue(access_permits(AccessLevel.OWNER, Action.READ))
        self.assertTrue(access_permits(AccessLevel.OWNER, Action.WRITE))
        self.assertTrue(access_permits(AccessLevel.OWNER, Action.DELETE))
        self.assertTrue(access_permits(AccessLevel.OWNER, Action.RESHARE))

    def test_no_access_permits_nothing(self):
        self.assertFalse(access_permits(None, Action.READ))
        self.assertFalse(access_permits(None, Action.WRITE))


class HasDocumentAccessTests(TestCase):
    """The DRF permission class maps HTTP method -> Action and combines
    resolve_access + access_permits."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = HasDocumentAccess()
        self.project = ProjectFactory()
        self.document = DocumentFactory(project=self.project)
        self.user = UserFactory(organization=self.project.organization)

    def _check(self, method, path="/"):
        request = getattr(self.factory, method.lower())(path)
        request.user = self.user
        return self.permission.has_object_permission(request, None, self.document)

    def test_viewer_may_read(self):
        DocumentPermissionFactory(
            document=self.document, user=self.user, access_level=AccessLevel.VIEWER
        )

        with self.assertNumQueries(1):
            self.assertTrue(self._check("GET"))

    def test_viewer_may_not_write(self):
        DocumentPermissionFactory(
            document=self.document, user=self.user, access_level=AccessLevel.VIEWER
        )

        with self.assertNumQueries(1):
            self.assertFalse(self._check("PATCH"))

    def test_editor_may_not_delete(self):
        DocumentPermissionFactory(
            document=self.document, user=self.user, access_level=AccessLevel.EDITOR
        )

        with self.assertNumQueries(1):
            self.assertFalse(self._check("DELETE"))

    def test_owner_may_delete(self):
        DocumentPermissionFactory(
            document=self.document, user=self.user, access_level=AccessLevel.OWNER
        )

        with self.assertNumQueries(1):
            self.assertTrue(self._check("DELETE"))

    def test_user_without_any_permission_is_denied(self):
        with self.assertNumQueries(2):
            self.assertFalse(self._check("GET"))

    def test_anonymous_user_is_denied_without_hitting_the_db(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        with self.assertNumQueries(0):
            self.assertFalse(
                self.permission.has_object_permission(request, None, self.document)
            )
