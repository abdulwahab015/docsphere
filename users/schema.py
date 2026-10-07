from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class JWTAuthenticationScheme(SimpleJWTScheme):
    """Documents ``users.authentication.JWTAuthentication`` exactly like
    SimpleJWT's own class, which it extends (drf-spectacular matches the class
    itself, not its subclasses). Registered by being imported."""

    target_class = "users.authentication.JWTAuthentication"
