"""
Django settings for clinic project — Offline LAN / Waitress Production Build
Optimized for: Windows 11 · Mobile Hotspot · Zero Internet · SQLite
"""

import os
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Security ─────────────────────────────────────────────────────────────────
# NOTE: Move SECRET_KEY to env var for production:
#   set DJANGO_SECRET_KEY=<your-key>
import secrets
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-ilon790hk!3bj+zd$ng^-qy0hv4&bqgc699jtvo2-&%(#eg7w0'
)

DEBUG = False

# Allow all LAN IPs (hotspot clients + localhost)
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    '0.0.0.0',
    '192.168.137.1',   # Windows default hotspot gateway IP
    '192.168.1.1',     # Common router LAN IP
    '*',               # Wildcard fallback — restrict in strict production
]

# ─── CSRF — LAN friendly ──────────────────────────────────────────────────────
# HTMX sends X-CSRFToken header; SameSite=Lax works for same-origin requests
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = False
# Trust all local IPs on the hotspot
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://192.168.137.1:8000',
    'http://192.168.137.1:8080',
    'http://192.168.1.1:8000',
]

SESSION_COOKIE_SECURE = False

# ─── Application definition ───────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app.apps.AppConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise serves static files at full speed — must be SECOND
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Timezone set in settings — no per-request overhead
    'app.middleware.TimezoneMiddleware',
]

# ─── Auth ─────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'app.CustomUser'
LOGIN_URL = 'clinic:htmx_login'
LOGIN_REDIRECT_URL = 'clinic:index'
LOGOUT_REDIRECT_URL = 'clinic:htmx_login'

ROOT_URLCONF = 'clinic.urls'

# ─── Templates ────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'clinic.wsgi.application'

# ─── Database — SQLite WAL mode for multi-device hotspot ─────────────────────
DATA_DIR = Path(os.environ.get('CLINIC_DATA_DIR', BASE_DIR.parent / 'data'))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,      # Wait up to 20s for locked DB (multi-device)
            'init_command': "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA cache_size=10000; PRAGMA temp_store=MEMORY;",
        },
    }
}

# ─── Sessions — Cache-backed for speed (no DB hit per request) ────────────────
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'clinic-session-cache',
        'TIMEOUT': 3600,  # 1 hour
    }
}

# ─── Password validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Internationalization ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'

# Clinic is in India (IST) — set directly here, middleware is no longer needed
# but kept for compatibility
TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True
USE_TZ = True

# ─── Static files — WhiteNoise serves with compression + cache headers ─────────
STATIC_URL = '/static/'
STATIC_ROOT = Path(os.environ.get('CLINIC_STATIC_ROOT', BASE_DIR / 'staticfiles'))

# WhiteNoise: serve pre-compressed files with long-lived cache headers
# This means browsers cache static files and NEVER re-request them
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# WhiteNoise settings — serve static files with 1-year cache
WHITENOISE_MAX_AGE = 31536000          # 1 year in seconds
WHITENOISE_ALLOW_ALL_ORIGINS = True

# ─── Media files ──────────────────────────────────────────────────────────────
MEDIA_URL = '/media/'
MEDIA_ROOT = DATA_DIR / 'media'

# ─── Default PK ───────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── Logging — disable in production to avoid I/O overhead ───────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'null': {
            'class': 'logging.NullHandler',
        },
    },
    'root': {
        'handlers': ['null'],
    },
}
