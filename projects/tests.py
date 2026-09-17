from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, APITestCase

from core.tests import AssumeActiveSubscription
from organizations.factories import OrganizationFactory
from projects.api.v1.serializers import ProjectSerializer
from projects.api.v1.views import ProjectListCreateAPIView
from projects.choices import AccessLevel, Action
from projects.factories import (
    DocumentFactory,
    DocumentPermissionFactory,
    ProjectFactory,
    ProjectPermissionFactory,
)
from projects.models import Document, DocumentPermission, Project, ProjectPermission
from projects.permissions import (
    HasDocumentAccess,
    HasProjectAccess,
    access_permits,
    resolve_access,
    resolve_project_access,
)
from users.factories import AdminUserFactory, UserFactory


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


class DocumentManagerTests(TestCase):
    def test_for_project_returns_only_that_projects_active_documents(self):
        project = ProjectFactory()
        document = DocumentFactory(project=project)
        DocumentFactory(project=project, is_active=False)
        DocumentFactory()

        self.assertEqual(list(Document.objects.for_project(project)), [document])


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


class ResolveProjectAccessTests(TestCase):
    """A single ProjectPermission lookup, no fallback chain."""

    def setUp(self):
        self.project = ProjectFactory()
        self.user = UserFactory(organization=self.project.organization)

    def test_returns_the_granted_level_when_a_permission_exists(self):
        ProjectPermissionFactory(
            project=self.project, user=self.user, access_level=AccessLevel.EDITOR
        )

        with self.assertNumQueries(1):
            self.assertEqual(
                resolve_project_access(self.user, self.project), AccessLevel.EDITOR
            )

    def test_returns_none_when_no_permission_exists(self):
        with self.assertNumQueries(1):
            self.assertIsNone(resolve_project_access(self.user, self.project))

    def test_permission_on_another_project_does_not_leak(self):
        other = ProjectFactory(organization=self.project.organization)
        ProjectPermissionFactory(
            project=other, user=self.user, access_level=AccessLevel.OWNER
        )

        with self.assertNumQueries(1):
            self.assertIsNone(resolve_project_access(self.user, self.project))


class HasProjectAccessTests(TestCase):
    """The DRF permission class maps HTTP method -> Action and combines
    resolve_project_access + access_permits."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = HasProjectAccess()
        self.project = ProjectFactory()
        self.user = UserFactory(organization=self.project.organization)

    def _check(self, method, path="/"):
        request = getattr(self.factory, method.lower())(path)
        request.user = self.user
        return self.permission.has_object_permission(request, None, self.project)

    def test_viewer_may_read(self):
        ProjectPermissionFactory(
            project=self.project, user=self.user, access_level=AccessLevel.VIEWER
        )

        with self.assertNumQueries(1):
            self.assertTrue(self._check("GET"))

    def test_viewer_may_not_write(self):
        ProjectPermissionFactory(
            project=self.project, user=self.user, access_level=AccessLevel.VIEWER
        )

        with self.assertNumQueries(1):
            self.assertFalse(self._check("PATCH"))

    def test_editor_may_not_delete(self):
        ProjectPermissionFactory(
            project=self.project, user=self.user, access_level=AccessLevel.EDITOR
        )

        with self.assertNumQueries(1):
            self.assertFalse(self._check("DELETE"))

    def test_owner_may_delete(self):
        ProjectPermissionFactory(
            project=self.project, user=self.user, access_level=AccessLevel.OWNER
        )

        with self.assertNumQueries(1):
            self.assertTrue(self._check("DELETE"))

    def test_user_without_any_permission_is_denied(self):
        with self.assertNumQueries(1):
            self.assertFalse(self._check("GET"))


class ProjectCreateAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.org = OrganizationFactory(name="Acme")
        self.other_org = OrganizationFactory(name="Globex")
        self.admin = AdminUserFactory(organization=self.org)
        self.member = UserFactory(organization=self.org)
        self.url = reverse("project_list_create")

    def test_admin_creates_project_with_creator_org_and_owner_permission(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(5):
            response = self.client.post(self.url, {"name": "Roadmap"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(name="Roadmap")
        self.assertEqual(project.created_by, self.admin)
        self.assertEqual(project.organization, self.org)
        self.assertTrue(
            ProjectPermission.objects.filter(
                project=project, user=self.admin, access_level=AccessLevel.OWNER
            ).exists()
        )

    def test_non_admin_member_cannot_create(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            response = self.client.post(self.url, {"name": "Roadmap"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Project.objects.filter(name="Roadmap").exists())

    def test_admin_without_an_organization_cannot_create(self):
        rootless_admin = AdminUserFactory(organization=None)
        self.client.force_authenticate(rootless_admin)

        with self.assertNumQueries(0):
            response = self.client.post(self.url, {"name": "Roadmap"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_perform_create_rejects_a_user_without_an_organization(self):
        request = APIRequestFactory().post(self.url)
        request.user = UserFactory(organization=None)
        view = ProjectListCreateAPIView()
        view.request = request

        with self.assertNumQueries(0), self.assertRaises(ValidationError):
            view.perform_create(ProjectSerializer())

    def test_duplicate_name_within_the_same_organization_is_rejected(self):
        ProjectFactory(organization=self.org, name="Roadmap")
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.post(self.url, {"name": "Roadmap"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_name_in_a_different_organization_is_allowed(self):
        ProjectFactory(organization=self.other_org, name="Roadmap")
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(5):
            response = self.client.post(self.url, {"name": "Roadmap"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class ProjectListAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.member = UserFactory(organization=self.org)
        self.url = reverse("project_list_create")

    def test_lists_active_projects_in_own_org_ordered_by_name(self):
        ProjectFactory(organization=self.org, name="Charlie")
        ProjectFactory(organization=self.org, name="Bravo")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["name"] for row in response.data["results"]]
        self.assertEqual(names, ["Alpha", "Bravo", "Charlie"])

    def test_excludes_projects_from_other_organizations(self):
        ProjectFactory(name="Foreign")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        names = [row["name"] for row in response.data["results"]]
        self.assertEqual(names, ["Alpha"])

    def test_excludes_soft_deleted_projects(self):
        ProjectFactory(organization=self.org, name="Deleted", is_active=False)
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        names = [row["name"] for row in response.data["results"]]
        self.assertEqual(names, ["Alpha"])

    def test_search_filters_by_name(self):
        ProjectFactory(organization=self.org, name="Budget")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url, {"search": "Budg"})

        names = [row["name"] for row in response.data["results"]]
        self.assertEqual(names, ["Budget"])

    def test_anonymous_request_is_rejected(self):
        with self.assertNumQueries(0):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProjectDetailAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.owner = UserFactory(organization=self.org)
        self.editor = UserFactory(organization=self.org)
        self.viewer = UserFactory(organization=self.org)
        self.stranger = UserFactory(organization=self.org)
        ProjectPermissionFactory(
            project=self.project, user=self.owner, access_level=AccessLevel.OWNER
        )
        ProjectPermissionFactory(
            project=self.project, user=self.editor, access_level=AccessLevel.EDITOR
        )
        ProjectPermissionFactory(
            project=self.project, user=self.viewer, access_level=AccessLevel.VIEWER
        )
        self.url = reverse("project_detail", args=[self.project.pk])

    def test_member_with_viewer_permission_can_retrieve(self):
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Alpha")

    def test_member_without_permission_cannot_retrieve(self):
        self.client.force_authenticate(self.stranger)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_org_project_is_a_404_not_a_403(self):
        foreign = ProjectFactory(name="Foreign")
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(1):
            response = self.client.get(reverse("project_detail", args=[foreign.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_editor_can_update(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(4):
            response = self.client.patch(
                self.url, {"name": "Alpha Prime"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Alpha Prime")

    def test_viewer_cannot_update(self):
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(2):
            response = self.client.patch(
                self.url, {"name": "Alpha Prime"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_to_a_name_used_by_another_project_is_rejected(self):
        ProjectFactory(organization=self.org, name="Beta")
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(3):
            response = self.client.patch(self.url, {"name": "Beta"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_soft_delete_and_project_drops_out_of_the_api(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(3):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_active)

        with self.assertNumQueries(1):
            follow_up = self.client.get(self.url)
        self.assertEqual(follow_up.status_code, status.HTTP_404_NOT_FOUND)

    def test_editor_cannot_delete(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(2):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_active)


class ProjectRestoreAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha", is_active=False)
        self.org = self.project.organization
        self.admin = AdminUserFactory(organization=self.org)
        self.member = UserFactory(organization=self.org)
        self.url = reverse("project_restore", args=[self.project.pk])

    def test_admin_can_restore_a_soft_deleted_project(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(2):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Alpha")
        self.project.refresh_from_db()
        self.assertTrue(self.project.is_active)

    def test_non_admin_cannot_restore(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_active)

    def test_admin_without_an_organization_cannot_restore(self):
        rootless_admin = AdminUserFactory(organization=None)
        self.client.force_authenticate(rootless_admin)

        with self.assertNumQueries(0):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_restoring_an_already_active_project_is_a_404(self):
        active_project = ProjectFactory(organization=self.org, name="Beta")
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("project_restore", args=[active_project.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_org_restore_is_a_404(self):
        foreign = ProjectFactory(name="Foreign", is_active=False)
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(1):
            response = self.client.post(reverse("project_restore", args=[foreign.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DocumentCreateAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.editor = UserFactory(organization=self.org)
        self.viewer = UserFactory(organization=self.org)
        ProjectPermissionFactory(
            project=self.project, user=self.editor, access_level=AccessLevel.EDITOR
        )
        ProjectPermissionFactory(
            project=self.project, user=self.viewer, access_level=AccessLevel.VIEWER
        )
        self.url = reverse("document_list_create")

    def test_editor_creates_document_with_creator_and_project(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(3):
            response = self.client.post(
                self.url,
                {"title": "Spec", "project": self.project.pk},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = Document.objects.get(title="Spec")
        self.assertEqual(document.created_by, self.editor)
        self.assertEqual(document.project, self.project)

    def test_viewer_only_cannot_create(self):
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(2):
            response = self.client.post(
                self.url,
                {"title": "Spec", "project": self.project.pk},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Document.objects.filter(title="Spec").exists())

    def test_create_against_a_project_from_another_org_is_a_404(self):
        foreign_project = ProjectFactory(name="Foreign")
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(1):
            response = self.client.post(
                self.url,
                {"title": "Spec", "project": foreign_project.pk},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Document.objects.filter(title="Spec").exists())

    def test_create_with_a_non_numeric_project_id_is_a_404(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(0):
            response = self.client.post(
                self.url,
                {"title": "Spec", "project": "not-a-number"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_without_an_organization_is_rejected(self):
        rootless_user = UserFactory(organization=None)
        self.client.force_authenticate(rootless_user)

        with self.assertNumQueries(0):
            response = self.client.post(
                self.url,
                {"title": "Spec", "project": self.project.pk},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DocumentListAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.document = DocumentFactory(project=self.project, title="Alpha Doc")
        self.member = UserFactory(organization=self.org)
        self.url = reverse("document_list_create")

    def test_lists_active_documents_in_own_org_ordered_by_title(self):
        DocumentFactory(project=self.project, title="Charlie Doc")
        DocumentFactory(project=self.project, title="Bravo Doc")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [row["title"] for row in response.data["results"]]
        self.assertEqual(titles, ["Alpha Doc", "Bravo Doc", "Charlie Doc"])

    def test_excludes_documents_from_other_organizations(self):
        DocumentFactory(title="Foreign Doc")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        titles = [row["title"] for row in response.data["results"]]
        self.assertEqual(titles, ["Alpha Doc"])

    def test_excludes_soft_deleted_documents(self):
        DocumentFactory(project=self.project, title="Deleted Doc", is_active=False)
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        titles = [row["title"] for row in response.data["results"]]
        self.assertEqual(titles, ["Alpha Doc"])

    def test_search_filters_by_title(self):
        DocumentFactory(project=self.project, title="Budget Doc")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url, {"search": "Budg"})

        titles = [row["title"] for row in response.data["results"]]
        self.assertEqual(titles, ["Budget Doc"])

    def test_project_filter_returns_only_that_projects_documents(self):
        other_project = ProjectFactory(organization=self.org, name="Beta")
        DocumentFactory(project=other_project, title="Beta Doc")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(3):
            response = self.client.get(self.url, {"project": self.project.pk})

        titles = [row["title"] for row in response.data["results"]]
        self.assertEqual(titles, ["Alpha Doc"])

    def test_project_filter_with_a_project_from_another_org_is_a_404(self):
        foreign_project = ProjectFactory(name="Foreign")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(1):
            response = self.client.get(self.url, {"project": foreign_project.pk})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_request_is_rejected(self):
        with self.assertNumQueries(0):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DocumentDetailAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.document = DocumentFactory(project=self.project, title="Doc1")
        self.owner = UserFactory(organization=self.org)
        self.editor = UserFactory(organization=self.org)
        self.viewer = UserFactory(organization=self.org)
        self.stranger = UserFactory(organization=self.org)
        ProjectPermissionFactory(
            project=self.project, user=self.owner, access_level=AccessLevel.OWNER
        )
        ProjectPermissionFactory(
            project=self.project, user=self.editor, access_level=AccessLevel.EDITOR
        )
        ProjectPermissionFactory(
            project=self.project, user=self.viewer, access_level=AccessLevel.VIEWER
        )
        self.url = reverse("document_detail", args=[self.document.pk])

    def test_member_with_viewer_permission_can_retrieve(self):
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(3):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Doc1")

    def test_member_without_permission_cannot_retrieve(self):
        self.client.force_authenticate(self.stranger)

        with self.assertNumQueries(3):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_org_document_is_a_404_not_a_403(self):
        foreign = DocumentFactory(title="Foreign")
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(1):
            response = self.client.get(reverse("document_detail", args=[foreign.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_editor_can_update(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(4):
            response = self.client.patch(
                self.url, {"title": "Doc1 Prime"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "Doc1 Prime")

    def test_viewer_cannot_update(self):
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(3):
            response = self.client.patch(
                self.url, {"title": "Doc1 Prime"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_soft_delete_and_document_drops_out_of_the_api(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.document.refresh_from_db()
        self.assertFalse(self.document.is_active)

        with self.assertNumQueries(1):
            follow_up = self.client.get(self.url)
        self.assertEqual(follow_up.status_code, status.HTTP_404_NOT_FOUND)

    def test_editor_cannot_delete(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(3):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.document.refresh_from_db()
        self.assertTrue(self.document.is_active)


class DocumentRestoreAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.document = DocumentFactory(
            project=self.project, title="Doc1", is_active=False
        )
        self.owner = UserFactory(organization=self.org)
        self.editor = UserFactory(organization=self.org)
        ProjectPermissionFactory(
            project=self.project, user=self.owner, access_level=AccessLevel.OWNER
        )
        ProjectPermissionFactory(
            project=self.project, user=self.editor, access_level=AccessLevel.EDITOR
        )
        self.url = reverse("document_restore", args=[self.document.pk])

    def test_owner_can_restore_a_soft_deleted_document(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Doc1")
        self.document.refresh_from_db()
        self.assertTrue(self.document.is_active)

    def test_editor_cannot_restore(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(3):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.document.refresh_from_db()
        self.assertFalse(self.document.is_active)

    def test_restoring_an_already_active_document_is_a_404(self):
        active_document = DocumentFactory(project=self.project, title="Doc2")
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("document_restore", args=[active_document.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_org_restore_is_a_404(self):
        foreign = DocumentFactory(title="Foreign", is_active=False)
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(1):
            response = self.client.post(reverse("document_restore", args=[foreign.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class ProjectShareAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.owner = UserFactory(organization=self.org)
        self.editor = UserFactory(organization=self.org)
        self.viewer = UserFactory(organization=self.org)
        self.target = UserFactory(organization=self.org)
        ProjectPermissionFactory(
            project=self.project, user=self.owner, access_level=AccessLevel.OWNER
        )
        ProjectPermissionFactory(
            project=self.project, user=self.editor, access_level=AccessLevel.EDITOR
        )
        ProjectPermissionFactory(
            project=self.project, user=self.viewer, access_level=AccessLevel.VIEWER
        )
        self.url = reverse("project_share", args=[self.project.pk])

    @patch("core.email.send_mail")
    def test_owner_can_share_with_a_new_user(self, mock_send_mail):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(11):
            response = self.client.post(
                self.url,
                {"user": self.target.pk, "access_level": AccessLevel.EDITOR},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        permission = ProjectPermission.objects.get(
            project=self.project, user=self.target
        )
        self.assertEqual(permission.access_level, AccessLevel.EDITOR)
        mock_send_mail.assert_called_once()
        self.assertEqual(
            mock_send_mail.call_args.kwargs["recipient_list"], [self.target.email]
        )

    @patch("core.email.send_mail")
    def test_owner_can_reshare_updating_existing_level(self, mock_send_mail):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(9):
            response = self.client.post(
                self.url,
                {"user": self.viewer.pk, "access_level": AccessLevel.OWNER},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        permissions = ProjectPermission.objects.filter(
            project=self.project, user=self.viewer
        )
        self.assertEqual(permissions.count(), 1)
        self.assertEqual(permissions.first().access_level, AccessLevel.OWNER)
        mock_send_mail.assert_called_once()

    def test_owner_can_list_current_grants(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_ids = {row["user"] for row in response.data["results"]}
        self.assertEqual(user_ids, {self.owner.pk, self.editor.pk, self.viewer.pk})

    def test_editor_cannot_share(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(2):
            response = self.client.post(
                self.url,
                {"user": self.target.pk, "access_level": AccessLevel.EDITOR},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            ProjectPermission.objects.filter(
                project=self.project, user=self.target
            ).exists()
        )

    def test_editor_cannot_list_current_grants(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_viewer_cannot_share(self):
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(2):
            response = self.client.post(
                self.url,
                {"user": self.target.pk, "access_level": AccessLevel.EDITOR},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_org_target_user_is_rejected(self):
        foreign_user = UserFactory()
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.post(
                self.url,
                {"user": foreign_user.pk, "access_level": AccessLevel.EDITOR},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            ProjectPermission.objects.filter(
                project=self.project, user=foreign_user
            ).exists()
        )

    def test_cross_org_project_share_attempt_is_a_404(self):
        foreign_project = ProjectFactory()
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("project_share", args=[foreign_project.pk]),
                {"user": self.target.pk, "access_level": AccessLevel.EDITOR},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ProjectShareRevokeAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.owner = UserFactory(organization=self.org)
        self.editor = UserFactory(organization=self.org)
        self.target = UserFactory(organization=self.org)
        ProjectPermissionFactory(
            project=self.project, user=self.owner, access_level=AccessLevel.OWNER
        )
        ProjectPermissionFactory(
            project=self.project, user=self.editor, access_level=AccessLevel.EDITOR
        )
        ProjectPermissionFactory(
            project=self.project, user=self.target, access_level=AccessLevel.VIEWER
        )
        self.url = reverse(
            "project_share_revoke", args=[self.project.pk, self.target.pk]
        )

    def test_owner_can_revoke(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(resolve_project_access(self.target, self.project))

    def test_owner_cannot_revoke_the_projects_last_owner(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.delete(
                reverse("project_share_revoke", args=[self.project.pk, self.owner.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            resolve_project_access(self.owner, self.project), AccessLevel.OWNER
        )

    def test_owner_can_revoke_a_co_owner_when_another_owner_remains(self):
        co_owner = UserFactory(organization=self.org)
        ProjectPermissionFactory(
            project=self.project, user=co_owner, access_level=AccessLevel.OWNER
        )
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(5):
            response = self.client.delete(
                reverse("project_share_revoke", args=[self.project.pk, co_owner.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(resolve_project_access(co_owner, self.project))

    def test_editor_cannot_revoke(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(2):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIsNotNone(resolve_project_access(self.target, self.project))

    def test_revoking_a_nonexistent_permission_is_a_404(self):
        stranger = UserFactory(organization=self.org)
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(3):
            response = self.client.delete(
                reverse("project_share_revoke", args=[self.project.pk, stranger.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_org_project_revoke_attempt_is_a_404(self):
        foreign_project = ProjectFactory()
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(1):
            response = self.client.delete(
                reverse(
                    "project_share_revoke", args=[foreign_project.pk, self.target.pk]
                )
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class DocumentShareAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.document = DocumentFactory(project=self.project, title="Doc1")
        self.owner = UserFactory(organization=self.org)
        self.editor = UserFactory(organization=self.org)
        self.target = UserFactory(organization=self.org)
        ProjectPermissionFactory(
            project=self.project, user=self.owner, access_level=AccessLevel.OWNER
        )
        ProjectPermissionFactory(
            project=self.project, user=self.editor, access_level=AccessLevel.EDITOR
        )
        self.url = reverse("document_share", args=[self.document.pk])

    @patch("core.email.send_mail")
    def test_owner_can_share_with_a_new_user(self, mock_send_mail):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(13):
            response = self.client.post(
                self.url,
                {"user": self.target.pk, "access_level": AccessLevel.VIEWER},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        permission = DocumentPermission.objects.get(
            document=self.document, user=self.target
        )
        self.assertEqual(permission.access_level, AccessLevel.VIEWER)
        mock_send_mail.assert_called_once()
        self.assertEqual(
            mock_send_mail.call_args.kwargs["recipient_list"], [self.target.email]
        )

    @patch("core.email.send_mail")
    def test_owner_can_reshare_updating_existing_level(self, mock_send_mail):
        DocumentPermissionFactory(
            document=self.document, user=self.target, access_level=AccessLevel.VIEWER
        )
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(11):
            response = self.client.post(
                self.url,
                {"user": self.target.pk, "access_level": AccessLevel.OWNER},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        permissions = DocumentPermission.objects.filter(
            document=self.document, user=self.target
        )
        self.assertEqual(permissions.count(), 1)
        self.assertEqual(permissions.first().access_level, AccessLevel.OWNER)
        mock_send_mail.assert_called_once()

    def test_owner_can_list_current_grants(self):
        DocumentPermissionFactory(
            document=self.document, user=self.target, access_level=AccessLevel.VIEWER
        )
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(5):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_ids = {row["user"] for row in response.data["results"]}
        self.assertEqual(user_ids, {self.target.pk})

    def test_editor_cannot_share(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(3):
            response = self.client.post(
                self.url,
                {"user": self.target.pk, "access_level": AccessLevel.VIEWER},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            DocumentPermission.objects.filter(
                document=self.document, user=self.target
            ).exists()
        )

    def test_editor_cannot_list_current_grants(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(3):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_org_target_user_is_rejected(self):
        foreign_user = UserFactory()
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(6):
            response = self.client.post(
                self.url,
                {"user": foreign_user.pk, "access_level": AccessLevel.VIEWER},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            DocumentPermission.objects.filter(
                document=self.document, user=foreign_user
            ).exists()
        )

    def test_cross_org_document_share_attempt_is_a_404(self):
        foreign_document = DocumentFactory()
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse("document_share", args=[foreign_document.pk]),
                {"user": self.target.pk, "access_level": AccessLevel.VIEWER},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DocumentShareRevokeAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.document = DocumentFactory(project=self.project, title="Doc1")
        self.owner = UserFactory(organization=self.org)
        self.editor = UserFactory(organization=self.org)
        self.target = UserFactory(organization=self.org)
        ProjectPermissionFactory(
            project=self.project, user=self.owner, access_level=AccessLevel.OWNER
        )
        ProjectPermissionFactory(
            project=self.project, user=self.editor, access_level=AccessLevel.EDITOR
        )
        ProjectPermissionFactory(
            project=self.project, user=self.target, access_level=AccessLevel.VIEWER
        )
        DocumentPermissionFactory(
            document=self.document, user=self.target, access_level=AccessLevel.EDITOR
        )
        self.url = reverse(
            "document_share_revoke", args=[self.document.pk, self.target.pk]
        )

    def test_owner_can_revoke_and_access_falls_back_to_project_permission(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(5):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(resolve_access(self.target, self.document), AccessLevel.VIEWER)

    def test_owner_cannot_revoke_the_documents_last_owner(self):
        DocumentPermissionFactory(
            document=self.document, user=self.owner, access_level=AccessLevel.OWNER
        )
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.delete(
                reverse("document_share_revoke", args=[self.document.pk, self.owner.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resolve_access(self.owner, self.document), AccessLevel.OWNER)

    def test_owner_can_revoke_a_co_owner_when_another_owner_remains(self):
        co_owner = UserFactory(organization=self.org)
        DocumentPermissionFactory(
            document=self.document, user=co_owner, access_level=AccessLevel.OWNER
        )
        DocumentPermissionFactory(
            document=self.document, user=self.owner, access_level=AccessLevel.OWNER
        )
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(5):
            response = self.client.delete(
                reverse("document_share_revoke", args=[self.document.pk, co_owner.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(resolve_access(co_owner, self.document))

    def test_editor_cannot_revoke(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(3):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resolve_access(self.target, self.document), AccessLevel.EDITOR)

    def test_revoking_the_last_permission_removes_access_entirely(self):
        stranger = UserFactory(organization=self.org)
        DocumentPermissionFactory(
            document=self.document, user=stranger, access_level=AccessLevel.VIEWER
        )
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(5):
            response = self.client.delete(
                reverse("document_share_revoke", args=[self.document.pk, stranger.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(resolve_access(stranger, self.document))

    def test_revoking_a_nonexistent_permission_is_a_404(self):
        stranger = UserFactory(organization=self.org)
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.delete(
                reverse("document_share_revoke", args=[self.document.pk, stranger.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_org_document_revoke_attempt_is_a_404(self):
        foreign_document = DocumentFactory()
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(1):
            response = self.client.delete(
                reverse(
                    "document_share_revoke",
                    args=[foreign_document.pk, self.target.pk],
                )
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
