from django.db import models
from django_extensions.db.models import (
    TimeStampedModel as _DjangoExtensionsTimeStampedModel,
)


class TimeStampedModel(_DjangoExtensionsTimeStampedModel):
    """created/modified timestamps plus is_active, in one base class."""

    is_active = models.BooleanField(default=True)

    class Meta(_DjangoExtensionsTimeStampedModel.Meta):
        abstract = True
