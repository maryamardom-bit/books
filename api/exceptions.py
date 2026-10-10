"""Single error envelope for every API response: {"success": false, "error": {...}}."""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class APIError(exceptions.APIException):
    """Raise from views for business-rule failures, e.g. APIError('BOOK_OUT_OF_STOCK', 'این کتاب موجود نیست.')."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code, message, status_code=None):
        super().__init__(detail=message, code=code)
        self.error_code = code
        if status_code is not None:
            self.status_code = status_code


_DEFAULT_CODES = {
    status.HTTP_400_BAD_REQUEST: 'VALIDATION_ERROR',
    status.HTTP_401_UNAUTHORIZED: 'NOT_AUTHENTICATED',
    status.HTTP_403_FORBIDDEN: 'PERMISSION_DENIED',
    status.HTTP_404_NOT_FOUND: 'NOT_FOUND',
    status.HTTP_405_METHOD_NOT_ALLOWED: 'METHOD_NOT_ALLOWED',
    status.HTTP_429_TOO_MANY_REQUESTS: 'RATE_LIMITED',
}


def error_response(code, message, http_status, details=None):
    error = {'code': code, 'message': message}
    if details is not None:
        error['details'] = details
    return Response({'success': False, 'error': error}, status=http_status)


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        return None

    code = getattr(exc, 'error_code', None) or _DEFAULT_CODES.get(response.status_code, 'ERROR')
    details = None
    if isinstance(exc, exceptions.ValidationError):
        details = response.data
        message = 'Invalid input.'
    else:
        message = str(getattr(exc, 'detail', '')) or str(exc)

    new_response = error_response(code, message, response.status_code, details)
    for header in ('WWW-Authenticate', 'Retry-After', 'Allow'):
        if header in response:
            new_response[header] = response[header]
    return new_response
