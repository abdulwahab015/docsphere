from django.db import models
from django_extensions.db.models import TimeStampedModel  # noqa: F401


class ActiveModel(models.Model):
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
