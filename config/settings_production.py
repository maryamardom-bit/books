"""Production settings: everything from settings.py plus transport/cookie hardening."""

from .settings import *  # noqa: F401,F403
from .settings import env

DEBUG = False

# nginx terminates TLS and forwards X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool('DJANGO_SECURE_SSL_REDIRECT', default=True)
# /health/ is probed over plain HTTP from inside the Docker network.
SECURE_REDIRECT_EXEMPT = [r'^health/$']
SECURE_HSTS_SECONDS = env.int('DJANGO_SECURE_HSTS_SECONDS', default=60 * 60 * 24 * 30)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = env.bool('DJANGO_SECURE_HSTS_PRELOAD', default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
# Lax (not Strict): the bank redirects the customer back to us with a cross-site navigation.
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

STATIC_ROOT = env('DJANGO_STATIC_ROOT', default=str(BASE_DIR / 'staticfiles'))  # noqa: F405
MEDIA_ROOT = env('DJANGO_MEDIA_ROOT', default=str(BASE_DIR / 'media'))  # noqa: F405

EMAIL_BACKEND = env('DJANGO_EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('DJANGO_EMAIL_HOST', default='localhost')
EMAIL_PORT = env.int('DJANGO_EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('DJANGO_EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('DJANGO_EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('DJANGO_EMAIL_USE_TLS', default=True)
DEFAULT_FROM_EMAIL = env('DJANGO_DEFAULT_FROM_EMAIL', default='no-reply@kasra-pub.ir')
