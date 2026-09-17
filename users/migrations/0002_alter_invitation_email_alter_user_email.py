from django.db import migrations
from django.db.models.functions import Lower

import users.fields


def lowercase_existing_emails(apps, schema_editor):
    """Bring any rows written before EmailField normalized to lowercase."""
    for model_name in ("User", "Invitation"):
        model = apps.get_model("users", model_name)
        model.objects.exclude(email=Lower("email")).update(email=Lower("email"))


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invitation",
            name="email",
            field=users.fields.EmailField(max_length=254),
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=users.fields.EmailField(max_length=254, unique=True),
        ),
        migrations.RunPython(
            lowercase_existing_emails, migrations.RunPython.noop, elidable=True
        ),
    ]
