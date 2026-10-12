from django.conf import settings
from django.db import connections
from django.test.runner import DiscoverRunner


class DisposableDatabaseTestRunner(DiscoverRunner):
    """Verifies the server identity before Django creates, migrates or drops any test database."""

    def setup_databases(self, **kwargs):
        for alias in connections:
            self._verify(alias)
        return super().setup_databases(**kwargs)

    def _verify(self, alias):
        connection = connections[alias]
        if connection.vendor != 'postgresql':
            raise RuntimeError(f'Database {alias!r} is not PostgreSQL; refusing to run the isolated suite.')
        with connection._nodb_cursor() as cursor:
            cursor.execute(
                "SELECT current_setting('cluster_name'), current_user, "
                "(SELECT rolsuper FROM pg_roles WHERE rolname = current_user), "
                "(SELECT system_identifier FROM pg_control_system())::text, current_setting('server_version_num')"
            )
            cluster, user, superuser, system_id, version = cursor.fetchone()
        if cluster != settings.DISPOSABLE_CLUSTER_NAME:
            raise RuntimeError(f'Database {alias!r} is not the disposable server (cluster_name={cluster!r}).')
        if superuser:
            raise RuntimeError(f'Database {alias!r}: role {user!r} is a superuser; use the isolated test role.')
        self.log(f'Disposable PostgreSQL verified: alias={alias} cluster={cluster} role={user} '
                 f'system_identifier={system_id} server_version_num={version}')
