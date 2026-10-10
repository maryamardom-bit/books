"""
Django settings for config project.
"""

from pathlib import Path
from environs import Env
import os
import sys
from datetime import timedelta

# for environment variables
env = Env()
env.read_env()

TESTING = (len(sys.argv) > 1 and sys.argv[1] == 'test') or 'pytest' in sys.modules

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DJANGO_DEBUG")

ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['127.0.0.1', 'localhost'])
CSRF_TRUSTED_ORIGINS = env.list('DJANGO_CSRF_TRUSTED_ORIGINS', default=[])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',


    # third party
    'jalali_date',
    'crispy_forms',
    'crispy_bootstrap5',
    'auth_style',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'rosetta',
    'ckeditor',
    'phonenumber_field',

    # local
    'accounts.apps.AccountsConfig',
    'pages.apps.PagesConfig',
    'products.apps.ProductsConfig',
    'cart.apps.CartConfig',
    'persian_translate.apps.PersianTranslateConfig',
    'orders.apps.OrdersConfig',
    'payment.apps.PaymentConfig',
    'rest_framework',
    'rest_framework_simplejwt',
    # Required for BLACKLIST_AFTER_ROTATION to actually revoke rotated refresh tokens.
    'rest_framework_simplejwt.token_blacklist',
    'drf_yasg',
    'api',
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.sites.middleware.CurrentSiteMiddleware',
]

INTERNAL_IPS = [
    "127.0.0.1",
]

# The debug toolbar is a development tool only; it must never load in tests or production.
ENABLE_DEBUG_TOOLBAR = DEBUG and not TESTING
if ENABLE_DEBUG_TOOLBAR:
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [str(BASE_DIR.joinpath('templates'))],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart',
                'products.context_processors.faq_context',
                'products.context_processors.search_context',
                'pages.context_processors.site_contact',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DJANGO_DB_NAME', default='postgres'),
        'USER': env('DJANGO_DB_USER', default='postgres'),
        'PASSWORD': env('DJANGO_DB_PASSWORD', default='postgres'),
        'HOST': env('DJANGO_DB_HOST', default='db'),
        'PORT': env.int('DJANGO_DB_PORT', default=5432),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Internationalization
LANGUAGE_CODE = 'fa'
LANGUAGES = (
    ('en', 'English'),
    ('fa', 'Persian'),
)
TIME_ZONE = 'Asia/Tehran'

USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# accounts config
AUTH_USER_MODEL = 'accounts.CustomUser'
LOGIN_REDIRECT_URL = 'product:product_list'
LOGOUT_REDIRECT_URL = 'page:home'

# all auth settings (new)
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*']

# media
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

# crispy forms settings
CRISPY_ALLOWED_TEMPLATE_PACK = "bootstrap5"
CRISPY_TEMPLATE_PACK = 'bootstrap5'

LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'templates', 'locale'),
)

# phone_number
PHONENUMBER_DEFAULT_REGION = 'IR'

# messages
from django.contrib.messages import constants as messages_constant
MESSAGE_TAGS = {
    messages_constant.ERROR: 'danger',
}

CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'Custom',
        'toolbar_Custom': [
            ['Bold', 'Italic', 'Underline'],
            ['NumberedList', 'BulletedList'],
            ['JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock'],
            ['Link', 'Unlink'],
            ['RemoveFormat', 'Source']
        ],
        'height': 500,
        'width': '100%',
    },
}

# Kavenegar SMS
KAVENEGAR_API_KEY = env("KAVENEGAR_API_KEY", default="test_api_key")
KAVENEGAR_SENDER = env("KAVENEGAR_SENDER", default="1000596446")
# Without a real key every SMS would be a failing HTTP call (tests, local dev).
SMS_ENABLED = env.bool('SMS_ENABLED', default=KAVENEGAR_API_KEY != 'test_api_key' and not TESTING)
CART_SESSION_ID = 'cart'

# Payment
PAYMENT_GATEWAY = env('PAYMENT_GATEWAY', default='sep')
# Store prices are in Toman; Iranian gateways charge in Rial.
PAYMENT_AMOUNT_MULTIPLIER = env.int('PAYMENT_AMOUNT_MULTIPLIER', default=10)
PAYMENT_HTTP_TIMEOUT = env.int('PAYMENT_HTTP_TIMEOUT', default=15)
SEP_TERMINAL_ID = env('SEP_TERMINAL_ID', default='test_terminal_id')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'EXCEPTION_HANDLER': 'api.exceptions.api_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': env('API_THROTTLE_ANON', default='60/minute'),
        'user': env('API_THROTTLE_USER', default='240/minute'),
    },
}

if TESTING:
    REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []

REDIS_URL = env('REDIS_URL', default='')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'},
    },
    'root': {'handlers': ['console'], 'level': env('DJANGO_LOG_LEVEL', default='INFO')},
    'loggers': {
        'django.db.backends': {'level': 'WARNING'},
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'USE_SESSION_AUTH': True,
    'JSON_EDITOR': True,
    'SUPPORTED_SUBMIT_METHODS': [
        'get',
        'post',
        'put',
        'patch',
        'delete'
    ],
}