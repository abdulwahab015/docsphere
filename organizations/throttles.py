from rest_framework.throttling import ScopedRateThrottle


class OrganizationScopedRateThrottle(ScopedRateThrottle):
    """A scoped rate shared by everyone in the caller's organization, rather
    than one per person - for limits on what the organization as a whole may
    ask for (its exports). Needs an authenticated member, so it's for views
    whose permissions require one."""

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.organization_id,
        }
