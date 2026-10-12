# Kasra order-correction plan — Revision 7

Status: **NO-GO**.

This document is a planning and static-review revision. It does not approve a data change, a role change, a backup, a deployment, or a test run. `EXECUTION_ENABLED` stays `False`. `APPROVED_ANOMALY_WORDPRESS_IDS` stays empty. `AUTHORIZED_APPROVALS` stays empty. No gate in section 11 is satisfied.

Companion evidence note: `audit_reports/KASRA_ORDER_CORRECTION_REV7_STATIC_FINDINGS.md`. Where this plan specifies a future mechanism, that mechanism is **NOT IMPLEMENTED** unless the findings note shows the current source already doing it.

## 1. Executive summary

The repository at `2c3b9fde70fc7ff3e5b5f7a72bdcb111b9d74d03` contains a disabled correction command, tests, and a Phase 3 plan. Revision 6 is not in the tree. The open safety issues named for this revision were checked against that source.

The command will not write while `EXECUTION_ENABLED` is false. If that flag were turned on, the current design would still be insufficient for a production change:

- `COMMITTED` means Django 6.0.2 left `transaction.atomic()` without raising. The program does not record a transaction id, does not confirm `txid_status`, and does not notice if the driver connection was replaced.
- `ROLLED_BACK` means an exception was raised before the body set `body_done`. Django can swallow a failed `ROLLBACK` and still present the body exception. A lost session is not, by itself, proof that `COMMIT` never reached the server.
- The on-disk report can end at `RUN_STARTED` or `RUN_COMMIT_UNKNOWN`. Rollback accepts both and will either no-op or issue further writes from row contents. Row contents on a later connection do not identify the original transaction.
- Authorization is a SHA-256 allowlist in source code beside a JSON file. That binds bytes to a string in the same codebase. It does not authenticate an approver, a nonce, a window, a revocation, a commit, or an image.
- No source-tree identity, lockfile identity, or image digest exists. `requirements.txt` is pinned without hashes. Container tags are mutable. Reproducibility is **not** established.
- No read-only role and no execution role are defined. Development and production compose files describe the application login as the PostgreSQL bootstrap user, and the production web command runs `migrate` with that login. Creating a writable login before the later gates would open an unapproved write path.
- Every future test in section 10 is **NOT EXECUTED**. Historical test sentences in the Phase 3 plan have no retained log in this repository and were not repeated.

Further writes after any uncertain transaction result are forbidden until that result is resolved from transaction-id evidence or the run is halted for restore. An owner instruction to continue is not that evidence.

## 2. Revision 6 findings and disposition

No Revision 6 file is tracked at HEAD. The findings below are the unresolved issues this revision was required to close in the plan. "Disposition" means how Revision 7 classifies them. It does not mean the code was changed.

| ID | Unresolved issue | What static inspection found | Revision 7 disposition |
| --- | --- | --- | --- |
| F1 | Transaction outcome is inferred from exceptions and from `atomic()` returning | Confirmed. `_run_write` has no xid and no post-commit proof. | Required evidence is specified in sections 4 and 5. **NOT IMPLEMENTED**. |
| F2 | Connection replacement can inherit old verification | Confirmed as a gap. Django `connect()` clears wrapper transaction flags and installs a new driver connection. The command keeps Python dicts from the old session. | A new connection must not reuse old verification. Section 4. **NOT IMPLEMENTED**. |
| F3 | `COMMITTED` / `ROLLED_BACK` / `COMMIT_UNKNOWN` evidence is weaker than the safety bar | Confirmed. Success is "no exception". Rollback of the database is not required to have been acknowledged. | Section 5. Current labels do not meet the bar. **NOT IMPLEMENTED**. |
| F4 | Audit durability is a single file `fsync` | Confirmed. `flush` + `os.fsync` on the file only. No directory fsync, no per-record checksum, no halt latch. | Section 5. `fsync` is not claimed to be universal durability. **NOT IMPLEMENTED** beyond the current file fsync. |
| F5 | Hashing an approval file is treated as authorization | Confirmed. `AUTHORIZED_APPROVALS` maps a digest to `approval_ref`. | Section 6. Cryptographic authorization is **NOT IMPLEMENTED**. |
| F6 | Artifact identity omits behavior-affecting inputs | No `*.py` hash exists either. Policy hash covers only the in-memory policy dict. Dependencies, Dockerfiles, and image digest are unbound. | Section 7. **NOT IMPLEMENTED**. Reproducible build: **NOT VERIFIED** and not claimed. |
| F7 | Read-only and execution roles are not proven least privilege | No role definition, grant script, or catalog evidence is in the tree. Compose files point the app at the bootstrap user and run migrations on start. | Section 8 checklist. Live privileges **NOT VERIFIED**. |
| F8 | An execution role created before approval can write | No such role is in source. The lifecycle that would prevent early use is also absent. | Section 9. Do not create the role in this revision. **NOT IMPLEMENTED**. |
| F9 | Rollback accepts `RUN_STARTED` and `RUN_COMMIT_UNKNOWN` and shares the forward approval | Confirmed in `load_execution_report` and `_rollback`, and encoded in tests. | Section 10. Those reports must not authorize a rollback write. Separate rollback authorization is **NOT IMPLEMENTED**. |
| F10 | Tests do not cover the failure modes in the task | The named scenarios are absent or, where a nearby test exists, it asserts the weaker current behavior. None were run. | Section 11. All **NOT EXECUTED**. |
| F11 | Passing review or tests could be mistaken for execution approval | Phase 3 gates G5/G6 were already "implemented and tested" while status stayed NO-GO. Those test claims are not re-verified here. | Section 12. Code review and tests never satisfy the execution gate. |

Phase 3 statements that this revision does not carry forward as facts:

- "The code is uncommitted." The correction files are tracked at `2c3b9fd`. That fact does not close review or execution.
- "332 tests ran … correction tests passed." No log is in the tree. **NOT RE-VERIFIED**.
- "Tampered, ambiguous or incomplete reports are refused." Files that end at `RUN_STARTED` or `RUN_COMMIT_UNKNOWN` are accepted. The source and Phase 3 section 10.6 agree with each other and disagree with that sentence.
- Disposable PostgreSQL `server_version_num` 160015 and "the same major version as `books-db-1`." **NOT VERIFIED** in this revision. No database was contacted.

## 3. Scope and safety constraints observed

This revision authorizes documentation only. The work performed stayed inside these limits:

- No connection to a development, production, or disposable database.
- No importer, correction, rollback, migration, or deployment command.
- No test run.
- No role, grant, password, allowlist, or snapshot.
- No commit, merge, or runtime change.
- Execution and rollback flags were left disabled.

Anything that can be known only by querying a server or running the suite is marked **NOT VERIFIED**, with a future procedure that stays on an isolated disposable cluster.

## 4. Transaction lifecycle (Django 6.0.2, psycopg2 2.9.11)

Versions are the pins in `requirements.txt` and the copies installed in the local virtualenv. The PostgreSQL **server** version that would receive a future command is **NOT VERIFIED**. Compose names `postgres:16` by tag.

Five different objects must stay distinct:

| Object | What it is | What the current command stores |
| --- | --- | --- |
| Django database wrapper | `connections[alias]`, a process-local `DatabaseWrapper` | Used implicitly. The same object is reused after reconnect. |
| Driver connection | `wrapper.connection`, a psycopg2 connection | Not recorded. |
| PostgreSQL backend PID | `pg_backend_pid()` for one session on one postmaster | Not queried. |
| Transaction id | `pg_current_xact_id()` inside the open transaction | Not queried. |
| Cluster identity | `system_identifier`, plus database oid | Read into a dict. Not tied to PID or driver object. Not re-checked after commit. |

A verification result belongs to the driver connection and backend PID that produced it. `DatabaseWrapper.connect()` installs a new driver connection and clears the wrapper's atomic flags, savepoints, `needs_rollback`, and `closed_in_transaction`. It does not copy the old PID or xid onto the new session. Python variables in the command (`progress`, `identity`, approval dicts) survive that replacement. They are process memory, not session state. Future code must drop them when `id(wrapper.connection)` or the backend PID changes. Reusing them on the new session is a silent inheritance bug. That guard is **NOT IMPLEMENTED**.

### 4.1 Acquisition and initial identity check

Snapshot and preview call `read_only`, which requires the wrapper not already be in an atomic block, then opens `transaction.atomic()` and, on PostgreSQL, runs `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY` as the first statement. `database_identity()` runs inside that transaction. The `system_identifier` read sits in a nested atomic block (a savepoint).

Apply and rollback repeat a read-only pass that also runs `check_schema` (migration executor) and `check_identity` before the write. The write later calls `database_identity()` again inside `write_transaction`. That second read is a new observation on whatever session is connected at `SET TRANSACTION` time. It does not prove the session is still the one that produced the earlier preview.

`check_identity` compares name, oid, `system_identifier`, `server_version_num`, and `cluster_name`. A physical replica and a promoted standby share `system_identifier` with the primary they were copied from. The command never reads `pg_is_in_recovery()`. Host and port are not bound. An endpoint change to another member of the same cluster can pass this check. Detecting that is **NOT IMPLEMENTED**.

### 4.2 Entry into `transaction.atomic()`

`write_transaction` uses `transaction.atomic(using=using)` (defaults: `savepoint=True`, `durable=False`). For an outermost block entered while autocommit is on, Django 6.0.2 `Atomic.__enter__`:

- sets `commit_on_exit = True` and `needs_rollback = False`;
- calls `set_autocommit(False, force_begin_transaction_with_broken_autocommit=True)`.

On the PostgreSQL backend, `force_begin_transaction_with_broken_autocommit` does not emit SQLite's extra `BEGIN`. `_set_autocommit(False)` assigns `connection.autocommit = False` on the psycopg2 connection, which starts a transaction at the next statement. `set_autocommit` calls `ensure_connection()` first, so a wrapper with `connection is None` connects here, **before** `in_atomic_block` is set.

Settings leave `AUTOCOMMIT` at the Django default (true), do not set a pool, and do not set `assume_role`. `init_connection_state` may `SET TIME ZONE` and will issue an extra driver `commit()` only when autocommit is already off. With the default autocommit setting, that extra commit is skipped. This is a reading of Django 6.0.2 `postgresql/base.py` `init_connection_state`. It was not executed.

### 4.3 Transaction-state validation

Inside the block the command checks three things only: vendor is PostgreSQL, `pg_try_advisory_xact_lock` returned true, and `check_identity` passed. It does not assert `wrapper.connection` is still the object acquired at enter, does not read `pg_backend_pid()`, and does not assert `in_atomic_block` stays true for the body. `durable=True` is not used, so a nested atomic block does not raise. `database_identity` intentionally opens one.

Required future check, **NOT IMPLEMENTED**: capture `(driver_id, backend_pid, cluster identity, database oid, pg_is_in_recovery() = false)` immediately after the lock and again before `COMMIT` is sent. Any difference aborts the attempt to classify the outcome as `COMMITTED`. If `COMMIT` might already have been sent, the class is `COMMIT_UNKNOWN`.

### 4.4 Transaction id and durable recording

**NOT IMPLEMENTED.** The required order is:

1. Perform the correction body.
2. On that same driver connection, read `pg_current_xact_id()` and `pg_backend_pid()`.
3. Durably record a `PRE_COMMIT` audit event containing that xid, PID, cluster identity, database oid, batch id, and the hash of the intended row set. `COMMIT` is not sent if this record is not durable.
4. Send `COMMIT` only after that record is durable.
5. Classify using section 5.
6. Durably record the terminal classification. If that write fails, the xid record from step 3 is what recovery uses. The process still exits as a halt if the terminal record cannot be made durable.

`pg_current_xact_id()` assigns an xid if the transaction does not yet have one. Calling it before the body would also work, but the id must be the id of the transaction that contains the updates. A second transaction's id must not be written into the first transaction's record.

### 4.5 Correction body

`_execute` / `_restore` lock target rows with `SELECT … FOR UPDATE NOWAIT`, recheck payments, compare-and-set `total_price`, and check the sum. Any exception before `body()` returns leaves `body_done` false. The updates are uncommitted until Django commits in `__exit__`. A failure of a middle `UPDATE` does not by itself prove the server will abort; proof is a successful `ROLLBACK` acknowledgement or `txid_status = aborted` (section 5).

`QuerySet.update` does not run `Model.save` and does not refresh `auto_now` fields in Django. Catalog triggers remain **NOT VERIFIED**.

### 4.6 `Atomic.__exit__` in Django 6.0.2

For this outermost block the installed `Atomic.__exit__` does the following. Line numbers refer to `django/db/transaction.py` in Django 6.0.2.

1. Pops `atomic_blocks` while `in_atomic_block` is still true (lines 227–228).
2. Sees an empty `savepoint_ids` and sets `in_atomic_block = False` **before** commit or rollback (lines 232–234).
3. If `closed_in_transaction` is already true, it neither commits nor rolls back (lines 237–240). The comment in Django says the database will roll the transaction back itself. That describes a backend session that dies before processing `COMMIT`. It is not a proof when the acknowledgement of `COMMIT` was lost, and it is not a proof when a pooler keeps the server session. Current settings do not enable Django's pool. An external pooler is **NOT VERIFIED**.
4. If the body raised no exception and `needs_rollback` is false, it calls `wrapper.commit()` → psycopg2 `connection.commit()` (lines 260–263).
5. If that raises `DatabaseError`, it tries `rollback()`. If rollback raises `Error`, it `close()`s and then re-raises the **commit** error (lines 264–271).
6. If the body raised, or `needs_rollback` is true, it tries `rollback()` (lines 292–295). If rollback raises `Error`, it `close()`s and does **not** re-raise (lines 296–299). `__exit__` then returns false, and Python propagates the original body exception. The failed rollback is discarded unless `close()` itself raises.
7. `finally` (lines 301–307): if `closed_in_transaction`, it sets `wrapper.connection = None`. Otherwise it calls `set_autocommit(True)`, which runs commit hooks after a successful commit.

### 4.7 Commit, rollback, close, cleanup, and masking

| Event | What Django 6.0.2 does | What `_run_write` records today | What Revision 7 requires |
| --- | --- | --- | --- |
| `commit()` returns and `set_autocommit(True)` returns | Normal success path | `COMMITTED` | `COMMITTED` only with the evidence in section 5, including a durable xid record |
| `commit()` returns, then `set_autocommit(True)` raises | `finally` raises. The transaction was acknowledged if `commit()` returned on that same connection. | `COMMIT_UNKNOWN` because `body_done` is true | Stay `COMMIT_UNKNOWN` until `txid_status` confirms the recorded xid. Do not issue more writes. |
| `commit()` raises, `rollback()` returns | Commit error is re-raised. A live session that accepts `ROLLBACK` still had a transaction open or aborted, which is evidence `COMMIT` did not complete on **that** session. A dead socket is a different case. | `COMMIT_UNKNOWN` | `COMMIT_UNKNOWN` until `txid_status` on the recorded xid is `aborted` or `committed`. A rollback acknowledgement on the same PID may support `ROLLED_BACK` only together with that status or with proof `COMMIT` was never sent. |
| `commit()` raises, `rollback()` raises, `close()` returns | Commit error is re-raised. Driver connection is closed. | `COMMIT_UNKNOWN` | `COMMIT_UNKNOWN`. Halt. |
| `commit()` raises, `close()` raises | The `close()` error replaces the commit error. The commit error remains on `__context__`. | `COMMIT_UNKNOWN`, described from the outer exception only | `COMMIT_UNKNOWN`. Future logs must keep both exceptions. **NOT IMPLEMENTED**. |
| Body raises, `rollback()` returns on the same connection | Body exception propagates | `ROLLED_BACK` | `ROLLED_BACK` only if section 5's abort evidence holds |
| Body raises, `rollback()` fails, `close()` returns | Body exception propagates. Rollback failure is hidden. | `ROLLED_BACK` | `COMMIT_UNKNOWN` if the session is gone or `COMMIT` may have been sent. The current label is **not** sufficient. |
| Body raises, `close()` raises | `close()` masks the body exception | `ROLLED_BACK` if `body_done` is false, described from the outer exception | `COMMIT_UNKNOWN` unless abort evidence exists |
| `closed_in_transaction` already set | No commit and no rollback attempted | Whatever exception escapes; class follows `body_done` | `COMMIT_UNKNOWN` unless a recorded xid resolves |
| Process killed after `commit()` acknowledgement and before the terminal marker | No Python classification | File can end at `RUN_STARTED` | Recovery uses the durable xid. Until then, `COMMIT_UNKNOWN` and halt. |

`DatabaseErrorWrapper` sets `errors_occurred` for operational and interface failures. The correction command never reads that flag. `is_usable()`'s `SELECT 1` is not an outcome probe.

### 4.8 Connection replacement and reconnection

Replacement is visible as a new `wrapper.connection` or a new `pg_backend_pid()`.

Paths present in Django 6.0.2:

- `Atomic.__exit__` sets `wrapper.connection = None` when `closed_in_transaction` is set. The next `ensure_connection()` calls `connect()`.
- `connect()` resets atomic state on the wrapper and opens a new psycopg2 connection with a new backend PID.
- `ensure_connection` raises `ProgrammingError` if a new connection is requested while `in_atomic_block and closed_in_transaction`. It will connect if the driver pointer is already `None` and `closed_in_transaction` is still false. The psycopg pool `_close` nulls the pointer before that flag is set. The pool is off in current settings. Turning `OPTIONS['pool']` on would change this path. That configuration is not authorized.
- `close_if_health_check_failed` can close a connection when health checks are enabled. They are off in `config/settings.py`. `close_if_unusable_or_obsolete` can close when `errors_occurred` is set or `CONN_MAX_AGE` has elapsed. The command does not call it between statements. `CONN_MAX_AGE` is unset (Django default 0).

Required rule: after any replacement, discard identity checks, PIDs, and xids taken from the old session. Do not run a "confirmation" query on the new session and treat success, or a matching `total_price`, as the fate of the old xid. The new session may be used only as a **new** session whose own cluster identity has been read again, and only to call `txid_status` for an xid that was durably recorded earlier, on a primary (`pg_is_in_recovery()` false) of that same `system_identifier` and database oid.

### 4.9 Post-transaction verification

The command runs none. `_finish` only writes the CSV marker.

Queries that can establish the original transaction's outcome:

- `txid_status(recorded_xid)` on a session that has just been shown to be the primary of the same `system_identifier` and the same database oid. `committed` supports `COMMITTED`. `aborted` supports `ROLLED_BACK`. `in progress` means the session may still be open: halt, do not start a second writer, and do not classify yet.
- A row inserted in that same transaction, found on that primary, **together with** `txid_status(recorded_xid) = committed`. The row alone is not enough, because a later transaction can write the same business values.

Queries that leave the outcome unknown, even when they succeed:

- Any statement on a newly connected session that does not pass the primary and cluster checks above.
- `SELECT` of `orders.total_price` (values can be written by another transaction, restored later, or still unchanged on a replica).
- `SELECT 1`, a successful connect, or an idle advisory lock.
- `pg_control_system()` alone.
- The correction function returning, or the CSV containing `RUN_COMMITTED` without a bound xid.

`txid_status` NULL is `COMMIT_UNKNOWN`. Causes include a wrong cluster, an xid that was never assigned, or a commit-log horizon that no longer contains the xid. NULL is not success and not abort.

Prepared transactions: this command does not issue `PREPARE TRANSACTION`. If recovery finds the recorded xid still `in progress` and `pg_prepared_xacts` has a prepared transaction that could be this batch, the result stays `COMMIT_UNKNOWN` until that prepared transaction is resolved by a separately authorized procedure. Guessing `COMMIT PREPARED` or `ROLLBACK PREPARED` is out of scope and is not authorized.

Failover or an endpoint change between two connections is `COMMIT_UNKNOWN` when the recorded xid cannot be resolved on the re-identified primary. Reading the new endpoint's orders and continuing to write is forbidden.

Any uncertainty halts further correction and rollback writes.

## 5. Commit evidence and durable audit records

### 5.1 Minimum evidence

**`COMMITTED`** — all of the following:

1. A durable `PRE_COMMIT` record holds the xid taken from the transaction that performed the updates, plus backend PID, `system_identifier`, database oid, and batch hash.
2. psycopg2 `commit()` on **that same** driver connection returned without error (`CommandComplete` for `COMMIT`).
3. After that acknowledgement, `txid_status(xid)` on the re-identified primary is `committed`.
4. A durable terminal record stores that status, the xid, and the batch hash.

A return from the management command, a later `SELECT`, or a CSV line written without the xid does not satisfy this. If step 2 was observed but step 3 has not been done, the classification remains `COMMIT_UNKNOWN`.

**`ROLLED_BACK`** — `COMMIT` was not acknowledged, and one of these is true:

- `ROLLBACK` returned successfully on the same driver connection and the same backend PID, and either no xid had been assigned or `txid_status` for the recorded xid is `aborted`; or
- `COMMIT` was never sent, the backend PID is gone, no matching prepared transaction exists, and `txid_status` is `aborted` or the transaction never obtained an xid because the session died before assignment **and** the audit record shows `COMMIT` was not sent.

An exception class, a closed socket, or "the rows still show the old total" is not this evidence. Django's habit of hiding a failed `rollback()` makes exception text a poor witness. Connection loss during `commit()` is `COMMIT_UNKNOWN` even if the rows look unchanged: the acknowledgement may have been lost after the server committed, or a replica may be stale.

**`COMMIT_UNKNOWN`** — everything else, including:

- `commit()` raised;
- `commit()` succeeded and the process died before a durable terminal record, until `txid_status` is read;
- `txid_status` is NULL or `in progress`;
- the driver connection or PID changed and `COMMIT` may have been sent;
- rollback was not acknowledged;
- the audit record is truncated, missing, or internally inconsistent;
- the endpoint or recovery state does not match the recorded primary.

`COMMIT_UNKNOWN` stops every later apply and rollback write for that batch until an independent recovery procedure resolves the xid or a rehearsed restore is chosen. A new preview that "looks original" does not clear the halt. The current tests expect a retry apply after `RUN_COMMIT_UNKNOWN`. That retry is **not** acceptable under this plan. Changing the tests is **NOT IMPLEMENTED** and is not authorized as an execution step.

### 5.2 Audit record behavior

Required event order for a future writer (**NOT IMPLEMENTED**):

1. `RUN_AUTHORIZED` — authorization verified, no data change.
2. `RUN_STARTED` — file created, batch listed, no data change yet.
3. `PRE_COMMIT` — xid and session identity, durable before `COMMIT` is sent.
4. Terminal record — only after section 5.1 is applied: `COMMITTED`, `ROLLED_BACK`, or `COMMIT_UNKNOWN`.
5. `HALT` — written whenever the terminal class is `COMMIT_UNKNOWN` or the terminal record could not be finished. Later invocations of apply and rollback must refuse when a halt is present for this batch.

Current code writes `INTENDED` and `RUN_STARTED`, then one of `RUN_COMMITTED`, `RUN_ROLLED_BACK`, or `RUN_COMMIT_UNKNOWN`. There is no `PRE_COMMIT`, no xid, and no halt that the next process must honor. `Outputs.reserve` refuses an existing path, so a second run cannot overwrite the file. It also does not look at any other batch's halt file. A new path can be chosen and another write attempted. That is the gap.

Failure rules:

| Failure | Required behavior |
| --- | --- |
| Create fails (`O_EXCL` or directory missing) | No transaction. Current code already raises. |
| Write, flush, or fsync fails **before** the body | No `COMMIT`. Discard only if no `PRE_COMMIT` and no `COMMIT` was sent. |
| Write, flush, or fsync fails on `PRE_COMMIT` | Do not send `COMMIT`. Roll back only with an acknowledgement. Otherwise `COMMIT_UNKNOWN` is impossible for an unsent `COMMIT`; classify `ROLLED_BACK` only with section 5.1. If the session then dies without that evidence, halt as `COMMIT_UNKNOWN`. |
| Process killed after a durable `PRE_COMMIT` and before a terminal record | Recovery reads `txid_status`. No second writer. |
| Process killed after `commit()` returns and before the terminal fsync | Same recovery. Current files that stop at `RUN_STARTED` are this case **without** an xid, so they are `COMMIT_UNKNOWN`, not a license to restore from row values. |
| Torn or partial last record | The file is not a terminal success. Treat as `COMMIT_UNKNOWN` / halt. A CSV parser that stops at the last complete `RUN_STARTED` line must not start a write. |
| Duplicate invocation | Refuse unless a consumed nonce and the terminal record say the prior attempt is `ROLLED_BACK` or `NOOP` with section 5.1 evidence. Same approval cannot be replayed (section 6). |
| fsync returns | The kernel accepted the call for that file descriptor. This does not prove durability on every operating system, copy-on-write filesystem, network mount, hypervisor disk, or controller that acknowledges before media is stable. Directory entries also need a directory fsync after create or rename, which the current `Outputs.write` does not do. Windows `os.fsync` and a POSIX `fsync` are not the same guarantee. The plan does not claim otherwise. |

Recovery after an interrupted run is a read-only procedure on the disposable design first, then, only under later gates, on the target: re-identify the primary, call `txid_status` for a recorded xid, append a terminal record, and halt if the xid was never recorded. It is **NOT VERIFIED** and **NOT IMPLEMENTED**.

## 6. Authorization authenticity and artifact binding

### 6.1 Hash versus authentication

`load_approval` checks that the file bytes hash to a digest stored in `AUTHORIZED_APPROVALS` and that `approval_ref` matches the mapped string. That shows the file matches a value compiled into the source. Anyone who can change both the file and that dict, or who can deploy a different tree, can authorize a different batch. The hash is an integrity check of one blob. Authentication is a check that an identifiable approver accepted that blob under a trust anchor the operator cannot rewrite by editing the same file.

The current mechanism does not authenticate. It is **NOT IMPLEMENTED** as an authorization system. The empty registry correctly fail-closes apply and rollback while `EXECUTION_ENABLED` is also false. Emptiness is not a signature scheme.

### 6.2 Required authorization payload

Future apply authorization, **NOT IMPLEMENTED**, is a canonical payload plus a detached signature. The verifier accepts it only when every field below is present and matches live observations:

| Field | Bound to |
| --- | --- |
| `authorization_id` | Unique id |
| `nonce` | Single use; consumed durably before any data change |
| `operator` | Named operator identity |
| `approver` | Independent approver, different from the operator |
| `database_identity` | `system_identifier`, database oid, database name, and the approved endpoint identity |
| `execution_role` | Role name that will run the writes, which must be `NOLOGIN` until credential release |
| `policy_version` and `policy_sha256` | Exact classification policy |
| `rule` | One rule |
| `batch_id` and `order_id_set_sha256` | Exact anomaly/order id set for this batch |
| `before_state_sha256` | Before-state fingerprint |
| `preview_sha256` and `manifest_sha256` | Preview and manifest |
| `git_commit` | Commit that was reviewed |
| `source_tree_identity` | Section 7 |
| `build_identity` | Section 7, including lockfiles |
| `image_digest` | Section 7 |
| `not_before`, `not_after` | Execution window |
| `revocation_generation` | Generation of the revocation list that was current when signed |

A hash stored next to a mutable JSON file does not meet this list. Putting the same digest in `AUTHORIZED_APPROVALS` does not meet it either.

### 6.3 Trust anchor

The signature is verified with a public key (or an equivalent independent trust mechanism such as a hardware-backed approval service) whose identity is held outside the authorization file. The trust anchor is recorded by a security owner in a location the correction operator cannot update as part of preparing the JSON. Verification steps:

1. Canonicalize the payload.
2. Check the signature with the trusted public key. A wrong key, a truncated signature, or a payload that does not canonicalize is a refusal.
3. Check key id and algorithm against the trust anchor.
4. Load a separately signed revocation list. If `authorization_id` is revoked, or the list is missing, stale, or unsigned, refuse.
5. Check wall-clock time against `not_before` and `not_after`. Refuse outside the window.
6. Refuse if the nonce appears in the durable consumed-nonce ledger.
7. Compare payload database identity, role, policy, batch, before-state, preview, manifest, commit, source-tree identity, build identity, and image digest to freshly measured values. Any mismatch refuses.
8. Only then append the nonce to the ledger and fsync it. If that append fails, refuse and do not write business data. A nonce that might have been written and not fsynced is treated as consumed.

No key, signature format, or ledger is implemented. Key ceremony, algorithm choice, and where the trust anchor lives require security-owner approval (section 13). This revision does not generate a key.

### 6.4 Replay, expiry, revocation, and substitution

- **Replay:** the nonce ledger rejects a second use even if the signature is still valid and the window has not ended.
- **Expiry:** `not_after` is enforced at the start of apply and again immediately before `COMMIT`. A window that expires after `PRE_COMMIT` and before `COMMIT` stops the send and follows section 5.
- **Revocation:** checked at both of those times against the signed list. A bit inside the authorization file is not a revocation status.
- **Batch swap:** `batch_id`, `order_id_set_sha256`, `rule`, and `preview_sha256` are inside the signature. Substituting another preview fails the signature or the live hash compare.
- **Database swap:** signed `system_identifier`, database oid, and endpoint identity must match the session just connected. A replica with the same `system_identifier` fails the `pg_is_in_recovery()` check.
- **Artifact swap:** source-tree identity, build identity, and image digest are inside the signature and re-measured.
- **Window swap:** timestamps are inside the signature. Editing them invalidates the signature.

Rollback uses a **second** payload (section 10), not this apply payload.

## 7. Complete artifact identity

### 7.1 What exists now

The command hashes the before-state CSV, the preview CSV, the approval file, the execution report, the export file, and the classification-policy JSON. It does not hash the source tree. A `*.py`-only hash is also absent, so the question of whether that hash is too narrow starts from "there is no such control," not from a control that merely misses a few files.

If a `*.py`-only hash were added, it would still omit inputs that change behavior without a Python edit:

- `requirements.txt` (Django and psycopg2 pins; no `--hash` lines, so the same pin can install different artifacts if an index is substituted).
- Dockerfiles and compose files (base image tags, `apt` packages, the production `migrate` command).
- `nginx` configuration shipped in the production compose context.
- Any future `.sql` file. None are in the tree today.
- The built image's package set and the mutable tag `python:3.14-slim` / `python:3.14.3` / `postgres:16`.

Python files that **do** affect the correction and would need to be inside any honest source identity include `correct_imported_order_amounts.py`, `audit_imported_order_amounts.py`, `import_wordpress_complete.py`, `core/money.py`, `orders/models.py`, `payment/models.py`, the `orders` and `payment` migrations, and `config/settings.py`. Templates are not imported by the command. They still change a `COPY .` image. They belong to image identity, not to the command's logic hash.

### 7.2 Four identities

| Identity | Contents | How it is verified | State |
| --- | --- | --- | --- |
| Source-tree identity | Canonical manifest (path, file mode, content sha256) of the workflow files listed above, plus settings and migrations. Git commit id is recorded only when `git status` is clean and `HEAD` tree matches the manifest. | Recompute the manifest from the tree that will be built. Compare to the signed payload. | **NOT IMPLEMENTED**. This revision's HEAD is recorded in the findings note, which is a point-in-time observation, not a signed identity. |
| Build identity | Source-tree identity plus `requirements.txt` content hash, Dockerfile and compose hashes, and build arguments. A lockfile with artifact hashes would be required before this identity can be called reproducible. | Rebuild in an isolated builder and compare. | **NOT IMPLEMENTED**. No lockfile is in the tree. Reproducibility is **not** claimed. |
| Image identity | Registry digest `sha256:…` of the image that will execute the command, not the tag. | The runner prints the digest it is actually executing. The approver's payload must equal that digest. | **NOT IMPLEMENTED** and **NOT VERIFIED**. No image was built. |
| Authorization identity | Signature over section 6, which includes the three identities above. | Section 6.3. | **NOT IMPLEMENTED**. |

These four are not substitutes for each other. A matching git commit with a dirty tree fails source-tree identity. A matching source tree built from an unpinned base image fails image identity. A matching image without a valid signature fails authorization identity.

## 8. Database privilege model

`default_transaction_read_only=on` is defense in depth. It is not the access-control boundary. In PostgreSQL that parameter is user-settable: a session can turn it off. Superuser is not required. The boundary is the absence of write grants, the absence of role membership that inherits write grants, and `NOLOGIN` until credential release.

No Stage 1 role and no execution role exist in source. The checklist below is the static review that must be completed on an isolated disposable PostgreSQL **of the target major version** before any later gate. Running it now is not authorized. Completing it against the real server is not authorized. Results copied from the role's name, or from a single `has_table_privilege` query, are not acceptance.

### 8.1 Stage 1 read-only role (future)

Purpose: snapshot and preview only.

Must not hold: `rolsuper`, `rolcreatedb`, `rolcreaterole`, `rolreplication`, `rolbypassrls`, membership in any role that holds those, `INSERT`/`UPDATE`/`DELETE`/`TRUNCATE`/`REFERENCES`/`TRIGGER` on application tables, `CREATE` on schemas, ownership of application tables, `EXECUTE` on non-catalog functions that write, or membership that inherits any of those. `LOGIN` may exist only while a snapshot window is open, and only with a credential released for that window.

Must be able to: `SELECT` the order and payment columns the snapshot reads, `SELECT` on `django_migrations` if schema inspection stays in this role, and `EXECUTE` on `pg_control_system()` if identity is required. That function is not a general public read on every PostgreSQL build; the exact default grant for the target major version is **NOT VERIFIED** and must be read from the disposable cluster's catalog. If the only way to call it is superuser, do not grant superuser. Read identity through a separate admin path instead. The correction command already refuses when `system_identifier` is missing.

`SET TRANSACTION READ ONLY` in the command remains required. `ALTER ROLE … SET default_transaction_read_only = on` is additional, not primary.

### 8.2 Execution role (future)

Purpose: one compare-and-set batch, then the privilege is removed.

Least privilege is defined by the statements the command actually sends:

| Statement | Privilege the disposable test must prove is necessary and sufficient |
| --- | --- |
| `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` | Ability to set transaction characteristics. Not a table grant. |
| `pg_try_advisory_xact_lock` | Execute on that function. No table grant. |
| `pg_backend_pid`, `pg_current_xact_id`, `txid_status`, `pg_is_in_recovery` | Execute as required. Confirm each on the disposable server. |
| `SELECT … FOR UPDATE NOWAIT` on `orders` | `SELECT` plus the `UPDATE` privilege PostgreSQL requires for `FOR UPDATE`. Whether a column-level `UPDATE` grant is enough for this statement is **NOT VERIFIED** and must be tested. Do not grant `UPDATE` on every column if a narrower grant passes the real statement. |
| `UPDATE orders SET total_price = …` | `UPDATE` on `total_price` only, if the lock test shows the lock does not need a wider update grant. |
| `SELECT` on `payment` and `introspection.table_names()` | `SELECT` on `payment`. Introspection queries `pg_catalog` / `information_schema`; prove the role can see that table and cannot see a needless write path. |
| Sum aggregate | `SELECT` on `total_price`. |
| `MigrationExecutor` | This should not run as the execution role. Schema check belongs to the read-only stage or to a DBA. The execution role must not be able to insert into `django_migrations` or run DDL. |

Must not hold: superuser, `CREATEDB`, `CREATEROLE`, replication, `BYPASSRLS`, ownership of `orders` or `payment`, `TRUNCATE`, `DELETE`, `INSERT` on `orders`, grants on other application tables, `CREATE` on `public`, execute on every `SECURITY DEFINER` function, or membership in the migration/admin role. `PUBLIC` grants on `public` must be reviewed and revoked where they supply a write path. Temporary-table and large-object privileges must be reviewed because they are write paths that table grants do not describe.

### 8.3 Static review checklist

Perform on the disposable cluster with a catalog dump saved as evidence. Each line is **NOT VERIFIED** today.

1. `rolsuper`, `rolinherit`, `rolcreaterole`, `rolcreatedb`, `rolcanlogin`, `rolreplication`, `rolbypassrls`, `rolconnlimit` for the read-only role, the execution role, and every role they are a member of, directly or indirectly.
2. Ownership of the database, schemas, tables, sequences, and functions the command touches.
3. Direct grants and grants to `PUBLIC` on database, schema, table, column, sequence, function, and language.
4. Sequence `USAGE`/`UPDATE`/`SELECT`. The correction's `UPDATE` of `total_price` does not take a new primary key in Django. Prove no trigger consumes a sequence anyway.
5. Temporary schema and `pg_largeobject` privileges.
6. `SECURITY DEFINER` functions executable by either role, and the owner they run as.
7. Triggers, rules, and RLS policies on `orders` and `payment`, including policies that fire for the table owner. Migration source has no `CREATE TRIGGER` / `CREATE POLICY`. The live catalog is a separate fact.
8. Connection pooler or `SET ROLE` / `assume_role` in front of the session. Django will run `SET ROLE` if `OPTIONS['assume_role']` is set. It is unset in `config/settings.py`. An external pooler that lets a client pick a role is a write path.
9. Ability to run `CREATE`, `ALTER`, `DROP`, `COPY`, `pg_read_file`, or `lo_import`. Must fail for both roles.
10. `SELECT FOR UPDATE` and the single-column `UPDATE` under the proposed grants, including a denied attempt to update `is_paid` or `status`.
11. A denied attempt to `INSERT` into `django_migrations` and to `CREATE TABLE`.
12. `default_transaction_read_only=on` does not stop a role that can `SET` it off; demonstrate that, and demonstrate that removing write grants does stop the write.

Evidence to retain: SQL of the grants, command output, PostgreSQL version, `system_identifier`, role OIDs, and the git commit of the command under test. Failure response: do not proceed to snapshot or approval. Fix grants on the disposable cluster only, then repeat the checklist. Do not apply the fix to the real server under this plan.

## 9. Prevent premature execution-role use

Creating a `LOGIN` role, a password, a certificate, or an inherited write grant before execution authorization gives anyone who obtains that secret a write path the approval file does not control. This revision does not create or alter roles.

Required lifecycle, **NOT IMPLEMENTED**, and not started:

1. Through gate 6 (independent approval), no execution role exists, or it exists as `NOLOGIN`, `NOINHERIT` is set on every other login, it has zero memberships, and it has zero write grants.
2. The Stage 1 read-only role is a different role. It is not a member of the execution role and the execution role is not a member of it.
3. Grants for the execution role are applied only inside the approved execution window, by a DBA path that is not the correction command, after gates 1–7 are recorded.
4. The password or client certificate is released by a second person from a store the operator cannot read early. Release is logged. The release record names the authorization id.
5. The role gains `LOGIN` only for that window. `rolconnlimit` is 1.
6. The command connects as that role, re-checks `current_user`, `session_user`, and `pg_is_in_recovery()`, and refuses any other role.
7. Immediately after the terminal audit record, `LOGIN` is revoked, the password is removed, write grants are revoked, and the credential in the store is destroyed. A failed revoke is an incident: halt and assume the credential is live until the DBA proves otherwise.
8. `EXECUTION_ENABLED` remains a separate code switch. A true flag without a released credential must fail. A released credential with a false flag must fail. Neither one alone is authorization.
9. The web application's migrate-on-start login in `docker-compose.prod.yml` must not be this role and must not inherit it. Whether production still uses that compose command is **NOT VERIFIED**. It is a reason not to reuse `DJANGO_DB_USER` as the execution role.

An owner decision to "create the role early but not tell anyone the password" does not meet this lifecycle. Passwords leak, and grants without `LOGIN` are still usable through `SET ROLE` if any login inherits them.

## 10. Rollback and reconciliation

### 10.1 Current behavior (insufficient)

Rollback is disabled by `EXECUTION_ENABLED`. If it were enabled, `load_execution_report` would accept `RUN_STARTED` and `RUN_COMMIT_UNKNOWN`. `_rollback` would restore every row when all of them show the corrected total, and would no-op when all of them show the original total, including for those two report statuses. Mixed or unexpected rows already stop the command. That stop rule is the part worth keeping. The acceptance of incomplete reports and the shared approval file are not.

A no-op because rows look original is not evidence the transaction aborted. A restore because rows look corrected is not evidence a specific transaction committed, and it is a new write.

### 10.2 Separate rollback authorization

**NOT IMPLEMENTED.** A rollback write requires its own signed payload, distinct from the apply authorization, containing:

- the apply `authorization_id` and its nonce;
- the original report hash and the durable xid / terminal evidence;
- target database identity (same primary rules as section 4);
- the same batch, rule, and order-id set;
- the original before-state hash and a post-execution state hash taken after the apply terminal record;
- a fresh reconciliation id and the hash of a newly generated reconciliation record;
- the rollback policy version;
- a new nonce, a new window, operator, and an approver who is not the operator;
- revocation status for both the apply authorization and the rollback authorization.

The apply signature does not authorize rollback. `AUTHORIZED_APPROVALS` does not authorize rollback. An owner message that says "roll it back" does not authorize rollback.

### 10.3 Per-order reconciliation before any rollback write

On the re-identified primary, inside one read-only repeatable-read transaction, classify **every** order in the batch:

| Observed state | Meaning | Action |
| --- | --- | --- |
| Matches the signed before-state, and apply evidence is `ROLLED_BACK` or a verified no-op | Already at the prior value with transaction evidence | No write. Record `ROLLBACK_NOOP`. |
| Matches the signed post-execution state, and apply evidence is `COMMITTED` with a resolved xid | Candidate for restore | Eligible for the rollback transaction only if **every** order in the batch is in this class or the noop class above, and the rollback signature matches. |
| Matches neither, or `is_paid` / `wordpress_id` / payment presence differs | Unexpected, partial, external, or unknown | Stop the entire batch. No row is restored. |
| Apply evidence is `COMMIT_UNKNOWN`, `RUN_STARTED`, missing, or torn | Unknown | Stop. Do not use row contents to choose a restore. Recovery is section 5, or a rehearsed restore from backup under its own gate. |
| Some rows corrected and some original | Partial or mixed | Stop the entire batch. Phase 3 already refuses this in code. Keep that refusal. The remedy is the verified backup, not a best-effort per-row update. |

"Stop" means zero `UPDATE` statements for the batch. There is no per-row override. An owner decision to proceed is not a substitute for a missing xid, a matching reconciliation record, or a signed rollback authorization.

The rollback transaction, when it is later allowed, uses the same connection-identity, `PRE_COMMIT`, and `txid_status` rules as apply. Its terminal classes are `ROLLBACK_COMMITTED`, `ROLLBACK_ROLLED_BACK`, and `ROLLBACK_COMMIT_UNKNOWN`. The last one halts further writes.

This revision does not enable `--rollback` and does not add the second signature.

## 11. Test matrix

Every test below is **NOT EXECUTED**. Existing tests in `products/tests_order_amount_correction*.py` were not run. Where an existing test asserts the opposite of a row below (retry after `COMMIT_UNKNOWN`, restore from a `RUN_STARTED` file), that test is evidence of current behavior, not a pass of this matrix.

Isolated environment for every row: a new disposable PostgreSQL cluster, `cluster_name` distinct from any real server, non-superuser roles from section 8, `config.settings_isolated_test` host denylist left in place, no route to the real database, image digest recorded, source-tree identity recorded. Failure response for every row: keep execution disabled, do not promote the build, file a defect, and repeat on a fresh disposable cluster after a code change that is itself reviewed. Evidence to retain: PostgreSQL version, `system_identifier`, role name, git commit, command output, audit files, and `txid_status` output.

| ID | Preconditions | Expected result | Evidence |
| --- | --- | --- | --- |
| T1 Connection replacement during cleanup | Disposable DB. After `commit()` returns, force `Atomic.__exit__` `finally` to drop `wrapper.connection` and open a new session before classification. | Class stays `COMMIT_UNKNOWN` until `txid_status` on the **old** xid is `committed`. The new session's `SELECT` of `total_price` is not used as proof. No second write. | Both PIDs, xid, `txid_status`, audit file. |
| T2 Exception masking in `Atomic.__exit__` | Body raises; `rollback()` raises; `close()` raises a different exception. | Outer exception is visible and the body exception remains recorded. Class is `COMMIT_UNKNOWN` unless abort evidence exists. No partial `total_price` change remains. | Exception chain, row checksums. |
| T3 Commit success then process kill | `commit()` returns; process is killed before the terminal fsync. Durable `PRE_COMMIT` exists. | Restart does not write. Recovery reads `txid_status=committed` and only then records `COMMITTED`. | xid, audit file before and after recovery. |
| T4 Connection loss during commit | Drop the socket after the server can process `COMMIT` and before the client reads the result, and a second case where the drop happens before the server receives `COMMIT`. | Both are `COMMIT_UNKNOWN` at the client until `txid_status` distinguishes them. No retry write in either case before that. | Packet timing notes, xid status, halt record. |
| T5 `txid_status` unavailable or NULL | Valid xid on a cluster whose status function returns NULL (or the function is denied). | `COMMIT_UNKNOWN`, halt, no write. | Error or NULL result, halt file. |
| T6 Prepared-transaction ambiguity | Manually create a prepared transaction that holds the same xid or lock, without using production data. | Writer halts as `COMMIT_UNKNOWN`. It does not issue `COMMIT PREPARED`. | `pg_prepared_xacts` snapshot, halt file. |
| T7 Failover or endpoint change | Two clusters, or a primary and a standby that share a `system_identifier` copy. Point the second connection at the other endpoint. | Identity-plus-recovery check refuses. No write based on the second endpoint's rows. | Both system identifiers, `pg_is_in_recovery`, refusal output. |
| T8 Forged or replaced authorization | Flip a payload byte; replace the file with a same-shaped file; put the digest only in `AUTHORIZED_APPROVALS`. | Refusal. Signature check fails closed. The in-source digest map alone does not pass. | Refusal text, unchanged row checksums. |
| T9 Modified non-Python inputs | Change `requirements.txt` or a Dockerfile after the source-tree/build identity was signed. Leave `.py` files untouched. | Measured build or image identity differs. Apply refuses. | Both manifests. |
| T10 Replay, expiry, revocation, batch substitution | Reuse a nonce; present an expired window; present a revoked id; swap `preview_sha256` or the order-id set. | Each case refuses before any `UPDATE`. | Ledger, revocation list generation, zero row locks taken (prove with statement log). |
| T11 Effective privileges and indirect side effects | Section 8 checklist roles. Add a disposable trigger that writes a side table. | Side-table write is either impossible under the grant or, if the trigger fires, the test fails the privilege gate. `is_paid` update is denied. | Grant dump, denied-SQL log, side-table count. |
| T12 Premature execution-role use | Execution role is `NOLOGIN` with no grants; then `LOGIN` with grants but no credential release; then credential release outside the window. | Connection fails in each case. No `UPDATE` reaches the server. | Server log showing no successful login, or login without a following update. |
| T13 Audit write, flush, fsync, truncation | Inject failure on create, on `write`, on `flush`, on `fsync`, and a torn last line. Kill after `PRE_COMMIT`. | No `COMMIT` if `PRE_COMMIT` is not durable. A torn file or a file ending at `RUN_STARTED` does not authorize rollback. Halt is set when the class is unknown. | Partial files, statement log showing no `COMMIT` in the pre-commit failures. |
| T14 Rollback of partial or external edits | One order changed outside the batch; one order missing; a payment inserted; a mix of old and new totals; a `RUN_STARTED` report whose rows look corrected. | No rollback `UPDATE`. `COMMIT_UNKNOWN` / unexpected state stops the whole batch. | Statement log, reconciliation record. |
| T15 `SELECT FOR UPDATE` under proposed grants | Execution role with the intended grants only. | The lock and the `total_price` update succeed. Update of other columns and of other tables fails. A role with only `SELECT` cannot take the lock. | SQLSTATE values, grant script. |

Existing nearby tests (`test_commit_failure_is_reported_as_unknown_and_never_as_rolled_back`, `test_a_report_cut_off_after_run_started_is_resolved_from_the_database`) are **NOT EXECUTED** here. Their assertions currently allow a noop rollback and a retry. They do not satisfy T4, T13, or T14.

## 12. Gate dependency table

Gates run in this order. A later gate cannot be marked satisfied while an earlier one is unsatisfied or **NOT VERIFIED**. A pass at gate 1 or gate 2 does not satisfy gate 8 or gate 9.

| Gate | Purpose | Required evidence | Independent reviewer | Preconditions | Failure response | Now |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Source review and planning | This plan and the findings note reviewed against the commit | Review record naming `2c3b9fd` or a later reviewed commit, plus disposition of F1–F11 | Someone other than the author of the change | This document exists | Remain NO-GO | **Unsatisfied.** The document exists. No independent review exists. |
| 2. Disposable test verification | Section 11 matrix | Retained logs for T1–T15 on a disposable cluster | Someone other than the implementer | Gate 1 | Fix on disposable only; do not touch the real database | **NOT EXECUTED / unsatisfied** |
| 3. DBA privilege and identity preparation | Section 8 and 9, still without a usable write login | Catalog dump, grant script, proof the execution role is `NOLOGIN` and ungranted, proof the app migrate role does not inherit it | DBA, not the operator | Gates 1–2 | Stop. Do not issue a password. | **NOT VERIFIED / unsatisfied** |
| 4. Deployment and build verification | Section 7 identities | Clean source-tree manifest, lockfile proposal accepted, image digest measured in a non-production registry | Release owner, not the operator | Gates 1–3 | Do not deploy the image to the target | **NOT VERIFIED / unsatisfied**. Reproducible build is not claimed. |
| 5. Snapshot and preview generation | Read-only artifacts on the **approved** target using the Stage 1 role | Before-state, manifest, preview, policy hash, database identity including recovery state | Operator produces; a second person checks hashes | Gates 1–4. Read-only credential released for this window only. | Discard artifacts. No write role exists yet. | **Unsatisfied.** No target snapshot was taken in this revision. |
| 6. Independent approval | Section 6 signature | Signed payload, trust-anchor id, revocation-list generation | Approver who is not the operator | Gate 5 hashes | Refuse. Do not release the execution credential. | **Unsatisfied.** Registry empty. No signature scheme. |
| 7. Backup and restore rehearsal | Restore actually returns the pre-change fingerprint | Backup identity, restore log, fingerprint match on a **disposable** restore target | DBA | Gates 1–6. Backup of the real database is a separate approved operation, not this revision. | No execution credential release | **Unsatisfied / NOT VERIFIED** |
| 8. Execution authorization | Window open, nonce unused, role still without a leaked credential | Section 6 checks logged; credential-release log by the second person; `EXECUTION_ENABLED` change reviewed | Approver plus DBA | Gates 1–7 | Do not set `LOGIN`. Destroy any partial credential. | **Unsatisfied** |
| 9. Execution | One batch, one transaction, section 5 evidence | Durable `PRE_COMMIT`, `txid_status=committed`, terminal record | Operator executes; a second person watches the halt rule | Gate 8 window still valid | `COMMIT_UNKNOWN` → halt. No retry. | **Unsatisfied.** Flag is false. Not authorized. |
| 10. Reconciliation | Read-only compare of every order to the signed post-state | Fresh reconciliation record | Second person | Gate 9 terminal record is `COMMITTED` with xid evidence | Halt. Do not "fix forward." | **Unsatisfied** |
| 11. Rollback authorization | Only if reconciliation or the owner requires undo **and** evidence allows it | Separate signature, section 10 | A new approver action | Gate 10. Unknown states skip this gate and go to restore review instead. | Stop with zero updates | **Unsatisfied.** Not authorized. |

Passing gate 1 or gate 2 never marks gate 8 or gate 9 satisfied.

## 13. NOT VERIFIED

- Revision 6 file contents beyond the issues listed in the task (the file is absent).
- Any historical test pass, including the Phase 3 "332 tests" sentence and disposable `server_version_num` 160015.
- Live or disposable database identity, role list, grants, RLS, triggers, poolers, and `pg_control_system()` privileges.
- Production equality with `docker-compose.prod.yml`, including whether `migrate` runs as a superuser.
- Contents of ignored env files (not read).
- `txid_status` behavior on the target major version (specified from PostgreSQL's contract; not executed).
- Durability of `os.fsync` on the operator filesystem.
- Image digests and reproducibility.
- Signature verification (no implementation).
- Connection-loss timing (T4) and failover (T7).
- That a column-level `UPDATE` grant is sufficient for `SELECT FOR UPDATE`.
- Independent review of this document.

## 14. Decisions required from owners

These are unanswered. This document does not answer them on the owner's behalf.

| Decision | Owner |
| --- | --- |
| Currency hypotheses H1 (IRR) and H2 (IRHT), and the factors in `core.money` | Business owner, with settlement evidence |
| Rules R4, R5, R7, rounding, and the large IRHT set | Business owner |
| The two anomaly WordPress ids | Business owner. They must not be guessed. |
| Trust-anchor location, algorithm, key holders, and revocation publisher | Security owner |
| Whether the execution role may exist as `NOLOGIN` with zero grants before gate 8, or must not exist at all until then | DBA and security owner |
| Backup tool, retention, and who may see the backup | DBA |
| Target environment name and the endpoint identity that will be signed | DBA and business owner |
| Accepting that `COMMIT_UNKNOWN` ends in halt rather than a retry | Business owner and DBA |
| Whether templates and the rest of the image context must be in source-tree identity or only in image identity | Security owner. This plan puts command logic in source-tree identity and the image digest over the full build context. |

## 15. GO / NO-GO checklist

| # | Condition | Result |
| --- | --- | --- |
| 1 | Independent review of Revision 7 recorded | NO |
| 2 | T1–T15 executed on disposable PostgreSQL and retained | NO |
| 3 | Privilege checklist passed, execution role not usable | NO |
| 4 | Source, build, and image identities measured and signed | NO |
| 5 | Fresh read-only snapshot and preview bound to that identity | NO |
| 6 | Signed apply authorization, unexpired, unrevoked, nonce unused | NO |
| 7 | Backup restore rehearsed and fingerprinted | NO |
| 8 | Execution credential released only inside the window | NO |
| 9 | `EXECUTION_ENABLED` still false in the reviewed tree | YES (remains disabled; this is not a GO) |
| 10 | Anomaly registry empty | YES (fail-closed; this is not a GO) |
| 11 | `AUTHORIZED_APPROVALS` empty | YES (fail-closed; this is not a GO) |
| 12 | `txid_status` evidence design implemented | NO |
| 13 | Halt after uncertain commit implemented | NO |
| 14 | Separate rollback authorization implemented | NO |
| 15 | No real database contacted by this revision | YES |

**Final status: NO-GO.**

Items 9–11 and 15 show the safety switches are still closed. A closed switch is not an approval to open it. Execution, rollback, role creation, backup of real data, and deployment remain unauthorized until every gate in section 12 is independently completed and a later document records that evidence. This file is not that record.
