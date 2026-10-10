"""Liveness/readiness checks for load balancers and the admin System Health page."""

import time
import uuid

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


def _check_database():
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        cursor.fetchone()


def _check_cache():
    key = f'health:{uuid.uuid4().hex}'
    cache.set(key, 'ok', 5)
    if cache.get(key) != 'ok':
        raise RuntimeError('cache read-back failed')
    cache.delete(key)


CHECKS = {
    'database': _check_database,
    'cache': _check_cache,
    # TODO(Phase 1/2): storage (S3), email, SMS, payment gateway reachability, search, queue.
}


def run_checks():
    results = {}
    for name, check in CHECKS.items():
        started = time.monotonic()
        try:
            check()
            results[name] = {'status': 'PASS'}
        except Exception as exc:  # noqa: BLE001 - a health probe must report, not raise
            results[name] = {'status': 'FAIL', 'error': exc.__class__.__name__}
        results[name]['ms'] = round((time.monotonic() - started) * 1000, 1)
    return results


@never_cache
@require_GET
def health_view(request):
    results = run_checks()
    healthy = all(item['status'] == 'PASS' for item in results.values())
    return JsonResponse(
        {'status': 'PASS' if healthy else 'FAIL', 'checks': results},
        status=200 if healthy else 503,
    )
