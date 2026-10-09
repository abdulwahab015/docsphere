import factory

from audit.choices import AuditVerb
from audit.models import AuditEvent
from organizations.factories import OrganizationFactory
from users.factories import AdminUserFactory


class AuditEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AuditEvent

    organization = factory.SubFactory(OrganizationFactory)
    actor = factory.SubFactory(
        AdminUserFactory, organization=factory.SelfAttribute("..organization")
    )
    verb = AuditVerb.MEMBER_REACTIVATED
