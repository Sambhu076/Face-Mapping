import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file(ENV_FILE)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-replace-this-in-production")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "DJANGO_CSRF_TRUSTED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "faces",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "studioface.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "studioface.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "facemap"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "600")),
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DATA_UPLOAD_MAX_NUMBER_FILES = int(os.getenv("DJANGO_DATA_UPLOAD_MAX_NUMBER_FILES", "1000"))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", "104857600"))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE", "10485760"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "faces:login"
LOGIN_REDIRECT_URL = "faces:admin-dashboard"
LOGOUT_REDIRECT_URL = "faces:login"

FACE_APP = {
    "FAISS_INDEX_PATH": BASE_DIR / "data" / "face.index",
    "FAISS_MAPPING_PATH": BASE_DIR / "data" / "face_mapping.json",
    "EMBEDDING_DIMENSION": 512,
    "SIMILARITY_THRESHOLD": float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.45")),
    "MAX_RESULTS": 24,
    "SEARCH_TOP_K": int(os.getenv("FACE_SEARCH_TOP_K", "256")),
    "DETECTION_CONFIDENCE_THRESHOLD": float(os.getenv("FACE_DETECTION_CONFIDENCE_THRESHOLD", "0.55")),
    "INSIGHTFACE_CTX_ID": -1,
    "INSIGHTFACE_PROVIDERS": [
        provider.strip()
        for provider in os.getenv("FACE_INSIGHTFACE_PROVIDERS", "CPUExecutionProvider").split(",")
        if provider.strip()
    ],
    "ALLOW_OPENCV_FALLBACK": os.getenv("FACE_ALLOW_OPENCV_FALLBACK", "false").lower() == "true",
    "SEARCH_ALL_QUERY_FACES": os.getenv("FACE_SEARCH_ALL_QUERY_FACES", "true").lower() == "true",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "faces": {
            "handlers": ["console"],
            "level": os.getenv("FACE_LOG_LEVEL", "INFO").upper(),
            "propagate": False,
        },
    },
}

# Optimized Cache for local development WITHOUT Redis:
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://redis:6379/1"),
    }
}

# Run Celery tasks synchronously (in-thread) without Redis broker:
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

USE_X_FORWARDED_HOST = True

