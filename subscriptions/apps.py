from django.apps import AppConfig


class SubscriptionsConfig(AppConfig):
    name = "subscriptions"

    def ready(self):
        from subscriptions import signals
