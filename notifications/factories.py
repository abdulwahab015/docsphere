import factory

from notifications.choices import NotificationVerb
from notifications.models import Notification
from users.factories import UserFactory


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    recipient = factory.SubFactory(UserFactory)
    actor = factory.SubFactory(
        UserFactory, organization=factory.SelfAttribute("..recipient.organization")
    )
    verb = NotificationVerb.ACCESS_REQUEST_DENIED
