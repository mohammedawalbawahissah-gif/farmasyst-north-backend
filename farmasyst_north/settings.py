from pathlib import Path
from decouple import config
from datetime import timedelta
import dj_database_url
import os
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "False") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
]

LOCAL_APPS = [
    'accounts',
    'farms',
    'credit',
    'investors',
    'marketplace',
    'training',
    'notifications',
    'payments',
    'vet',
    'inputs',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'farmasyst_north.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'farmasyst_north.wsgi.application'

# ── Database ──────────────────────────────────────────────────────────────────
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
    )
}


# ── Auth ──────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── DRF ───────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}

# ── JWT ───────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        config('FRONTEND_URL', default='http://localhost:5173')
    ).split(",")
    if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

# ── Static & Media ────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

USE_S3 = config('USE_S3', default=False, cast=bool)
if USE_S3:
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')
    AWS_DEFAULT_ACL = 'private'
    AWS_S3_FILE_OVERWRITE = False
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# ── i18n ──────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Accra'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Third-party credentials ───────────────────────────────────────────────────
MOMO_BASE_URL         = config('MOMO_BASE_URL', default='https://sandbox.momodeveloper.mtn.com')
MOMO_SUBSCRIPTION_KEY = config('MOMO_SUBSCRIPTION_KEY', default='')
MOMO_API_USER         = config('MOMO_API_USER', default='')
MOMO_API_KEY          = config('MOMO_API_KEY', default='')
MOMO_ENVIRONMENT      = config('MOMO_ENVIRONMENT', default='sandbox')

PAYSTACK_SECRET_KEY   = config('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PUBLIC_KEY   = config('PAYSTACK_PUBLIC_KEY', default='')

HUBTEL_CLIENT_ID      = config('HUBTEL_CLIENT_ID', default='')
HUBTEL_CLIENT_SECRET  = config('HUBTEL_CLIENT_SECRET', default='')
HUBTEL_SENDER_ID      = config('HUBTEL_SENDER_ID', default='FarmAsyst')

TWILIO_ACCOUNT_SID    = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN     = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_FROM_NUMBER    = config('TWILIO_FROM_NUMBER', default='')
