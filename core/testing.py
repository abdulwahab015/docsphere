from unittest.mock import PropertyMock, patch

from organizations.models import Organization


class AssumeActiveSubscription:
    """Test mixin that makes ``Organization.active_subscription`` truthy for the
    duration of each test, so ``HasActiveSubscription`` passes without any
    dj-stripe rows. Use it where a paid organization is a precondition rather
    than the thing under test."""

    def setUp(self):
        super().setUp()
        patcher = patch.object(
            Organization,
            "active_subscription",
            new_callable=PropertyMock,
            return_value=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
