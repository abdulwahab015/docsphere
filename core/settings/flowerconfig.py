"""Flower configuration — passed as `celery -A core flower --conf=...`.

Not a Django settings module (no `from base import *`); Flower imports it
directly and reads module-level names as its options.
"""

from decouple import config

broker = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")

# "user:password" — required, no default: a misconfigured deploy should fail to
# start Flower rather than expose an unauthenticated dashboard.
basic_auth = [config("FLOWER_BASIC_AUTH")]
