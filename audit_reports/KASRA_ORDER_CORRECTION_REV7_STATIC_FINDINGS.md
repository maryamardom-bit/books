# Kasra order-correction — Revision 7 static findings

Status: **evidence note only**. This file records what source inspection established at one commit. It is not an approval, not a test report, and not permission to execute.

Inspection method: read-only. No implementation file was edited. No test, migration, importer, correction, rollback, or database session was run for this note.

## 1. Tree identity at inspection

| Item | Observed value |
| --- | --- |
| Branch | `cursor/payment-hardening-and-architecture-review` |
| Upstream | `origin/cursor/payment-hardening-and-architecture-review` (status: up to date) |
| HEAD | `2c3b9fde70fc7ff3e5b5f7a72bdcb111b9d74d03` |
| HEAD subject | `add test` |
| HEAD author date | `2026-10-12T12:44:27+03:30` |
| Working tree before this note | clean (`git status --porcelain` empty) |
| Django pin | `Django==6.0.2` in `requirements.txt` |
| Installed Django | `django.VERSION = (6, 0, 2, "final", 0)` in the local virtualenv |
| Driver pin | `psycopg2-binary==2.9.11` |
| Installed driver | `psycopg2 2.9.11 (dt dec pq3 ext lo64)` |
| PostgreSQL image named in compose | `postgres:16` (tag, not a digest) in `docker-compose.yml` and `docker-compose.prod.yml` |
| Target server version | **NOT VERIFIED**. No database connection was opened. |

No file named `KASRA_ORDER_CORRECTION_PLAN_REV6.md`, and no other Revision 6 plan, exists in the tracked tree. `audit_reports/` at HEAD contained only:

- `P0_2_PHASE1_CURRENCY_CONVERTER_RECONCILIATION.md`
- `P0_2_PHASE2_READ_ONLY_RECONCILIATION.md`
- `P0_2_PHASE3_CORRECTION_PLAN.md`
- `WORDPRESS_DJANGO_FEATURE_GAP_AUDIT.md`

The Phase 3 plan is an input. Several of its statements are stale relative to HEAD. Those contradictions are listed in section 8. They are not treated as proof that a gate passed.

## 2. Execution controls observed in source

In `products/management/commands/correct_imported_order_amounts.py`:

- `EXECUTION_ENABLED = False` (line 70).
- `APPROVED_ANOMALY_WORDPRESS_IDS = frozenset()` (line 75), with `EXPECTED_ANOMALY_COUNT = 2`.
- `AUTHORIZED_APPROVALS = {}` (line 80).

`--apply` and `--rollback` both call `_require`, which raises `CommandError` while `EXECUTION_ENABLED` is false, before a write transaction is opened (lines 1169–1175). This revision did not change those constants and did not enable either mode.

`apply_blockers` also records `EXECUTION_DISABLED_IN_CODE`, `ANOMALY_REGISTRY_NOT_OWNER_APPROVED`, and `NO_AUTHORIZED_APPROVAL_RECORDED` when those constants stay at the values above (lines 743–750). A preview blocker is a report field. It is not a signature and it is not an execution authorization.

## 3. What the write path actually does

### 3.1 Transaction entry

`write_transaction` (`correct_imported_order_amounts.py` lines 355–373):

1. Refuses a non-PostgreSQL vendor.
2. Refuses an existing `connection.in_atomic_block`.
3. Enters `transaction.atomic(using=using)` with Django defaults `savepoint=True`, `durable=False`.
4. First statements inside that block: `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ`, then `SELECT pg_try_advisory_xact_lock(%s)` with `ADVISORY_LOCK_KEY`.
5. Calls `check_identity(expected_identity, database_identity(using))` on that same wrapper.
6. Yields to the body (`_execute` or `_restore`).

There is no `SELECT pg_backend_pid()`, no `pg_current_xact_id()` / `txid_current()`, no `pg_is_in_recovery()`, and no comparison of the driver connection object before and after the body.

`database_identity` (lines 376–396) reads `current_database()`, `pg_database.oid`, `server_version_num`, and `cluster_name` on the current wrapper. It then opens a **nested** `transaction.atomic()` and reads `system_identifier` from `pg_control_system()`. A `DatabaseError` there stores `system_identifier = None`. `check_identity` later refuses a missing required field. The nested block is a savepoint when an outer atomic block is already active.

`IDENTITY_COMPARED` is `database_name`, `database_oid`, `system_identifier`, `server_version_num`, `cluster_name` (lines 93–94). Host, port, backend PID, recovery state, and driver-connection identity are not part of the check.

### 3.2 Outcome classification

`_run_write` (lines 1193–1202):

- Sets `body_done = True` only after `body()` returns, still inside `write_transaction`.
- On any `BaseException`, returns `COMMIT_UNKNOWN` if `body_done` else `ROLLED_BACK`.
- If the `with` block ends without an exception, returns `COMMITTED`.

No transaction id is stored. No post-commit query runs. `_finish` (lines 1204–1220) appends `RUN_<outcome>` or `ROLLBACK_<outcome>` and, when an exception was captured, raises `CommandError`. The success message "corrections committed" is printed only when `exc is None` (line 1279). That means Django's `Atomic.__exit__` returned without raising. It does not mean a recorded xid was later observed as committed.

### 3.3 Body

`_execute` (lines 1281–1293): `SELECT … FOR UPDATE NOWAIT` in chunks of 1000, payment-table existence via `introspection.table_names()`, payment-row existence, per-row `QuerySet.update(total_price=...)` compare-and-set, then a sum check. `_restore` is the same shape with the before/after values swapped (lines 1352–1362).

The update uses `QuerySet.update`, not `Model.save`. Django does not apply `auto_now` on `QuerySet.update`, and this command does not write `datetime_modified`, `is_paid`, or `status`. A database trigger, rule, or row-level-security policy could still have side effects. No `RunSQL`, `CREATE TRIGGER`, `CREATE RULE`, or `ROW LEVEL SECURITY` statement was found in the repository's Python migrations. Absence from migration source does not prove the live catalog has no trigger. That catalog fact is **NOT VERIFIED**.

### 3.4 Audit file

`Outputs.write` (lines 316–320) writes bytes, `flush()`, then `os.fsync` on that file descriptor. It does not fsync the parent directory. Records are appended CSV lines without a per-record checksum. The exclusive create is `open('xb')` (line 310).

Apply writes `INTENDED` rows and `RUN_STARTED` **before** `_run_write` (line 1276). The final marker is written after `_run_write` returns. If the process stops between those two writes, a well-formed file can end at `RUN_STARTED`.

## 4. Django 6.0.2 transaction exit (installed source)

File: `django/db/transaction.py` in Django 6.0.2. `Atomic.__exit__` is lines 224–313.

Observed control flow for an outermost block (`savepoint_ids` empty):

1. `atomic_blocks.pop()` if `in_atomic_block`.
2. `in_atomic_block` is set to `False` **before** commit or rollback (lines 232–234). `DatabaseWrapper.commit` and `rollback` both call `validate_no_atomic_block()`, so this ordering is required for those calls to proceed.
3. If `connection.closed_in_transaction` is already true, the method does not commit and does not roll back (lines 237–240).
4. If there is no body exception and `needs_rollback` is false, it calls `connection.commit()` (line 263). On `DatabaseError` it tries `connection.rollback()`; on a further `Error` it calls `connection.close()`; then it re-raises the commit error (lines 264–271).
5. Otherwise it tries `connection.rollback()` (line 295). On `Error` it calls `connection.close()` and **does not re-raise** (lines 296–299). The original body exception then propagates, because `__exit__` returns a falsy value.
6. The `finally` block (lines 301–313), when the outermost block was entered from autocommit, either sets `connection.connection = None` if `closed_in_transaction`, or calls `connection.set_autocommit(True)`.

`set_autocommit(True)` after a successful `commit()` is what runs commit hooks (`base.py` lines 482–492). An exception from `set_autocommit` leaves the `with` statement as a failure even when `commit()` already returned. In `_run_write` that failure is `COMMIT_UNKNOWN` when `body_done` is already true. A failure raised from `finally` also replaces an exception raised in the `try` (the original remains on `__context__`). `_describe` reports only the exception object `_run_write` caught.

`DatabaseWrapper.close` (`base.py` lines 344–361): during an atomic block it sets `closed_in_transaction = True` and `needs_rollback = True`, and it does **not** clear `self.connection` on the non-pool path. `Atomic.__exit__`'s `finally` later assigns `connection.connection = None` when `closed_in_transaction` is set.

`DatabaseWrapper.connect` (`base.py` lines 237–259) replaces `self.connection`, then clears `in_atomic_block`, `savepoint_ids`, `atomic_blocks`, `needs_rollback`, `closed_in_transaction`, and `errors_occurred`. The new driver connection does not receive the old session's backend PID or transaction id. The same Django wrapper object is reused.

`ensure_connection` (lines 271–279) refuses to open a connection when `in_atomic_block and closed_in_transaction` (`ProgrammingError`: "Cannot open a new connection in an atomic block."). If `self.connection is None` while `in_atomic_block` is true and `closed_in_transaction` is false, `connect()` **would** open a new session and would reset atomic flags. The PostgreSQL pool `_close` sets `self.connection = None` before `close()`'s `finally` sets `closed_in_transaction` (`postgresql/base.py` lines 382–396). Current settings do not enable that pool (section 6).

`DatabaseErrorWrapper.__exit__` (`django/db/utils.py` lines 73–94) sets `errors_occurred` for every wrapped backend error except `DataError` and `IntegrityError`. That flag does not record whether `COMMIT` was acknowledged.

PostgreSQL `is_usable` (`postgresql/base.py` lines 486–496) runs `SELECT 1` on the driver cursor. A successful `SELECT 1` means the driver accepted a new statement. It does not identify an earlier transaction.

## 5. Driver and server boundary

`DatabaseWrapper._commit` calls `self.connection.commit()` (`base.py` lines 300–303), which for this pin is psycopg2 2.9.11. Django does not send `PREPARE TRANSACTION`. psycopg2's `commit()` is a single libpq `COMMIT`. This revision did not inspect libpq's network state machine beyond that call. A lost acknowledgement after the server has executed `COMMIT` is a known PostgreSQL client ambiguity: the driver raises, and the caller cannot see `CommandComplete`.

`txid_status(xid)` is the catalog function that can later report `committed`, `aborted`, or `in progress` for an xid on that cluster. It can also return NULL when the commit log no longer has that xid, or when the xid is not a transaction id of this cluster. The command never calls it. NULL must not be treated as either committed or aborted.

`pg_control_system().system_identifier` is a cluster identity, copied to physical replicas. A promoted standby keeps it. The command does not read `pg_is_in_recovery()`.

## 6. Database configuration present in the repository

`config/settings.py` lines 117–126:

- Engine `django.db.backends.postgresql`.
- Name, user, password, host, and port come from environment variables.
- Defaults written in source: database `postgres`, user `postgres`, password `postgres`, host `db`, port `5432`.
- No `OPTIONS`, no `CONN_MAX_AGE`, no `CONN_HEALTH_CHECKS`, no `assume_role`, no `ATOMIC_REQUESTS`.

Django therefore uses its defaults on this settings module: autocommit on, `CONN_MAX_AGE` 0, health checks off, no psycopg pool (`pool` is unset, so `DatabaseWrapper.pool` is `None`). `CONN_MAX_AGE` 0 still sets `close_at` to "now" at connect time; `close_if_unusable_or_obsolete` is not called by the correction command between statements. This revision did not observe a live `close_old_connections` during a run.

`config/settings_production.py` does not replace `DATABASES`. `docker-compose.prod.yml` starts the web container with `python manage.py migrate --noinput` and the official `postgres:16` image. That image creates `POSTGRES_USER` as a superuser. Whether any deployed server still matches this compose file is **NOT VERIFIED**.

`config/settings_isolated_test.py` refuses hosts `db`, `books-db-1`, `localhost`, `127.0.0.1`, `::1`, and `host.docker.internal`, and forces `KASRA_TEST_DB_*`. `config/test_runner.py` checks `cluster_name == kasra_p0_2_disposable`, refuses a superuser, and reads `system_identifier` before creating `test_kasra_p0_2`. Those checks run only if that test runner is invoked. It was not invoked for this revision.

`docker-compose.yml` publishes PostgreSQL on port 5432 and uses user `postgres` / password `postgres`. That is a development description, not a least-privilege design.

## 7. Authorization and artifacts present in source

`load_approval` (lines 848–896) accepts a JSON file whose SHA-256 equals `--approval-sha256` **and** whose digest is a key in `AUTHORIZED_APPROVALS`, mapping to the same `approval_ref`. The code comment on lines 78–79 states that the hash proves integrity, not authorisation, and that the registry is filled by a reviewed code change.

The approval object must contain exactly: `format`, `approval_ref`, `before_state_sha256`, `preview_sha256`, `rules`, `currency_factors`, `classification_policy_sha256`, `wholesale_threshold_toman`, `anomaly_wordpress_ids`, `database_identity`, `imported_orders_fingerprint_sha256`.

Not present in that object or in the checker: signature, trusted key id, nonce, operator, approver, execution role, repository commit, source-tree manifest, lockfile hash, image digest, `not_before` / `not_after`, revocation handle, or a one-time consumption record.

No source-tree hash, `*.py` hash, or image digest is computed anywhere in the command. `classification_policy()` hashes the in-process policy dict (lines 273–289), including the anomaly id list and the factors from `core.money.TOMAN_PER_UNIT`. That hash changes when those Python values change. It does not cover `requirements.txt`, Dockerfiles, or the rest of the tree.

`FACTOR_STATUS` is the literal `PROVISIONAL_UNAPPROVED`.

## 8. Rollback acceptance

`load_execution_report` (lines 946–952) rejects a marker pair of `RUN_STARTED` + `RUN_ROLLED_BACK`. It accepts:

- markers ending at `RUN_STARTED` only;
- `RUN_STARTED` + `RUN_COMMITTED`;
- `RUN_STARTED` + `RUN_COMMIT_UNKNOWN`.

`RUN_FINAL_STATUSES` is `('RUN_COMMITTED', 'RUN_COMMIT_UNKNOWN')` (line 918).

`_rollback` (lines 1308–1350) then classifies current rows. Any problem (`DB_ORDER_MISSING`, `DB_WORDPRESS_ID_CHANGED`, `DB_IS_PAID_CHANGED`, `DB_PAYMENT_PRESENT`, `DB_TOTAL_CHANGED`) or a mix of corrected and original values raises before a write. If every target holds the original `total_price`, it writes `ROLLBACK_NOOP_ALREADY_RESTORED` and returns, including when the report status is `RUN_STARTED` or `RUN_COMMIT_UNKNOWN`. If every target holds the corrected value, it opens a write transaction even for those two statuses.

The same original approval file authorises rollback. There is no second signature, no fresh reconciliation document, and no rollback policy version.

Phase 3 plan section 10.6 says a report ending at `RUN_STARTED` is accepted and resolved from the database. Section 10.7 says incomplete reports are refused. The source matches section 10.6. Tests encode the same acceptance:

- `CommitOutcomeTest.test_commit_failure_is_reported_as_unknown_and_never_as_rolled_back` expects a later rollback to print `Nothing to roll back (RUN_COMMIT_UNKNOWN)` and then expects a **retry apply** to succeed.
- `CommitOutcomeTest.test_a_report_cut_off_after_run_started_is_resolved_from_the_database` expects a `RUN_STARTED` report to restore rows.

Those tests were not executed in this revision. Their source shows the behavior the current program is written to perform.

## 9. Historical test claims that this revision does not adopt

`audit_reports/P0_2_PHASE3_CORRECTION_PLAN.md` section 10.9 describes a disposable container `kasra-p0-2-disposable-pg`, PostgreSQL `server_version_num` 160015, and a non-superuser role. Section 11 says 332 tests ran with two unrelated locale failures, and that correction tests passed.

No test log, JUnit file, or CI workflow is in the repository (no `.github` workflow files). This revision did not re-run that suite and did not attach to that container. Those sentences remain unverified historical assertions. They are not evidence that any Revision 7 test passed.

Section 10.11 also says the correction code is uncommitted. At inspection, the command, tests, and Phase 3 plan are tracked at `2c3b9fd`. Being committed is not independent review and is not execution approval.

## 10. Importer interaction present in source

`import_wordpress_complete.py` takes a **session-level** `pg_try_advisory_lock` on the same `ADVISORY_LOCK_KEY` for the order import. The correction command takes a **transaction-level** `pg_try_advisory_xact_lock` on that key. Advisory locks are re-entrant for the same session. The transaction lock ends at commit or rollback. It does not cover the gap between snapshot and apply.

## 11. Items inspected and deliberately not treated as live proof

| Question | Result of static inspection |
| --- | --- |
| Does a read-only role exist on a server? | **NOT VERIFIED**. No role SQL and no catalog dump are in the tree. |
| Does an execution role exist? | **NOT VERIFIED**. None is defined in source. |
| Effective privileges, RLS, triggers, pooler, `SELECT FOR UPDATE` under a restricted grant | **NOT VERIFIED**. |
| Whether `pg_control_system()` is executable by a future non-superuser | **NOT VERIFIED** on any target. The command fail-closes if the value is missing. |
| Durable storage behavior of `os.fsync` on the operator's filesystem | **NOT VERIFIED**. |
| Image digest of any built container | **NOT VERIFIED**. Dockerfiles use mutable tags (`python:3.14.3`, `python:3.14-slim`, `postgres:16`). |
| Contents of `.env` / `.env.prod` | Not read. Live secrets and live role names are **NOT VERIFIED**. |
