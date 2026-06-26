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
    'ai',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

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

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# ── CORS ──────────────────────────────────────────────────────────────────────
_cors_env = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    config('FRONTEND_URL', default='http://localhost:5173'),
)
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]
_dev_origins = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]
for _o in _dev_origins:
    if _o not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(_o)

_csrf_env = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_env.split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept", "accept-encoding", "authorization", "content-type",
    "dnt", "origin", "user-agent", "x-csrftoken", "x-requested-with",
]
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

# ── Static & Media ────────────────────────────────────────────────────────────
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'

USE_S3 = config('USE_S3', default=False, cast=bool)
if USE_S3:
    AWS_ACCESS_KEY_ID       = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY   = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME      = config('AWS_S3_REGION_NAME', default='us-east-1')
    AWS_DEFAULT_ACL         = 'private'
    AWS_S3_FILE_OVERWRITE   = False
    DEFAULT_FILE_STORAGE    = 'storages.backends.s3boto3.S3Boto3Storage'

# ── i18n ──────────────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Africa/Accra'
USE_I18N      = True
USE_TZ        = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Email ─────────────────────────────────────────────────────────────────────
# Configure via environment variables. Supports SendGrid (recommended),
# Mailgun, or any SMTP provider.
#
# For SendGrid: set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
#   EMAIL_HOST=smtp.sendgrid.net  EMAIL_PORT=587
#   EMAIL_HOST_USER=apikey  EMAIL_HOST_PASSWORD=<your_sendgrid_api_key>
#
# For local development/testing, leave EMAIL_BACKEND unset to use the
# console backend (emails print to logs, nothing actually sent).
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST          = config('EMAIL_HOST',          default='smtp.sendgrid.net')
EMAIL_PORT          = config('EMAIL_PORT',          default=587, cast=int)
EMAIL_USE_TLS       = config('EMAIL_USE_TLS',       default=True, cast=bool)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER',     default='apikey')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config(
    'DEFAULT_FROM_EMAIL',
    default='FarmAsyst North <noreply@farmasystnorth.com>',
)

# ── Third-party credentials ───────────────────────────────────────────────────
MOMO_BASE_URL         = config('MOMO_BASE_URL',         default='https://sandbox.momodeveloper.mtn.com')
MOMO_SUBSCRIPTION_KEY = config('MOMO_SUBSCRIPTION_KEY', default='')
MOMO_API_USER         = config('MOMO_API_USER',         default='')
MOMO_API_KEY          = config('MOMO_API_KEY',          default='')
MOMO_ENVIRONMENT      = config('MOMO_ENVIRONMENT',      default='sandbox')
BACKEND_URL           = config('BACKEND_URL',           default='http://localhost:8000')
MOMO_CALLBACK_URL     = config('MOMO_CALLBACK_URL',     default='')
MOMO_WEBHOOK_SECRET   = config('MOMO_WEBHOOK_SECRET',   default='')

AFRICASTALKING_USERNAME = config('AFRICASTALKING_USERNAME', default='')
AFRICASTALKING_API_KEY  = config('AFRICASTALKING_API_KEY',  default='')

PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')

HUBTEL_CLIENT_ID      = config('HUBTEL_CLIENT_ID',      default='')
HUBTEL_CLIENT_SECRET  = config('HUBTEL_CLIENT_SECRET',  default='')
HUBTEL_SENDER_ID      = config('HUBTEL_SENDER_ID',      default='FarmAsyst')
HUBTEL_PAYMENT_CLIENT_ID       = config('HUBTEL_PAYMENT_CLIENT_ID',       default='')
HUBTEL_PAYMENT_CLIENT_SECRET   = config('HUBTEL_PAYMENT_CLIENT_SECRET',   default='')
HUBTEL_MERCHANT_ACCOUNT_NUMBER = config('HUBTEL_MERCHANT_ACCOUNT_NUMBER', default='')

TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN  = config('TWILIO_AUTH_TOKEN',  default='')
TWILIO_FROM_NUMBER = config('TWILIO_FROM_NUMBER', default='')

FRONTEND_URL      = config('FRONTEND_URL', default='http://localhost:5173')
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{asctime}] {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'payments':       {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'marketplace':    {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'notifications':  {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django':         {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}
