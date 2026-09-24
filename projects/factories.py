import factory

from organizations.factories import OrganizationFactory
from projects.choices import AccessLevel
from projects.models import (
    Document,
    DocumentAccessRequest,
    DocumentPermission,
    Project,
    ProjectPermission,
)
from users.factories import UserFactory


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    organization = factory.SubFactory(OrganizationFactory)
    created_by = factory.SubFactory(
        UserFactory, organization=factory.SelfAttribute("..organization")
    )
    name = factory.Sequence(lambda n: f"Project {n}")


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    project = factory.SubFactory(ProjectFactory)
    organization = factory.LazyAttribute(
        lambda document: document.project.organization if document.project else None
    )
    created_by = factory.SubFactory(
        UserFactory, organization=factory.SelfAttribute("..organization")
    )
    title = factory.Sequence(lambda n: f"Document {n}")


class ProjectPermissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProjectPermission

    project = factory.SubFactory(ProjectFactory)
    user = factory.SubFactory(
        UserFactory, organization=factory.SelfAttribute("..project.organization")
    )
    access_level = AccessLevel.VIEWER


class DocumentPermissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentPermission

    document = factory.SubFactory(DocumentFactory)
    user = factory.SubFactory(
        UserFactory,
        organization=factory.SelfAttribute("..document.organization"),
    )
    access_level = AccessLevel.VIEWER


class DocumentAccessRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DocumentAccessRequest

    document = factory.SubFactory(DocumentFactory)
    requested_by = factory.SubFactory(
        UserFactory, organization=factory.SelfAttribute("..document.organization")
    )
