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
from projects.choices import AccessLevel, AccessRequestStatus, Action, Visibility
from projects.factories import (
    DocumentAccessRequestFactory,
    DocumentFactory,
    DocumentPermissionFactory,
    ProjectFactory,
    ProjectPermissionFactory,
)
from projects.models import (
    Document,
    DocumentAccessRequest,
    DocumentPermission,
    Project,
    ProjectPermission,
)
from projects.permissions import (
    HasDocumentAccess,
    HasProjectAccess,
    access_permits,
    resolve_access,
    resolve_project_access,
)
from projects.tasks import send_access_request_created_email_task
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

    def test_document_access_request_str_names_requester_document_and_status(self):
        access_request = DocumentAccessRequestFactory()

        rendered = str(access_request)
        self.assertIn(str(access_request.requested_by), rendered)
        self.assertIn(str(access_request.document), rendered)
        self.assertIn(AccessRequestStatus.PENDING, rendered)


class DocumentManagerTests(TestCase):
    def test_for_project_returns_only_that_projects_active_documents(self):
        project = ProjectFactory()
        document = DocumentFactory(project=project)
        DocumentFactory(project=project, is_active=False)
        DocumentFactory()

        self.assertEqual(list(Document.objects.for_project(project)), [document])

    def test_for_organization_includes_personal_documents(self):
        org = OrganizationFactory()
        personal_document = DocumentFactory(project=None, organization=org)
        DocumentFactory(project=ProjectFactory(organization=org))
        DocumentFactory()

        self.assertIn(personal_document, Document.objects.for_organization(org))


class ProjectVisibleToTests(TestCase):
    """The list-endpoint chokepoint: explicit permission, or public, within
    the user's own organization - nothing else."""

    def setUp(self):
        self.org = OrganizationFactory()
        self.user = UserFactory(organization=self.org)

    def test_includes_projects_with_an_explicit_permission(self):
        project = ProjectFactory(organization=self.org)
        ProjectPermissionFactory(
            project=project, user=self.user, access_level=AccessLevel.VIEWER
        )

        self.assertEqual(list(Project.objects.visible_to(self.user)), [project])

    def test_includes_public_projects_without_a_permission(self):
        project = ProjectFactory(organization=self.org, visibility=Visibility.PUBLIC)

        self.assertEqual(list(Project.objects.visible_to(self.user)), [project])

    def test_excludes_private_projects_without_a_permission(self):
        ProjectFactory(organization=self.org)

        self.assertEqual(list(Project.objects.visible_to(self.user)), [])

    def test_excludes_public_projects_from_another_organization(self):
        ProjectFactory(visibility=Visibility.PUBLIC)

        self.assertEqual(list(Project.objects.visible_to(self.user)), [])

    def test_excludes_soft_deleted_projects_even_if_public(self):
        ProjectFactory(
            organization=self.org, visibility=Visibility.PUBLIC, is_active=False
        )

        self.assertEqual(list(Project.objects.visible_to(self.user)), [])

    def test_does_not_duplicate_a_project_that_is_both_public_and_explicitly_shared(
        self,
    ):
        project = ProjectFactory(organization=self.org, visibility=Visibility.PUBLIC)
        ProjectPermissionFactory(
            project=project, user=self.user, access_level=AccessLevel.EDITOR
        )

        self.assertEqual(list(Project.objects.visible_to(self.user)), [project])

    def test_does_not_duplicate_a_public_project_shared_with_other_users(self):
        project = ProjectFactory(organization=self.org, visibility=Visibility.PUBLIC)
        ProjectPermissionFactory.create_batch(2, project=project)

        self.assertEqual(list(Project.objects.visible_to(self.user)), [project])

    def test_annotates_the_explicit_level_over_the_public_default(self):
        project = ProjectFactory(organization=self.org, visibility=Visibility.PUBLIC)
        ProjectPermissionFactory(
            project=project, user=self.user, access_level=AccessLevel.EDITOR
        )

        self.assertEqual(
            Project.objects.visible_to(self.user).get().user_access_level,
            AccessLevel.EDITOR,
        )

    def test_annotates_implicit_viewer_on_a_public_project(self):
        ProjectFactory(organization=self.org, visibility=Visibility.PUBLIC)
        ProjectPermissionFactory(
            project__organization=self.org, access_level=AccessLevel.OWNER
        )

        self.assertEqual(
            Project.objects.visible_to(self.user).get().user_access_level,
            AccessLevel.VIEWER,
        )


class DocumentVisibleToTests(TestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.user = UserFactory(organization=self.org)

    def test_includes_documents_with_an_explicit_permission(self):
        document = DocumentFactory(project=ProjectFactory(organization=self.org))
        DocumentPermissionFactory(
            document=document, user=self.user, access_level=AccessLevel.VIEWER
        )

        self.assertEqual(list(Document.objects.visible_to(self.user)), [document])

    def test_includes_public_documents_without_a_permission(self):
        document = DocumentFactory(
            project=ProjectFactory(organization=self.org), visibility=Visibility.PUBLIC
        )

        self.assertEqual(list(Document.objects.visible_to(self.user)), [document])

    def test_includes_a_personal_document_with_an_explicit_permission(self):
        document = DocumentFactory(project=None, organization=self.org)
        DocumentPermissionFactory(
            document=document, user=self.user, access_level=AccessLevel.OWNER
        )

        self.assertEqual(list(Document.objects.visible_to(self.user)), [document])

    def test_excludes_private_documents_without_a_permission(self):
        DocumentFactory(project=ProjectFactory(organization=self.org))

        self.assertEqual(list(Document.objects.visible_to(self.user)), [])

    def test_excludes_public_documents_from_another_organization(self):
        DocumentFactory(visibility=Visibility.PUBLIC)

        self.assertEqual(list(Document.objects.visible_to(self.user)), [])


class ResolveAccessTests(TestCase):
    """An explicit DocumentPermission always wins; otherwise a public document
    grants every member of its organization an implicit Viewer level; a
    parent project's ProjectPermission never applies."""

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

    def test_public_document_with_no_permission_grants_implicit_viewer(self):
        self.document.visibility = Visibility.PUBLIC
        self.document.save(update_fields=["visibility"])

        with self.assertNumQueries(1):
            self.assertEqual(
                resolve_access(self.user, self.document), AccessLevel.VIEWER
            )

    def test_document_permission_overrides_public_visibility(self):
        self.document.visibility = Visibility.PUBLIC
        self.document.save(update_fields=["visibility"])
        DocumentPermissionFactory(
            document=self.document, user=self.user, access_level=AccessLevel.EDITOR
        )

        with self.assertNumQueries(1):
            self.assertEqual(
                resolve_access(self.user, self.document), AccessLevel.EDITOR
            )

    def test_public_document_in_another_organization_grants_nothing(self):
        self.document.visibility = Visibility.PUBLIC
        self.document.save(update_fields=["visibility"])
        outsider = UserFactory()

        with self.assertNumQueries(1):
            self.assertIsNone(resolve_access(outsider, self.document))

    def test_private_document_with_no_permission_grants_nothing(self):
        with self.assertNumQueries(1):
            self.assertIsNone(resolve_access(self.user, self.document))

    def test_project_permission_never_applies_to_a_document(self):
        ProjectPermissionFactory(
            project=self.project, user=self.user, access_level=AccessLevel.OWNER
        )

        with self.assertNumQueries(1):
            self.assertIsNone(resolve_access(self.user, self.document))

    def test_document_permission_on_another_document_does_not_leak(self):
        other_document = DocumentFactory(project=self.project)
        DocumentPermissionFactory(
            document=other_document,
            user=self.user,
            access_level=AccessLevel.OWNER,
        )

        with self.assertNumQueries(1):
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

    def test_public_document_viewer_without_an_explicit_permission_may_read(self):
        self.document.visibility = Visibility.PUBLIC
        self.document.save(update_fields=["visibility"])

        with self.assertNumQueries(1):
            self.assertTrue(self._check("GET"))

    def test_user_without_any_permission_is_denied(self):
        with self.assertNumQueries(1):
            self.assertFalse(self._check("GET"))


class ResolveProjectAccessTests(TestCase):
    """An explicit ProjectPermission always wins; otherwise a public project
    grants every member of its organization an implicit Viewer level."""

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

    def test_public_project_with_no_permission_grants_implicit_viewer(self):
        self.project.visibility = Visibility.PUBLIC
        self.project.save(update_fields=["visibility"])

        with self.assertNumQueries(1):
            self.assertEqual(
                resolve_project_access(self.user, self.project), AccessLevel.VIEWER
            )

    def test_project_permission_overrides_public_visibility(self):
        self.project.visibility = Visibility.PUBLIC
        self.project.save(update_fields=["visibility"])
        ProjectPermissionFactory(
            project=self.project, user=self.user, access_level=AccessLevel.EDITOR
        )

        with self.assertNumQueries(1):
            self.assertEqual(
                resolve_project_access(self.user, self.project), AccessLevel.EDITOR
            )

    def test_public_project_in_another_organization_grants_nothing(self):
        self.project.visibility = Visibility.PUBLIC
        self.project.save(update_fields=["visibility"])
        outsider = UserFactory()

        with self.assertNumQueries(1):
            self.assertIsNone(resolve_project_access(outsider, self.project))

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

    def test_public_project_viewer_without_an_explicit_permission_may_read(self):
        self.project.visibility = Visibility.PUBLIC
        self.project.save(update_fields=["visibility"])

        with self.assertNumQueries(1):
            self.assertTrue(self._check("GET"))

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

    def test_admin_creates_project_with_creator_org_owner_permission_and_private_default(
        self,
    ):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(5):
            response = self.client.post(self.url, {"name": "Roadmap"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["access_level"], AccessLevel.OWNER)
        project = Project.objects.get(name="Roadmap")
        self.assertEqual(project.created_by, self.admin)
        self.assertEqual(project.organization, self.org)
        self.assertEqual(project.visibility, Visibility.PRIVATE)
        self.assertTrue(
            ProjectPermission.objects.filter(
                project=project, user=self.admin, access_level=AccessLevel.OWNER
            ).exists()
        )

    def test_admin_can_create_a_public_project(self):
        self.client.force_authenticate(self.admin)

        with self.assertNumQueries(5):
            response = self.client.post(
                self.url,
                {"name": "Roadmap", "visibility": Visibility.PUBLIC},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(name="Roadmap")
        self.assertEqual(project.visibility, Visibility.PUBLIC)

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
        self.org = OrganizationFactory()
        self.member = UserFactory(organization=self.org)
        self.url = reverse("project_list_create")

    def test_lists_public_and_explicitly_shared_projects_ordered_by_name(self):
        shared = ProjectFactory(organization=self.org, name="Alpha")
        ProjectPermissionFactory(
            project=shared, user=self.member, access_level=AccessLevel.VIEWER
        )
        ProjectFactory(
            organization=self.org, name="Bravo", visibility=Visibility.PUBLIC
        )
        ProjectFactory(organization=self.org, name="Charlie")

        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["name"] for row in response.data["results"]]
        self.assertEqual(names, ["Alpha", "Bravo"])

    def test_reports_the_callers_own_access_level_on_each_project(self):
        for name, level in (
            ("Alpha", AccessLevel.OWNER),
            ("Bravo", AccessLevel.EDITOR),
        ):
            ProjectPermissionFactory(
                project__organization=self.org,
                project__name=name,
                project__visibility=Visibility.PUBLIC,
                user=self.member,
                access_level=level,
            )
        ProjectFactory(
            organization=self.org, name="Charlie", visibility=Visibility.PUBLIC
        )
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        levels = {row["name"]: row["access_level"] for row in response.data["results"]}
        self.assertEqual(
            levels,
            {
                "Alpha": AccessLevel.OWNER,
                "Bravo": AccessLevel.EDITOR,
                "Charlie": AccessLevel.VIEWER,
            },
        )

    def test_excludes_private_projects_without_a_permission(self):
        ProjectFactory(organization=self.org, name="Secret")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.data["results"], [])

    def test_excludes_projects_from_other_organizations(self):
        ProjectFactory(name="Foreign", visibility=Visibility.PUBLIC)
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.data["results"], [])

    def test_excludes_soft_deleted_projects(self):
        ProjectFactory(
            organization=self.org,
            name="Deleted",
            visibility=Visibility.PUBLIC,
            is_active=False,
        )
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.data["results"], [])

    def test_search_filters_by_name(self):
        ProjectFactory(
            organization=self.org, name="Budget", visibility=Visibility.PUBLIC
        )
        ProjectFactory(
            organization=self.org, name="Other", visibility=Visibility.PUBLIC
        )
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

    def test_public_project_viewer_without_an_explicit_permission_can_retrieve(self):
        public_project = ProjectFactory(
            organization=self.org, name="Beta", visibility=Visibility.PUBLIC
        )
        self.client.force_authenticate(self.stranger)

        with self.assertNumQueries(2):
            response = self.client.get(
                reverse("project_detail", args=[public_project.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_member_without_permission_gets_a_404_not_a_403(self):
        self.client.force_authenticate(self.stranger)

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

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

    def test_owner_can_change_visibility(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.patch(
                self.url, {"visibility": Visibility.PUBLIC}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.visibility, Visibility.PUBLIC)

    def test_editor_cannot_change_visibility(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(3):
            response = self.client.patch(
                self.url, {"visibility": Visibility.PUBLIC}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.project.refresh_from_db()
        self.assertEqual(self.project.visibility, Visibility.PRIVATE)

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

        with self.assertNumQueries(3):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Alpha")
        self.assertIsNone(response.data["access_level"])
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

    def test_editor_creates_document_in_project_and_becomes_owner(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(6):
            response = self.client.post(
                self.url,
                {"title": "Spec", "project": self.project.pk},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = Document.objects.get(title="Spec")
        self.assertEqual(document.created_by, self.editor)
        self.assertEqual(document.project, self.project)
        self.assertEqual(document.organization, self.org)
        self.assertEqual(document.visibility, Visibility.PRIVATE)
        self.assertTrue(
            DocumentPermission.objects.filter(
                document=document, user=self.editor, access_level=AccessLevel.OWNER
            ).exists()
        )

    def test_creator_can_set_visibility_to_public_at_creation(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(6):
            response = self.client.post(
                self.url,
                {
                    "title": "Spec",
                    "project": self.project.pk,
                    "visibility": Visibility.PUBLIC,
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        document = Document.objects.get(title="Spec")
        self.assertEqual(document.visibility, Visibility.PUBLIC)

    def test_any_org_member_can_create_a_personal_document_with_no_project(self):
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(4):
            response = self.client.post(self.url, {"title": "Notes"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["access_level"], AccessLevel.OWNER)
        document = Document.objects.get(title="Notes")
        self.assertIsNone(document.project)
        self.assertEqual(document.organization, self.org)
        self.assertTrue(
            DocumentPermission.objects.filter(
                document=document, user=self.viewer, access_level=AccessLevel.OWNER
            ).exists()
        )

    def test_viewer_only_cannot_create_a_document_in_a_project(self):
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
        self.member = UserFactory(organization=self.org)
        self.url = reverse("document_list_create")

    def test_lists_public_and_explicitly_shared_documents_ordered_by_title(self):
        shared = DocumentFactory(project=self.project, title="Alpha Doc")
        DocumentPermissionFactory(
            document=shared, user=self.member, access_level=AccessLevel.VIEWER
        )
        DocumentFactory(
            project=self.project, title="Bravo Doc", visibility=Visibility.PUBLIC
        )
        DocumentFactory(project=self.project, title="Charlie Doc")

        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [row["title"] for row in response.data["results"]]
        self.assertEqual(titles, ["Alpha Doc", "Bravo Doc"])

    def test_reports_the_callers_own_access_level_on_each_document(self):
        public_document = DocumentFactory(
            project=self.project, title="Alpha Doc", visibility=Visibility.PUBLIC
        )
        DocumentPermissionFactory(
            document=public_document, user=self.member, access_level=AccessLevel.EDITOR
        )
        DocumentFactory(
            project=self.project, title="Bravo Doc", visibility=Visibility.PUBLIC
        )
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        levels = [row["access_level"] for row in response.data["results"]]
        self.assertEqual(levels, [AccessLevel.EDITOR, AccessLevel.VIEWER])

    def test_lists_a_personal_document_the_member_has_a_permission_on(self):
        personal_document = DocumentFactory(
            project=None, organization=self.org, title="My Notes"
        )
        DocumentPermissionFactory(
            document=personal_document,
            user=self.member,
            access_level=AccessLevel.OWNER,
        )
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        titles = [row["title"] for row in response.data["results"]]
        self.assertEqual(titles, ["My Notes"])

    def test_excludes_private_documents_without_a_permission(self):
        DocumentFactory(project=self.project, title="Secret")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.data["results"], [])

    def test_excludes_documents_from_other_organizations(self):
        DocumentFactory(title="Foreign Doc", visibility=Visibility.PUBLIC)
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.data["results"], [])

    def test_excludes_soft_deleted_documents(self):
        DocumentFactory(
            project=self.project,
            title="Deleted Doc",
            visibility=Visibility.PUBLIC,
            is_active=False,
        )
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.data["results"], [])

    def test_search_filters_by_title(self):
        DocumentFactory(
            project=self.project, title="Budget Doc", visibility=Visibility.PUBLIC
        )
        DocumentFactory(
            project=self.project, title="Other Doc", visibility=Visibility.PUBLIC
        )
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url, {"search": "Budg"})

        titles = [row["title"] for row in response.data["results"]]
        self.assertEqual(titles, ["Budget Doc"])

    def test_project_filter_returns_only_that_projects_documents(self):
        DocumentFactory(
            project=self.project, title="Alpha Doc", visibility=Visibility.PUBLIC
        )
        other_project = ProjectFactory(organization=self.org, name="Beta")
        DocumentFactory(
            project=other_project, title="Beta Doc", visibility=Visibility.PUBLIC
        )
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(2):
            response = self.client.get(self.url, {"project": self.project.pk})

        titles = [row["title"] for row in response.data["results"]]
        self.assertEqual(titles, ["Alpha Doc"])

    def test_project_filter_with_a_project_from_another_org_returns_an_empty_list(self):
        foreign_project = ProjectFactory(name="Foreign")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(1):
            response = self.client.get(self.url, {"project": foreign_project.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_project_filter_with_a_private_project_in_own_org_returns_an_empty_list(
        self,
    ):
        """The filter never reveals whether a private project the caller can't
        see exists at all - it behaves identically to a nonexistent or
        cross-org id, always collapsing to an empty list rather than a 404."""
        private_project = ProjectFactory(organization=self.org, name="Vault")
        DocumentFactory(project=private_project, title="Confidential")
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(1):
            response = self.client.get(self.url, {"project": private_project.pk})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_project_filter_with_a_non_numeric_id_returns_an_empty_list(self):
        self.client.force_authenticate(self.member)

        with self.assertNumQueries(0):
            response = self.client.get(self.url, {"project": "not-a-number"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

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
        DocumentPermissionFactory(
            document=self.document, user=self.owner, access_level=AccessLevel.OWNER
        )
        DocumentPermissionFactory(
            document=self.document, user=self.editor, access_level=AccessLevel.EDITOR
        )
        DocumentPermissionFactory(
            document=self.document, user=self.viewer, access_level=AccessLevel.VIEWER
        )
        self.url = reverse("document_detail", args=[self.document.pk])

    def test_member_with_viewer_permission_can_retrieve(self):
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Doc1")
        self.assertEqual(response.data["access_level"], AccessLevel.VIEWER)

    def test_public_document_viewer_without_an_explicit_permission_can_retrieve(self):
        public_document = DocumentFactory(
            project=self.project, title="Doc2", visibility=Visibility.PUBLIC
        )
        self.client.force_authenticate(self.stranger)

        with self.assertNumQueries(2):
            response = self.client.get(
                reverse("document_detail", args=[public_document.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_member_without_permission_gets_a_404_not_a_403(self):
        self.client.force_authenticate(self.stranger)

        with self.assertNumQueries(1):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_org_document_is_a_404_not_a_403(self):
        foreign = DocumentFactory(title="Foreign")
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(1):
            response = self.client.get(reverse("document_detail", args=[foreign.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_editor_can_update(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(3):
            response = self.client.patch(
                self.url, {"title": "Doc1 Prime"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "Doc1 Prime")

    def test_viewer_cannot_update(self):
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(2):
            response = self.client.patch(
                self.url, {"title": "Doc1 Prime"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_change_visibility(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.patch(
                self.url, {"visibility": Visibility.PUBLIC}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.document.refresh_from_db()
        self.assertEqual(self.document.visibility, Visibility.PUBLIC)

    def test_editor_cannot_change_visibility(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(3):
            response = self.client.patch(
                self.url, {"visibility": Visibility.PUBLIC}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.document.refresh_from_db()
        self.assertEqual(self.document.visibility, Visibility.PRIVATE)

    def test_owner_can_soft_delete_and_document_drops_out_of_the_api(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(3):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.document.refresh_from_db()
        self.assertFalse(self.document.is_active)

        with self.assertNumQueries(1):
            follow_up = self.client.get(self.url)
        self.assertEqual(follow_up.status_code, status.HTTP_404_NOT_FOUND)

    def test_editor_cannot_delete(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(2):
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
        DocumentPermissionFactory(
            document=self.document, user=self.owner, access_level=AccessLevel.OWNER
        )
        DocumentPermissionFactory(
            document=self.document, user=self.editor, access_level=AccessLevel.EDITOR
        )
        self.url = reverse("document_restore", args=[self.document.pk])

    def test_owner_can_restore_a_soft_deleted_document(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(3):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Doc1")
        self.assertEqual(response.data["access_level"], AccessLevel.OWNER)
        self.document.refresh_from_db()
        self.assertTrue(self.document.is_active)

    def test_editor_cannot_restore(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(2):
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
        DocumentPermissionFactory(
            document=self.document, user=self.owner, access_level=AccessLevel.OWNER
        )
        DocumentPermissionFactory(
            document=self.document, user=self.editor, access_level=AccessLevel.EDITOR
        )
        self.url = reverse("document_share", args=[self.document.pk])

    @patch("core.email.send_mail")
    def test_owner_can_share_with_a_new_user(self, mock_send_mail):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(11):
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

        with self.assertNumQueries(9):
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

        with self.assertNumQueries(4):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_ids = {row["user"] for row in response.data["results"]}
        self.assertEqual(user_ids, {self.owner.pk, self.editor.pk, self.target.pk})

    def test_editor_cannot_share(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(2):
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

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_org_target_user_is_rejected(self):
        foreign_user = UserFactory()
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
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
        DocumentPermissionFactory(
            document=self.document, user=self.owner, access_level=AccessLevel.OWNER
        )
        DocumentPermissionFactory(
            document=self.document, user=self.editor, access_level=AccessLevel.EDITOR
        )
        DocumentPermissionFactory(
            document=self.document, user=self.target, access_level=AccessLevel.EDITOR
        )
        self.url = reverse(
            "document_share_revoke", args=[self.document.pk, self.target.pk]
        )

    def test_owner_can_revoke_and_access_is_removed_entirely(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(resolve_access(self.target, self.document))

    def test_owner_can_revoke_and_public_document_still_grants_implicit_viewer(self):
        self.document.visibility = Visibility.PUBLIC
        self.document.save(update_fields=["visibility"])
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(resolve_access(self.target, self.document), AccessLevel.VIEWER)

    def test_owner_cannot_revoke_the_documents_last_owner(self):
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
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(5):
            response = self.client.delete(
                reverse("document_share_revoke", args=[self.document.pk, co_owner.pk])
            )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIsNone(resolve_access(co_owner, self.document))

    def test_editor_cannot_revoke(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(2):
            response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resolve_access(self.target, self.document), AccessLevel.EDITOR)

    def test_revoking_a_nonexistent_permission_is_a_404(self):
        stranger = UserFactory(organization=self.org)
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(3):
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


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class DocumentAccessRequestAPITests(AssumeActiveSubscription, APITestCase):
    def setUp(self):
        super().setUp()
        self.project = ProjectFactory(name="Alpha")
        self.org = self.project.organization
        self.document = DocumentFactory(
            project=self.project, title="Doc1", visibility=Visibility.PUBLIC
        )
        self.owner = UserFactory(organization=self.org)
        self.other_owner = UserFactory(organization=self.org)
        self.viewer = UserFactory(organization=self.org)
        self.editor = UserFactory(organization=self.org)
        DocumentPermissionFactory(
            document=self.document, user=self.owner, access_level=AccessLevel.OWNER
        )
        DocumentPermissionFactory(
            document=self.document,
            user=self.other_owner,
            access_level=AccessLevel.OWNER,
        )
        DocumentPermissionFactory(
            document=self.document, user=self.editor, access_level=AccessLevel.EDITOR
        )
        self.url = reverse(
            "document_access_request_list_create", args=[self.document.pk]
        )

    @patch("core.email.send_mail")
    def test_viewer_on_a_public_document_can_request_editor_access(
        self, mock_send_mail
    ):
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(6):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        access_request = DocumentAccessRequest.objects.get(
            document=self.document, requested_by=self.viewer
        )
        self.assertEqual(access_request.status, AccessRequestStatus.PENDING)
        mock_send_mail.assert_called_once()
        self.assertEqual(
            set(mock_send_mail.call_args.kwargs["recipient_list"]),
            {self.owner.email, self.other_owner.email},
        )

    def test_editor_already_has_sufficient_access_and_cannot_request(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(2):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            DocumentAccessRequest.objects.filter(requested_by=self.editor).exists()
        )

    def test_owner_already_has_sufficient_access_and_cannot_request(self):
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(2):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_requesting_against_a_private_document_with_no_access_is_a_404(self):
        private_document = DocumentFactory(project=self.project, title="Secret")
        stranger = UserFactory(organization=self.org)
        self.client.force_authenticate(stranger)

        with self.assertNumQueries(1):
            response = self.client.post(
                reverse(
                    "document_access_request_list_create", args=[private_document.pk]
                )
            )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_pending_request_is_rejected(self):
        DocumentAccessRequestFactory(document=self.document, requested_by=self.viewer)
        self.client.force_authenticate(self.viewer)

        with self.assertNumQueries(3):
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            DocumentAccessRequest.objects.filter(requested_by=self.viewer).count(), 1
        )

    def test_owner_can_list_pending_requests(self):
        DocumentAccessRequestFactory(document=self.document, requested_by=self.viewer)
        self.client.force_authenticate(self.owner)

        with self.assertNumQueries(4):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_editor_cannot_list_pending_requests(self):
        self.client.force_authenticate(self.editor)

        with self.assertNumQueries(2):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("core.email.send_mail")
    def test_owner_can_approve_a_request(self, mock_send_mail):
        access_request = DocumentAccessRequestFactory(
            document=self.document, requested_by=self.viewer
        )
        self.client.force_authenticate(self.owner)
        url = reverse(
            "document_access_request_approve",
            args=[self.document.pk, access_request.pk],
        )

        with self.assertNumQueries(14):
            response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, AccessRequestStatus.APPROVED)
        self.assertEqual(access_request.reviewed_by, self.owner)
        self.assertEqual(resolve_access(self.viewer, self.document), AccessLevel.EDITOR)
        mock_send_mail.assert_called_once()
        self.assertEqual(
            mock_send_mail.call_args.kwargs["recipient_list"], [self.viewer.email]
        )

    @patch("core.email.send_mail")
    def test_owner_can_deny_a_request(self, mock_send_mail):
        access_request = DocumentAccessRequestFactory(
            document=self.document, requested_by=self.viewer
        )
        self.client.force_authenticate(self.owner)
        url = reverse(
            "document_access_request_deny",
            args=[self.document.pk, access_request.pk],
        )

        with self.assertNumQueries(5):
            response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, AccessRequestStatus.DENIED)
        self.assertEqual(access_request.reviewed_by, self.owner)
        # Denial doesn't touch DocumentPermission - the requester keeps whatever
        # access they already had (here, the document's implicit public Viewer).
        self.assertEqual(resolve_access(self.viewer, self.document), AccessLevel.VIEWER)
        mock_send_mail.assert_called_once()

    def test_editor_cannot_approve_a_request(self):
        access_request = DocumentAccessRequestFactory(
            document=self.document, requested_by=self.viewer
        )
        self.client.force_authenticate(self.editor)
        url = reverse(
            "document_access_request_approve",
            args=[self.document.pk, access_request.pk],
        )

        with self.assertNumQueries(2):
            response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, AccessRequestStatus.PENDING)

    def test_approving_an_already_resolved_request_is_a_404(self):
        access_request = DocumentAccessRequestFactory(
            document=self.document,
            requested_by=self.viewer,
            status=AccessRequestStatus.APPROVED,
        )
        self.client.force_authenticate(self.owner)
        url = reverse(
            "document_access_request_approve",
            args=[self.document.pk, access_request.pk],
        )

        with self.assertNumQueries(3):
            response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class DocumentTasksTests(TestCase):
    @patch("core.email.send_mail")
    def test_created_task_emails_every_current_owner(self, mock_send_mail):
        document = DocumentFactory(title="Doc1")
        owner_one = UserFactory(organization=document.organization)
        owner_two = UserFactory(organization=document.organization)
        DocumentPermissionFactory(
            document=document, user=owner_one, access_level=AccessLevel.OWNER
        )
        DocumentPermissionFactory(
            document=document, user=owner_two, access_level=AccessLevel.OWNER
        )
        access_request = DocumentAccessRequestFactory(document=document)

        send_access_request_created_email_task(access_request.pk)

        mock_send_mail.assert_called_once()
        self.assertEqual(
            set(mock_send_mail.call_args.kwargs["recipient_list"]),
            {owner_one.email, owner_two.email},
        )

    @patch("core.email.send_mail")
    def test_created_task_is_a_noop_when_the_document_has_no_owner(
        self, mock_send_mail
    ):
        access_request = DocumentAccessRequestFactory()

        send_access_request_created_email_task(access_request.pk)

        mock_send_mail.assert_not_called()
