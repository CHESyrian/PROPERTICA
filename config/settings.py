"""
Django settings for PROPERTICA.
Loads configuration from .env (see .env.example).
"""

from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    os.environ.get(
        "DJANGO_SECRET_KEY",
        "django-insecure-dev-only-change-me-in-production",
    ),
)

DEBUG = os.environ.get("DEBUG", os.environ.get("DJANGO_DEBUG", "true")).lower() in ("1", "true", "yes")

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")).split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "django_filters",
    # Project apps
    "accounts",
    "listings",
    "messaging",
    "search_app",
    "core",
    "api",
    "rest_framework.authtoken",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
# - Default: SQLite (local/dev/tests)
# - PostgreSQL when USE_POSTGRES=true or DATABASE_URL is set
_use_postgres = (
    os.environ.get("USE_POSTGRES", "").lower() in ("1", "true", "yes")
    or bool(os.environ.get("DATABASE_URL", "").strip())
)
if _use_postgres:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "propertica_db"),
            "USER": os.environ.get("POSTGRES_USER", "propertica"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ar"
TIME_ZONE = "Asia/Damascus"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ("ar", "العربية"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# RTL languages
RTL_LANGUAGES = {"ar"}

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Custom user model (must be set before first migration)
AUTH_USER_MODEL = "accounts.Account"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "core:home"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "api.pagination.ProperticaPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
}

# ── Email ─────────────────────────────────────────────────────────────
# Default: console in DEBUG, SMTP when EMAIL_HOST is set (production-ready).
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@propertica.example.com")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "false").lower() in ("1", "true", "yes")

_email_backend_override = os.environ.get("EMAIL_BACKEND", "").strip()
if _email_backend_override:
    EMAIL_BACKEND = _email_backend_override
elif EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# ── Cache (LocMem default; Redis-ready) ───────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "propertica-default",
    }
}
if os.environ.get("REDIS_URL"):
    CACHES["default"] = {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["REDIS_URL"],
    }

# ── Rate limits (requests per window) ─────────────────────────────────
RATE_LIMITS = {
    "contact": (10, 3600),       # 10 / hour
    "report": (10, 3600),
    "register": (5, 3600),
    "login": (20, 900),
    "phone_code": (5, 3600),
    "geocode": (60, 3600),
}

# ── Search backend ────────────────────────────────────────────────────
# "db" (default) or "opensearch" (stub until cluster is wired)
SEARCH_BACKEND = os.environ.get("SEARCH_BACKEND", "db")
OPENSEARCH_URL = os.environ.get("OPENSEARCH_URL", "")

# ── Media storage (local default; S3-compatible optional) ─────────────
# When USE_S3=true, uploads go to the bucket via django-storages + boto3.
# Works with AWS S3, Cloudflare R2, MinIO, DigitalOcean Spaces, etc.
USE_S3 = os.environ.get("USE_S3", "false").lower() in ("1", "true", "yes")
if USE_S3:
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL") or None
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN", "") or None
    AWS_DEFAULT_ACL = os.environ.get("AWS_DEFAULT_ACL", "public-read") or None
    AWS_QUERYSTRING_AUTH = os.environ.get("AWS_QUERYSTRING_AUTH", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": os.environ.get("AWS_S3_CACHE_CONTROL", "max-age=86400"),
    }
    AWS_S3_FILE_OVERWRITE = False  # keep unique names on collision
    AWS_S3_SIGNATURE_VERSION = os.environ.get("AWS_S3_SIGNATURE_VERSION", "s3v4")
    # path-style helps MinIO / some regional endpoints; virtual is AWS default
    _addr = os.environ.get("AWS_S3_ADDRESSING_STYLE", "").strip().lower()
    if _addr in ("path", "virtual"):
        AWS_S3_ADDRESSING_STYLE = _addr
    AWS_LOCATION = os.environ.get("AWS_LOCATION", "media").strip() or "media"

    if not AWS_STORAGE_BUCKET_NAME:
        raise ValueError(
            "USE_S3=true requires AWS_STORAGE_BUCKET_NAME "
            "(and usually AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)."
        )

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "location": AWS_LOCATION,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_LOCATION}/"
    elif AWS_S3_ENDPOINT_URL:
        # Generic S3-compatible public URL shape (MinIO / custom endpoints)
        endpoint = AWS_S3_ENDPOINT_URL.rstrip("/")
        MEDIA_URL = f"{endpoint}/{AWS_STORAGE_BUCKET_NAME}/{AWS_LOCATION}/"
    else:
        # Standard AWS virtual-hosted–style URL
        MEDIA_URL = (
            f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}"
            f".amazonaws.com/{AWS_LOCATION}/"
        )

# Featured listing duration when activated (days)
FEATURED_DURATION_DAYS = int(os.environ.get("FEATURED_DURATION_DAYS", "14"))


# ── OAuth (P3-6 scaffolding — wire provider SDK when credentials exist) ─
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
OAUTH_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)


# Soft verification policy:
# - False (default in DEBUG): profile can be used without verifying
# - True in production: show stronger prompts (never hard-blocks core browse)
REQUIRE_ACCOUNT_VERIFICATION = os.environ.get(
    "REQUIRE_ACCOUNT_VERIFICATION",
    "false" if DEBUG else "true",
).lower() in ("1", "true", "yes")


# ── Production security hardening (active when DEBUG is False) ────────
# Set these via env in real deploys; sensible defaults when DEBUG=False.
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() in ("1", "true", "yes")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    # HSTS — enable only once HTTPS is confirmed working
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get(
        "SECURE_HSTS_INCLUDE_SUBDOMAINS", "true"
    ).lower() in ("1", "true", "yes")
    SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "false").lower() in ("1", "true", "yes")
    # Behind a reverse proxy (nginx, Caddy, load balancer)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = os.environ.get("USE_X_FORWARDED_HOST", "true").lower() in ("1", "true", "yes")
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Session / CSRF cookie hardening (safe in both modes)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # must be readable by JS if you ever need it; keep False for forms
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"


# ── WhiteNoise (optional static serving in production) ────────────────
# Install whitenoise and set USE_WHITENOISE=true to serve static files from Django.
USE_WHITENOISE = os.environ.get("USE_WHITENOISE", "false").lower() in ("1", "true", "yes")
if USE_WHITENOISE:
    _security_idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
    MIDDLEWARE.insert(_security_idx + 1, "whitenoise.middleware.WhiteNoiseMiddleware")
    if "STORAGES" not in globals():
        STORAGES = {
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    STORAGES["staticfiles"] = {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }


# ── Logging ───────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG" if DEBUG else "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose" if not DEBUG else "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
