from .development import *
from .base import env

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.str("POSTGRES_DB", default="cafirm_dev"),
        "USER": env.str("POSTGRES_USER", default="cafirm_app"),
        "PASSWORD": env.str("POSTGRES_PASSWORD", default=""),
        "HOST": env.str("POSTGRES_HOST", default="127.0.0.1"),
        "PORT": env.int("POSTGRES_PORT", default=5432),
    }
}
