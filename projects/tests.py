from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, APITestCase

from core.testing import AssumeActiveSubscription
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
from projects.models import Project, ProjectPermission
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

    def test_anonymous_user_is_denied_without_hitting_the_db(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()

        with self.assertNumQueries(0):
            self.assertFalse(
                self.permission.has_object_permission(request, None, self.project)
            )


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
