import factory
from django.contrib.auth import get_user_model

from organizations.factories import OrganizationFactory
from users.choices import InvitationStatus, OrganizationRole
from users.models import Invitation

User = get_user_model()

DEFAULT_TEST_PASSWORD = "Test-Pass-123!"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    organization = factory.SubFactory(OrganizationFactory)
    org_role = OrganizationRole.MEMBER

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Route through the manager so the password is hashed properly."""
        password = kwargs.pop("password", DEFAULT_TEST_PASSWORD)
        return model_class.objects.create_user(*args, password=password, **kwargs)


class AdminUserFactory(UserFactory):
    org_role = OrganizationRole.ADMIN


class InvitationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Invitation

    organization = factory.SubFactory(OrganizationFactory)
    invited_by = factory.SubFactory(
        AdminUserFactory, organization=factory.SelfAttribute("..organization")
    )
    email = factory.Sequence(lambda n: f"invitee{n}@example.com")
    token = factory.Sequence(lambda n: f"token-{n}")
    status = InvitationStatus.PENDING
