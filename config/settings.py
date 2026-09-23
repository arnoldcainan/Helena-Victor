import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(f"{name} deve ser um número inteiro.") from exc


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEBUG = env_bool("DEBUG", True)
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "unsafe-development-key-change-me"
    else:
        raise ImproperlyConfigured("SECRET_KEY é obrigatória quando DEBUG=False.")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if railway_domain and railway_domain not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(railway_domain)
if DEBUG and "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS é obrigatório quando DEBUG=False.")

INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "events"]
if os.getenv("CLOUDINARY_URL"):
    INSTALLED_APPS += ["cloudinary", "cloudinary_storage"]

MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
MIDDLEWARE.insert(1, "config.middleware.ContentSecurityPolicyMiddleware")
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
if os.getenv("DATABASE_URL"):
    import dj_database_url
    DATABASES["default"] = dj_database_url.config(conn_max_age=600, ssl_require=not DEBUG)

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
if os.getenv("CLOUDINARY_URL"):
    STORAGES["default"] = {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/casal/"
LOGOUT_REDIRECT_URL = "/"
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if railway_domain and f"https://{railway_domain}" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(f"https://{railway_domain}")
EVENT_BASE_URL = os.getenv("EVENT_BASE_URL", f"https://{railway_domain}" if railway_domain else "http://localhost:8000")
AUTO_APPROVE_UPLOADS = env_bool("AUTO_APPROVE_UPLOADS", True)
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 20)
MAX_IMAGE_PIXELS = env_int("MAX_IMAGE_PIXELS", 40_000_000)
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_IMAGE_MIME_TYPES = {"JPEG": {"image/jpeg", "image/pjpeg"}, "PNG": {"image/png"}, "WEBP": {"image/webp"}}

UPLOAD_RATE_BURST_LIMIT = env_int("UPLOAD_RATE_BURST_LIMIT", 3)
UPLOAD_RATE_BURST_SECONDS = env_int("UPLOAD_RATE_BURST_SECONDS", 20)
UPLOAD_RATE_WINDOW_LIMIT = env_int("UPLOAD_RATE_WINDOW_LIMIT", 12)
UPLOAD_RATE_WINDOW_SECONDS = env_int("UPLOAD_RATE_WINDOW_SECONDS", 600)
UPLOAD_RATE_IP_LIMIT = env_int("UPLOAD_RATE_IP_LIMIT", 60)
GALLERY_POLL_SECONDS = env_int("GALLERY_POLL_SECONDS", 20)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0 if DEBUG else 31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False

CSP_ENABLED = env_bool("CSP_ENABLED", True)
CSP_REPORT_ONLY = env_bool("CSP_REPORT_ONLY", DEBUG)
CSP_DIRECTIVES = {
    "default-src": ("'self'",),
    "script-src": ("'self'",),
    "script-src-attr": ("'none'",),
    "style-src": ("'self'", "https://fonts.googleapis.com"),
    "style-src-attr": ("'none'",),
    "font-src": ("'self'", "https://fonts.gstatic.com"),
    "img-src": ("'self'", "data:", "blob:", "https://res.cloudinary.com"),
    "connect-src": ("'self'",),
    "form-action": ("'self'",),
    "frame-ancestors": ("'none'",),
    "base-uri": ("'self'",),
    "object-src": ("'none'",),
}
