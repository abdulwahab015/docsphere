from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "users"

    def ready(self):
        # Registers how the API schema documents the authentication class.
        from users import schema
