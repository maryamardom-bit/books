# Kasra order-correction safety audit — Revision 8 findings

Status: **NO-GO — NO EXECUTION AUTHORIZED.**

This is a documentation-only, read-only audit. It reconciles the Revision 7 plan, the Revision 7 static findings, the Phase 3 plan, and the source they describe. It approves nothing. Completing this document is not execution approval, review approval, or a test result.

Companion: `audit_reports/KASRA_ORDER_CORRECTION_REV8_GATE_MATRIX.md`.

## 1. Baseline verified before the audit

| Item | Observed |
| --- | --- |
| Authorized baseline | `90987a6cd10a0671aebede477c9fe29754a44669` |
| HEAD | `90987a6cd10a0671aebede477c9fe29754a44669` (subject `audit`) |
| HEAD tree | `6d302f64d43dfbdcad08f113d93e808bdfdd8236` |
| Branch | `cursor/payment-hardening-and-architecture-review` |
| Local upstream ref | `origin/cursor/payment-hardening-and-architecture-review` resolves to the same commit locally. No fetch was run, so the remote itself was not checked. |
| Git status | Clean (`git status --porcelain=v1 --untracked-files=all` empty), before and after the source inspection |
| Ancestry | `2c3b9fde70fc7ff3e5b5f7a72bdcb111b9d74d03` is an ancestor of HEAD; HEAD is exactly one commit ahead |
| Changed files `2c3b9fd..90987a6` | `A audit_reports/KASRA_ORDER_CORRECTION_PLAN_REV7.md`, `A audit_reports/KASRA_ORDER_CORRECTION_REV7_STATIC_FINDINGS.md`. No implementation file changed. |

Revision 7 names `2c3b9fd` as its inspected commit. Its two documents were committed afterwards in `90987a6`. Every implementation file has the same content at both commits, so Revision 7's source line references apply unchanged at `90987a6`.

Point-in-time Git blob ids at HEAD (an observation, not a signed identity):

| Blob | Path |
| --- | --- |
| `b89d3f6106c3874dfb853656bf477662b4d728ab` | `products/management/commands/correct_imported_order_amounts.py` |
| `a9143b343d8593b9890be25aeb160bcf8c69e70e` | `products/management/commands/import_wordpress_complete.py` |
| `080cbf4851411e9c5da4a5c3d88fbf138366ff77` | `products/management/commands/audit_imported_order_amounts.py` |
| `927e1cf3421195fac27fae980e7a3ee2cee1df80` | `products/tests_order_amount_correction.py` |
| `32e1bba72a016466c144421dc73a73832dec1980` | `products/tests_order_amount_correction_safety.py` |
| `dda98be93f35c5bc2a877123dc3baa3dbd90d206` | `products/tests_order_amount_correction_pg.py` |
| `c2a4f030b490fb85233c892d2c8ca65843c669e5` | `config/settings.py` |
| `ab1e5e8899be8c0582c3ac59d14904b29377e459` | `config/settings_production.py` |
| `01f86dd3b4a9e253c8fe09c5f957c57a6b523c75` | `config/settings_isolated_test.py` |
| `f75d4d066e3a953569edceccb4b11ae1d58d2fa5` | `config/test_runner.py` |
| `c73361f17fd61ce96478d340b6fe22e2fcd95884` | `requirements.txt` |
| `88c5d0c7df071bbc006c04b575978759b457145a` | `Dockerfile` |
| `8b508aeb89f369a4c1ff0d3363e695d74fb4cfef` | `Dockerfile.prod` |
| `1fd712c0ea7e791491756d78ec86a46d6ae58308` | `docker-compose.yml` |
| `0228751922bb1edfca87314421f1cf24849a193f` | `docker-compose.prod.yml` |
| `2e64e8bef3cbb21303860efadfb280fdf237c7cd` | `audit_reports/KASRA_ORDER_CORRECTION_PLAN_REV7.md` |
| `1774124d882b353b7b718161f370607d26dfa424` | `audit_reports/KASRA_ORDER_CORRECTION_REV7_STATIC_FINDINGS.md` |
| `946df4bf16a7fe14fd75d8b160b12b9c2f4b6331` | `audit_reports/P0_2_PHASE3_CORRECTION_PLAN.md` |

## 2. Method and limits

- Read-only commands:
  - Git: `rev-parse`, `branch --show-current`, `status`, `cat-file -t`, `merge-base --is-ancestor`, `diff --name-status`, `diff --stat`, `log`, `ls-files`, `ls-files --eol`, `config --get core.autocrlf`, `grep`.
  - PowerShell: `Get-ChildItem` (top-level directory listing and locating installed Django and psycopg2 files in `venv`), `Select-String` (line numbers in installed Django files and the static `def test_` count), `Test-Path` (checking for `.github`).
  - Editor search and file-read tools on the tracked tree and the installed Django files.
- Source read: the correction command, importer lock helper, settings modules, test runner, the three correction test files `products/tests_order_amount_correction.py`, `products/tests_order_amount_correction_safety.py`, and `products/tests_order_amount_correction_pg.py` (cited parts), `requirements.txt`, both Dockerfiles, both compose files, `.dockerignore`, and the installed Django 6.0.2 files `django/db/transaction.py`, `django/db/utils.py`, `django/db/backends/base/base.py`, `django/db/backends/postgresql/base.py` in the local `venv`.
- Installed package versions were taken from `venv/Lib/site-packages/django-6.0.2.dist-info` and `psycopg2_binary-2.9.11.dist-info` directory names. Python was not run and Django was not imported.
- Not read: `.env`, `.env.prod`, any credential store, and the local agent transcripts. Phase 3 section 6 states that a transcript contains printed environment values, so transcripts were excluded as a possible source of the 332-test log.
- Not done: no database connection, no test run, no Python execution, no migration, importer, correction, or rollback, no flag change, no role or approval change, no commit, merge, or push.
- Statements about PostgreSQL server behavior that cannot be read from repository or installed-library source are marked **NOT VERIFIED**, even where they match PostgreSQL documentation.

## 3. Classification legend

| Classification | Meaning in this document |
| --- | --- |
| VERIFIED FROM SOURCE | Read directly in the tracked tree at `90987a6` or the installed Django 6.0.2 source |
| VERIFIED FROM EXISTING REPRODUCIBLE EVIDENCE | A retained, re-checkable artifact (log, JUnit file, catalog dump, digest) exists and supports the claim. **No claim in this audit reached this class.** |
| REASONABLE DESIGN PROPOSAL | A mechanism Revision 7 specifies. It is not implemented and is not a control. |
| NOT VERIFIED | Could not be confirmed without a server, a run, an external system, or a person |
| CONTRADICTED BY SOURCE | Source shows something different from the claim |
| MISSING OR INCOMPLETE | The claim omits a material path, or the required artifact does not exist |

"Blocks" means: while this item stays as classified, no future execution authorization can be granted.

## 4. Claim summary

| ID | Claim (short) | Classification | Blocks |
| --- | --- | --- | --- |
| A1 | Rev7 inspected `2c3b9fd`; `90987a6` only adds the Rev7 documents | VERIFIED FROM SOURCE | No |
| A2 | Rev7: tree clean and upstream up to date at inspection | NOT VERIFIED | No |
| A3 | No Revision 6 document is tracked | VERIFIED FROM SOURCE | No |
| A4 | Phase 3 "code is uncommitted" is stale; the examined correction files first appear in `2c3b9fd` | VERIFIED FROM SOURCE | Yes |
| A5 | Django 6.0.2 and psycopg2-binary 2.9.11 pinned and installed locally | VERIFIED FROM SOURCE | No |
| B1 | `EXECUTION_ENABLED` false; anomaly registry and `AUTHORIZED_APPROVALS` empty | VERIFIED FROM SOURCE | No |
| B2 | Apply and rollback refuse before reading inputs while disabled | VERIFIED FROM SOURCE | No |
| B3 | `apply_blockers` is a report field, not an authorization | VERIFIED FROM SOURCE | No |
| C1 | Outcome labels come from exceptions and `body_done` only | VERIFIED FROM SOURCE | Yes |
| C2 | No xid, backend PID, recovery state, or driver identity is recorded | VERIFIED FROM SOURCE | Yes |
| C3 | Current `ROLLED_BACK` is only reachable when Django never called `commit()` | VERIFIED FROM SOURCE | Yes, until the GM-03 design covers it |
| C4 | Rev7 section 5.1 evidence rules for the three outcomes | REASONABLE DESIGN PROPOSAL | Yes |
| C5 | Rev7 pairs `pg_current_xact_id()` with `txid_status()` and treats bad xids as NULL | NOT VERIFIED | Yes |
| C6 | No halt latch; tests expect a retry apply after `RUN_COMMIT_UNKNOWN` | VERIFIED FROM SOURCE | Yes |
| C7 | A fresh preview is a remedy for `COMMIT_UNKNOWN` (command lines 1214–1216; Phase 3 §10.6, §10.9) | CONTRADICTED BY SOURCE | Yes |
| D1 | Rev7 line-level description of `Atomic.__exit__` | VERIFIED FROM SOURCE | No |
| D2 | Body error plus failed rollback: rollback error is swallowed | VERIFIED FROM SOURCE | No |
| D3 | Rev7 commit-failure paths are complete | MISSING OR INCOMPLETE | Yes, until the GM-03 design covers it |
| D4 | Revision 7 §4.7–§4.8 list the reconnect paths in `Atomic.__exit__` completely | MISSING OR INCOMPLETE | Yes |
| D5 | `connect()` resets atomic flags and reuses the same wrapper | VERIFIED FROM SOURCE | No |
| D6 | No pool, health checks, `CONN_MAX_AGE`, `assume_role`, or `ATOMIC_REQUESTS` in settings | VERIFIED FROM SOURCE | No |
| D7 | No external pooler sits in front of the target | NOT VERIFIED | Yes |
| E1 | Rollback accepts reports ending at `RUN_STARTED` or `RUN_COMMIT_UNKNOWN` | VERIFIED FROM SOURCE | Yes |
| E2 | "Truncated / incomplete reports are refused" (docstring, Phase 3 §10.7) | CONTRADICTED BY SOURCE | Yes |
| E3 | Rollback writes or no-ops based on row values, regardless of report status | VERIFIED FROM SOURCE | Yes |
| E4 | Apply approval also authorizes rollback | VERIFIED FROM SOURCE | Yes |
| E5 | Mixed corrected/original state is refused | VERIFIED FROM SOURCE | No |
| E6 | Rev7 separate rollback authorization and per-order reconciliation | REASONABLE DESIGN PROPOSAL | Yes |
| F1 | Authorization is a SHA-256 allowlist in source | VERIFIED FROM SOURCE | Yes |
| F2 | No signature, approver identity, nonce, window, or revocation | VERIFIED FROM SOURCE | Yes |
| F3 | An approval can be reused for repeated apply attempts | VERIFIED FROM SOURCE | Yes |
| F4 | Rev7 signed payload, trust anchor, nonce ledger, revocation | REASONABLE DESIGN PROPOSAL | Yes |
| F5 | Operator cannot alter the trust anchor; approver is independent | NOT VERIFIED | Yes |
| G1 | No source-tree, `*.py`, git-commit, or image identity is computed | VERIFIED FROM SOURCE | Yes |
| G2 | `requirements.txt` pinned without hashes; no lockfile | VERIFIED FROM SOURCE | Yes |
| G3 | Base and service images use mutable tags | VERIFIED FROM SOURCE | Yes |
| G4a | Working-tree line endings differ from Git blobs on this host (`core.autocrlf=true`, `i/lf w/crlf`) | VERIFIED FROM SOURCE | Yes |
| G4b | Images built from this checkout differ in bytes from images built from an LF checkout of the same commit | NOT VERIFIED | Yes |
| G5 | Repository build definitions do not record a commit (`.git` excluded from context; no commit build argument or label) | VERIFIED FROM SOURCE | Yes |
| G6 | Rev7 four-identity model | REASONABLE DESIGN PROPOSAL | Yes |
| G7 | Reproducible build | NOT VERIFIED | Yes |
| H1 | Identity check omits host, port, recovery state, and session | VERIFIED FROM SOURCE | Yes |
| H2 | Replicas and promoted standbys share `system_identifier` | NOT VERIFIED | Yes |
| H3 | Disposable-test isolation is enforced by code | MISSING OR INCOMPLETE | Yes |
| H4a | Production Compose runs `migrate --noinput` on web startup; both services reference `DJANGO_DB_USER` | VERIFIED FROM SOURCE | Yes |
| H4b | The web container's login equals the database bootstrap user | NOT VERIFIED | Yes |
| H5 | That bootstrap user is a superuser; production matches compose | NOT VERIFIED | Yes |
| H6 | No read-only or execution role is defined in the repository | VERIFIED FROM SOURCE | Yes |
| H7 | Rev7 privilege checklist and role lifecycle | REASONABLE DESIGN PROPOSAL | Yes |
| H8 | Column-level `UPDATE` suffices for `SELECT … FOR UPDATE`; `pg_control_system()` executable by non-superuser | NOT VERIFIED | Yes |
| H9 | Importer and correction share the advisory key; lock does not cover snapshot-to-apply | VERIFIED FROM SOURCE | No |
| H10 | Disposable server was PostgreSQL 16 (`160015`), same major as `books-db-1`, no route to it | NOT VERIFIED | Yes |
| I1 | Audit file: exclusive create, file `fsync` only, no directory `fsync`, no checksum | VERIFIED FROM SOURCE | Yes |
| I2 | `RUN_STARTED` is written with `flush()` and `os.fsync()` before the transaction; terminal marker after | VERIFIED FROM SOURCE | No |
| I3 | A failed terminal-marker write after commit leaves a file that rollback accepts | VERIFIED FROM SOURCE | Yes |
| I4 | `fsync` return is not universal durability | NOT VERIFIED | Yes |
| I5 | Rev7 `PRE_COMMIT` / terminal / `HALT` record design | REASONABLE DESIGN PROPOSAL | Yes |
| J1 | "332 tests ran, 2 locale failures, all correction tests passed" (332 equals only the static count of `def test_` definitions) | NOT VERIFIED | Yes |
| J2 | Real-PostgreSQL commit-failure test shows "no-op rollback, then successful retry" | CONTRADICTED BY SOURCE | No |
| J3 | Commit-failure coverage uses mocks; lost acknowledgement is not exercised | VERIFIED FROM SOURCE | Yes |
| J4 | Rev7 test matrix T1–T15 | MISSING OR INCOMPLETE | Yes |
| J5 | A test asserts `EXECUTION_ENABLED` is false | VERIFIED FROM SOURCE | No |

## 5. Detailed findings

### A. Baseline and document provenance

**A1 — Rev7 inspected `2c3b9fd`; `90987a6` only adds the two Rev7 documents.**
- Classification: VERIFIED FROM SOURCE.
- Where: Git history; Rev7 findings §1.
- Evidence: `git diff --name-status 2c3b9fd 90987a6` lists only the two Rev7 files as added. `merge-base --is-ancestor` exit 0.
- Uncertainty: none for file content. Rev7's own text still names `2c3b9fd` as HEAD.
- Next step: any later review record must name `90987a6` or a later reviewed commit, not `2c3b9fd`.
- Blocks: No.

**A2 — Rev7 states the tree was clean and the upstream was up to date when it was written.**
- Classification: NOT VERIFIED.
- Where: Rev7 findings §1.
- Evidence: point-in-time statement. Today the tree is clean, and the local tracking ref `origin/...` equals `90987a6`. No fetch was run.
- Uncertainty: the remote may differ from the local tracking ref.
- Next step: a reviewer runs `git fetch` and compares, outside this audit.
- Blocks: No.

**A3 — No Revision 6 document is tracked.**
- Classification: VERIFIED FROM SOURCE.
- Where: `audit_reports/` at HEAD contains six files: the Phase 1, 2, 3 reports, the feature-gap audit, and the two Rev7 files.
- Uncertainty: Revision 6 content can only be inferred from Rev7 §2.
- Next step: none required for safety; Rev7 §2 is treated as the issue list.
- Blocks: No.

**A4 — Phase 3 says the correction code is uncommitted; Rev7 says it is tracked at `2c3b9fd`.**
- Classification: VERIFIED FROM SOURCE (Rev7's correction of Phase 3 is right).
- Where: Phase 3 header, §10, §10.11; `git log` for the command, the three correction test files, `config/test_runner.py`, `config/settings_isolated_test.py`, and the Phase 3 plan.
- Evidence: every one of those examined files has exactly one commit, `2c3b9fd` (2026-10-12T12:44:27+03:30, "add test"). The Phase 3 plan is dated 2026-10-11 and describes test runs on an uncommitted working tree on top of `9cbcdbc`.
- Scope limit: this statement covers only the files listed above. Phase 3 §11 also lists `import_wordpress_complete.py`, `audit_imported_order_amounts.py`, and `products/tests_order_amount_audit.py` as changed. Their history was **not examined**. A read-only `git log` of those files was attempted during the consistency review, was blocked by the tool's auto-review, and was not retried. Their first-commit history is NOT VERIFIED.
- Uncertainty: the bytes that were tested on 2026-10-11 cannot be tied to any commit.
- Next step: any test evidence must be regenerated at a named commit (gate matrix GM-09).
- Blocks: Yes, for using any historical test claim as evidence.

**A5 — Django 6.0.2 and psycopg2-binary 2.9.11.**
- Classification: VERIFIED FROM SOURCE.
- Where: `requirements.txt` lines 8 and 41; `venv/Lib/site-packages/django-6.0.2.dist-info`, `psycopg2_binary-2.9.11.dist-info`.
- Uncertainty: the local virtualenv is not the image. The version inside any built image is NOT VERIFIED (see G2, G3).
- Next step: record versions from inside the measured image.
- Blocks: No.

### B. Execution controls

**B1 — Execution is disabled and both registries are empty.**
- Classification: VERIFIED FROM SOURCE.
- Where: `correct_imported_order_amounts.py` line 70 `EXECUTION_ENABLED = False`, line 75 `APPROVED_ANOMALY_WORDPRESS_IDS = frozenset()`, line 80 `AUTHORIZED_APPROVALS = {}`.
- Uncertainty: covers this tree only. A different deployed tree is not covered (see G1).
- Next step: none; keep unchanged.
- Blocks: No. These are fail-closed switches, not approvals.

**B2 — Apply and rollback refuse before any input is read while disabled.**
- Classification: VERIFIED FROM SOURCE.
- Where: `_require` lines 1169–1175 is the first call in `_apply` (line 1225) and `_rollback` (lines 1309–1312), before `Outputs.reserve`.
- Blocks: No.

**B3 — `apply_blockers` is a report field.**
- Classification: VERIFIED FROM SOURCE.
- Where: `apply_blockers` lines 743–761, used only in `preview_summary` (line 790).
- Blocks: No.

### C. Transaction outcomes (`COMMITTED`, `ROLLED_BACK`, `COMMIT_UNKNOWN`)

**C1 — Outcome labels come only from whether an exception escaped and whether the body returned.**
- Classification: VERIFIED FROM SOURCE.
- Where: `Command._run_write` lines 1193–1202.
- Evidence: `body_done` is set after `body()` returns, inside `write_transaction`. Any `BaseException` gives `COMMIT_UNKNOWN` if `body_done`, else `ROLLED_BACK`. No exception gives `COMMITTED`. `_finish` (1204–1220) writes `RUN_<outcome>`. "corrections committed" (line 1279) only means `Atomic.__exit__` returned.
- Uncertainty: none about the code.
- Next step: implement Rev7 §4.4 and §5 (GM-04).
- Blocks: Yes.

**C2 — No transaction id, backend PID, recovery state, or driver-connection identity is recorded.**
- Classification: VERIFIED FROM SOURCE.
- Where: whole command. A search for `pg_current_xact_id`, `txid_status`, `pg_backend_pid`, `pg_is_in_recovery` finds no match. `write_transaction` (355–373) runs only `SET TRANSACTION`, `pg_try_advisory_xact_lock`, and the identity check.
- Blocks: Yes.

**C3 — In current code, `ROLLED_BACK` can only be produced when Django never called `commit()` for that transaction.** (New in Revision 8.)
- Classification: VERIFIED FROM SOURCE.
- Where: `_run_write` 1196–1201; `write_transaction` 355–373; Django `Atomic.__exit__` 242–271.
- Evidence: `commit()` is reached only when `__exit__` sees no exception (line 242). That happens only after `body()` returned and `body_done` was set inside the same `with` block. An exception raised before that point (lock refusal, identity mismatch, row lock, compare-and-set miss, `KeyboardInterrupt`) leaves `body_done` false, and Django takes the rollback branch (292–299), which never sends `COMMIT`.
- Condition: this conclusion holds under the settings reviewed in D6 and assuming no pooler (D7).
- What this does not show: that the server-side transaction has ended, that row locks are released, or that a durable record exists saying `COMMIT` was not sent. If the process dies, the file ends at `RUN_STARTED` and that knowledge is lost. Under the settings reviewed in D6 and assuming no pooler (D7), Rev7 §4.7's "COMMIT may have been sent" condition cannot arise on this specific path. Rev7's stricter evidence rule for `ROLLED_BACK` is still a reasonable design, mainly because nothing durable records the fact.
- Distinction: the current command's label is conservative on this path. That is not the same as a complete, verified transaction-outcome design, which does not exist (C2, C4).
- Next step: record "COMMIT not sent" durably in the future audit design (Rev7 §5.2), as part of GM-03.
- Blocks: Yes, until the GM-03 design covers it. It narrows F3 of Rev7 and closes nothing.

**C4 — Rev7 §5.1 evidence rules for each outcome.**
- Classification: REASONABLE DESIGN PROPOSAL.
- Where: Rev7 plan §5.1, §5.2.
- Evidence: no corresponding code (C2).
- Uncertainty: depends on C5 and D4 being resolved first.
- Next step: revise the design for C5 and D4, then implement and test on a disposable cluster (GM-03, GM-04, GM-09).
- Blocks: Yes.

**C5 — Rev7 reads `pg_current_xact_id()` and resolves it with `txid_status()`, and treats a foreign or unknown xid as returning NULL.**
- Classification: NOT VERIFIED.
- Where: Rev7 plan §4.4, §4.9, §5.1, T5; Rev7 findings §5.
- Evidence: no source; this is server behavior. As documented for PostgreSQL 13 and later, `pg_current_xact_id()` returns `xid8` and pairs with `pg_xact_status(xid8)`. `txid_status(bigint)` pairs with the older `txid_current()`. The plan mixes the two families without saying how the value is stored and cast. Also, as documented, an xid that is ahead of the cluster's next xid raises an error ("in the future") rather than returning NULL. A wrong-cluster xid can therefore surface as an error, not NULL.
- Uncertainty: exact behavior on the target major version, which itself is NOT VERIFIED (H10).
- Next step: on a disposable cluster of the target major version, record function signatures from `pg_proc`, and test current, aborted, too-old, future, and foreign xids. Fix the design text to one function family.
- Blocks: Yes. The outcome design cannot be implemented as written until this is settled.

**C6 — There is no halt after an uncertain outcome; current tests expect a retry.**
- Classification: VERIFIED FROM SOURCE.
- Where: `_finish` lines 1211–1216 prints "Do not retry blindly" but nothing enforces it. `Outputs.reserve` (302–314) only refuses an existing path. `tests_order_amount_correction_safety.py` lines 393–418: after `RUN_COMMIT_UNKNOWN`, the test runs a rollback that prints `Nothing to roll back (RUN_COMMIT_UNKNOWN)` and then a successful apply to `retry.csv`.
- Required rule (REASONABLE DESIGN PROPOSAL; not implemented, not verified):
  - An uncertain outcome (`COMMIT_UNKNOWN`, a report ending at `RUN_STARTED`, or a torn or missing terminal record) places a halt on the **target database identity**: `system_identifier` plus database oid, as recorded for that run.
  - The halt is not batch-scoped. It blocks every later apply and rollback write against that database identity, for any batch.
  - A new snapshot, preview, approval, or report path cannot clear the halt.
  - Only the recovery gate GM-24 can clear it, using recorded transaction-status evidence from a re-identified primary, or a separately authorized and rehearsed restore with a matching fingerprint.
  - `system_identifier` and database oid define the halt's scope. They are not endpoint authentication: replicas can share `system_identifier` (H2), and the current identity check omits endpoint and recovery state (H1). Re-identification for GM-24 also requires the approved endpoint and `pg_is_in_recovery() = false`.
- Blocks: Yes.

**C7 — A fresh preview is a remedy for `COMMIT_UNKNOWN`.** (Added in the Revision 8 corrections.)
- Classification: CONTRADICTED BY SOURCE.
- Where: the command's `COMMIT_UNKNOWN` message (lines 1214–1216: "Do not retry blindly: run a preview to see which values the orders hold"); Phase 3 §10.6 (`RUN_COMMIT_UNKNOWN` row: "A preview shows which values the orders hold") and §10.9 Limits ("It is reported as `COMMIT_UNKNOWN`, and a fresh preview is needed"). These contradict Rev7 plan §5.1: "A new preview that 'looks original' does not clear the halt."
- Evidence: `_preview` (lines 1129–1158) refuses `--execution-report` (1132–1134) and reads only `database_identity`, current order rows (`pk`, `wordpress_id`, `total_price`, `is_paid`), and payment order ids, in a new read-only transaction (1142–1145). It reads no transaction id and no transaction status. A preview therefore cannot establish whether the original transaction committed. It only shows current row values, which another transaction could have produced.
- Uncertainty: none about the code. Whether a stale replica could serve the preview is NOT VERIFIED (H1, H2, D7).
- Next step: GM-03 and GM-04 must state that a preview never clears a halt. GM-24 defines the only recovery path.
- Blocks: Yes.

### D. Django atomic and reconnect behavior (Django 6.0.2, installed source)

**D1 — Rev7's line-level description of `Atomic.__exit__`.**
- Classification: VERIFIED FROM SOURCE.
- Where: `django/db/transaction.py` 224–313. Pop 227–228; premature `in_atomic_block = False` 232–234; `closed_in_transaction` branch 237–240; commit 260–263; commit-error handling 264–271; rollback 292–299; `finally` 301–313. Backend references also match: `base.py` `connect` 236–261, `ensure_connection` 270–279, `_commit` 300–303, `close` 343–361, `set_autocommit` 457–492; `postgresql/base.py` `_close` 382–396, `init_connection_state` 398–405, `is_usable` 486–496; `utils.py` `DatabaseErrorWrapper.__exit__` 73–94.
- Blocks: No.

**D2 — Body exception plus failed rollback: the rollback error is swallowed.**
- Classification: VERIFIED FROM SOURCE.
- Where: `transaction.py` 292–299. `rollback()` raising `Error` leads to `close()` with no re-raise.
- Uncertainty: D4 shows that the `finally` block can still replace the body exception.
- Blocks: No (covered by D4 and C3).

**D3 — Rev7's commit-failure table (§4.7) is complete.**
- Classification: MISSING OR INCOMPLETE.
- Where: `transaction.py` 262–271; `django/db/utils.py` lines 21–26.
- Evidence: `InterfaceError` subclasses `Error`, not `DatabaseError`. If `commit()` raises `InterfaceError` (for example on a driver connection already closed client-side), the `except DatabaseError` at line 264 does not catch it. No rollback and no `close()` are attempted, and the `finally` calls `set_autocommit(True)` on the same wrapper. Rev7 §4.7 has no row for this path.
- Contrast with D4: on this path nothing sets `wrapper.connection` to `None` before `set_autocommit(True)` is attempted (`transaction.py` 303–307). `ensure_connection()` (`base.py` 473, 270–279) therefore finds a connection object and does not open a new session. `_set_autocommit` (`postgresql/base.py` 473–475) assigns `autocommit` on the same psycopg2 connection.
- NOT VERIFIED: that assigning `autocommit` on that already-closed psycopg2 connection raises again, and that this second error then replaces the original `commit()` error (leaving it only on `__context__`). This is a likely outcome from reading the control flow, not an observed one.
- Uncertainty: which psycopg2 failure modes surface as `InterfaceError` at `commit()` is NOT VERIFIED without fault injection.
- Next step: add an `InterfaceError` row to T2/T4 (GM-09), and cover this path in the GM-03 design.
- Blocks: Yes, until the GM-03 design covers it. The current command still labels it `COMMIT_UNKNOWN` because `body_done` is true. That conservative label is not a verified outcome design.

**D4 — Revision 7 §4.7–§4.8 list the reconnect paths in `Atomic.__exit__` completely.** (New in Revision 8.)
- Classification: MISSING OR INCOMPLETE.
- Where:
  - Rev7 plan §4.7, rows "`commit()` raises, `rollback()` raises, `close()` returns" ("Driver connection is closed") and "Body raises, `rollback()` fails, `close()` returns" ("Rollback failure is hidden").
  - Rev7 plan §4.8, list "Paths present in Django 6.0.2", whose first bullet covers only the `closed_in_transaction` branch.
  - Source: `transaction.py` 232–234, 270, 299, 301–307; `base.py` 343–361, 457–473, 270–279, 236–261.
- What Revision 7 gets right: §4.6 step 7 correctly says the `finally` "calls `set_autocommit(True)`" when `closed_in_transaction` is false. Rev7 findings §4 correctly describes `close()` "during an atomic block". The §4.7 statement "Driver connection is closed" is true of the **old** driver connection.
- What Revision 7 omits: that on these paths a **new** session can be opened during the same `__exit__` call. Neither §4.7 nor §4.8 records this.
- Evidence, outermost block (the only kind the command opens):
  1. `__exit__` sets `in_atomic_block = False` at line 234, before any commit or rollback.
  2. When it then calls `close()` (line 270 after a failed commit-and-rollback, or line 299 after a failed rollback), `close()` sees `in_atomic_block` false and takes the `else` branch at `base.py` 360–361: `self.connection = None`. `closed_in_transaction` is **not** set.
  3. The `finally` (303–307) therefore skips the `closed_in_transaction` branch and calls `set_autocommit(True)`.
  4. `set_autocommit` calls `ensure_connection()` (`base.py` 473). The connection is `None` and `in_atomic_block` is false, so `connect()` runs: a new psycopg2 session to whatever endpoint the settings resolve to at that moment, with atomic flags reset.
  5. This happens inside the same `__exit__` call, before control returns to `_run_write`. If the new connection fails, its error replaces the commit or body exception, which survives only on `__context__`. `_describe` (479–481) reports only the outer exception.
- Consequences:
  - Rev7 records that the old driver connection is closed but omits that a new session is opened in the same `__exit__` call. If that reconnect succeeds, the wrapper holds a fresh session when `_run_write` sees the exception.
  - The `closed_in_transaction` branch at 237–240 is reachable only if `close()` ran while `in_atomic_block` was still true, that is, during the body. Nothing in the command does that, and health checks are off (D6). On the command's own paths that branch is effectively unreachable.
  - Rev7's requirement to take rollback acknowledgement, PID, and xid evidence "on the same driver connection" cannot be met by inspecting the wrapper after `transaction.atomic()` exits. Those values must be captured inside the block before `__exit__`, or the write path must manage the transaction without `atomic()`.
  - The current command does not issue further SQL on the wrapper after `_run_write`, so today the new session is unused. A future post-commit verification step would silently run on it.
- Uncertainty: behavior under a real dropped socket, rather than a reading of control flow, is NOT VERIFIED.
- Next step: revise Rev7 §4.7–§4.8 and T1/T2 (GM-03). On a disposable cluster, record `id(wrapper.connection)` and `pg_backend_pid()` before the body and after `__exit__`, with injected rollback failure (GM-09).
- Blocks: Yes. The outcome-evidence design omits this path.

**D5 — `connect()` resets the wrapper's atomic flags and keeps the same wrapper object.**
- Classification: VERIFIED FROM SOURCE.
- Where: `base.py` 236–261.
- Blocks: No.

**D6 — Database settings use Django defaults for pooling, health checks, connection age, and autocommit.**
- Classification: VERIFIED FROM SOURCE.
- Where: `config/settings.py` 117–126 (no `OPTIONS`, `CONN_MAX_AGE`, `CONN_HEALTH_CHECKS`, `AUTOCOMMIT`, `ATOMIC_REQUESTS`). `config/settings_production.py` does not override `DATABASES`.
- Uncertainty: the deployed environment could select a different settings module. NOT VERIFIED.
- Blocks: No.

**D7 — No external connection pooler sits between the command and the target.**
- Classification: NOT VERIFIED.
- Where: Rev7 plan §4.6 step 3, §8.3 item 8.
- Evidence: compose files define no pooler. The real endpoint behind `DJANGO_DB_HOST` was not read.
- Next step: DBA documents the network path to the target (GM-11).
- Blocks: Yes. A pooler changes session, PID, and outcome semantics.

### E. Rollback on incomplete reports

**E1 — Rollback accepts reports ending at `RUN_STARTED`, `RUN_COMMITTED`, or `RUN_COMMIT_UNKNOWN`.**
- Classification: VERIFIED FROM SOURCE.
- Where: `RUN_FINAL_STATUSES` line 918; `load_execution_report` 946–952. Only `RUN_STARTED, RUN_ROLLED_BACK` is refused.
- Blocks: Yes.

**E2 — "Truncated or incomplete reports are refused."**
- Classification: CONTRADICTED BY SOURCE.
- Where: `load_execution_report` docstring 922–927 ("Rolled-back, no-op, truncated or edited reports are rejected"); Phase 3 §10.7 step 3 ("Tampered, ambiguous or incomplete reports are refused").
- Evidence: a report cut off after its `RUN_STARTED` line passes 951–952. `test_a_report_cut_off_after_run_started_is_resolved_from_the_database` (safety tests 438–448) builds exactly that file and expects a restore. Rev7 already identified the Phase 3 contradiction. The in-code docstring contradicting its own function is additional.
- Next step: change the code so these reports cannot authorize a rollback write, under a separate reviewed change (GM-05).
- Blocks: Yes.

**E3 — Rollback acts on current row values, whatever the report status.**
- Classification: VERIFIED FROM SOURCE.
- Where: `_rollback` 1318–1349; `rollback_state` 995–1014. `run_status` appears only in a message (1345). All-original gives `ROLLBACK_NOOP_ALREADY_RESTORED`; all-corrected opens a write transaction.
- Blocks: Yes.

**E4 — The apply approval also authorizes rollback.**
- Classification: VERIFIED FROM SOURCE.
- Where: `_rollback` line 1318 calls `_authorised_inputs` with the same approval file and the same `AUTHORIZED_APPROVALS` lookup.
- Blocks: Yes.

**E5 — Mixed corrected/original states are refused.**
- Classification: VERIFIED FROM SOURCE.
- Where: `_rollback` 1333–1337; `_apply` 1256–1257.
- Next step: keep this control in any redesign.
- Blocks: No.

**E6 — Separate signed rollback authorization and per-order reconciliation.**
- Classification: REASONABLE DESIGN PROPOSAL.
- Where: Rev7 plan §10.2, §10.3.
- Blocks: Yes until implemented and tested.

### F. Independent authorization and replay prevention

**F1 — Authorization is a SHA-256 allowlist compiled into source.**
- Classification: VERIFIED FROM SOURCE.
- Where: `load_approval` 848–896; `AUTHORIZED_APPROVALS` line 80. The code comment at lines 78–79 says the hash proves integrity, not authorization.
- Blocks: Yes.

**F2 — No signature, approver identity, nonce, time window, or revocation exists.**
- Classification: VERIFIED FROM SOURCE.
- Where: `APPROVAL_KEYS` 841–845 lists all eleven accepted keys. None of those concepts is present.
- Blocks: Yes.

**F3 — The same approval can drive repeated apply attempts.**
- Classification: VERIFIED FROM SOURCE.
- Where: `Outputs.reserve` 302–314 refuses only an existing path. Nothing records approval consumption. The safety test at line 417 re-applies with the same approval to a new report path after `RUN_COMMIT_UNKNOWN`.
- Uncertainty: compare-and-set, fingerprint, and preview-hash checks stop a second write once the first committed. They do not stop a retry after an uncertain outcome.
- Blocks: Yes.

**F4 — Rev7 signed payload, trust anchor, nonce ledger, expiry, and revocation.**
- Classification: REASONABLE DESIGN PROPOSAL.
- Where: Rev7 plan §6.2–§6.4.
- Uncertainty: algorithm, key custody, ledger storage, and revocation publisher are owner decisions not yet made (Rev7 §14).
- Blocks: Yes.

**F5 — The operator cannot change the trust anchor, and the approver is independent of the operator.**
- Classification: NOT VERIFIED.
- Where: Rev7 plan §6.3, §9.
- Evidence: organizational; nothing in the repository can show it.
- Next step: the security owner records the trust-anchor location and access list (GM-06).
- Blocks: Yes.

### G. Source, build, and image identity

**G1 — No source-tree, `*.py`, git-commit, or image identity is computed.**
- Classification: VERIFIED FROM SOURCE.
- Where: the command has no reference to `rev-parse`, `git_commit`, `image_digest`, `source_tree`, `__file__`, or `subprocess`. Only data files and the in-memory policy are hashed (`classification_policy` 273–289).
- Blocks: Yes.

**G2 — Dependencies are pinned without hashes; there is no lockfile.**
- Classification: VERIFIED FROM SOURCE.
- Where: `requirements.txt` (56 `==` pins, no `--hash` lines). No lockfile is tracked.
- Blocks: Yes.

**G3 — Base and service images use mutable tags.**
- Classification: VERIFIED FROM SOURCE.
- Where: `Dockerfile` line 1 `python:3.14.3`; `Dockerfile.prod` line 1 `python:3.14-slim`, lines 9–14 unpinned `apt-get` packages; `docker-compose.yml` and `docker-compose.prod.yml` `postgres:16`; `docker-compose.prod.yml` `redis:7`, `nginx:1.27`.
- Blocks: Yes.

**G4a — Working-tree line endings differ from Git blobs on this host.** (New in Revision 8.)
- Classification: VERIFIED FROM SOURCE.
- Where: `git config core.autocrlf` is `true`. `git ls-files --eol` shows `i/lf w/crlf` for `correct_imported_order_amounts.py` and `Dockerfile.prod`, and `i/lf w/lf` for `requirements.txt`.
- Evidence: on this host, on-disk bytes of those CRLF files differ from their Git blob content. A manifest of on-disk bytes will not equal Git blob hashes on this host.
- Next step: add a `.gitattributes` line-ending policy and define the source manifest over normalized blob content (GM-07).
- Blocks: Yes.

**G4b — Images built from this checkout differ in bytes from images built from an LF checkout of the same commit.**
- Classification: NOT VERIFIED. No image was built.
- Where: `Dockerfile.prod` line 19 (`COPY . .`) copies the working tree into the image; G4a shows the working tree holds CRLF files on this host.
- Evidence: inference from G4a and the `COPY` instruction only. Whether any deployed image was built on this host is also NOT VERIFIED.
- Next step: build the same commit from a CRLF and an LF checkout in an isolated builder and compare digests (GM-07).
- Blocks: Yes. Until it is disproved or normalized, a commit id cannot be treated as determining image bytes.

**G5 — Repository build definitions do not record a commit.** (New in Revision 8.)
- Classification: VERIFIED FROM SOURCE.
- Where: `.dockerignore` line 3 excludes `.git/`. Neither `Dockerfile` nor `Dockerfile.prod` declares a build argument or label that carries a commit.
- Scope limit: this does not show that an image cannot report its commit by any means. Commit metadata could be added outside these files, for example by build-time labels or build provenance. Whether any such metadata exists on a built image is NOT VERIFIED.
- Next step: record the commit and source manifest as build metadata or labels, verified against the registry digest (GM-07).
- Blocks: Yes.

**G6 — Rev7's four identities: source tree, build, image digest, authorization.**
- Classification: REASONABLE DESIGN PROPOSAL.
- Where: Rev7 plan §7.2.
- Uncertainty: needs G4a, G4b, and G5 added.
- Blocks: Yes.

**G7 — The build is reproducible.**
- Classification: NOT VERIFIED. Rev7 correctly does not claim it.
- Next step: GM-07 requires either an independent rebuild yielding the same digest, or a recorded security-owner acceptance of a non-reproducible but digest-pinned image.
- Blocks: Yes.

### H. PostgreSQL endpoint and privilege assumptions

**H1 — The identity check omits host, port, recovery state, and session.**
- Classification: VERIFIED FROM SOURCE.
- Where: `IDENTITY_REQUIRED` / `IDENTITY_COMPARED` 93–94; `database_identity` 376–396; `check_identity` 399–406. `cluster_name` is compared but not required, and it is a server setting.
- Current code does not refuse a write when `pg_is_in_recovery()` is true, or when the endpoint or backend PID differs from an approved value. It reads neither.
- Next step: GM-04's stop condition rejects writes in those cases, and when the database identity differs from the signed authorization payload. That requirement is not implemented.
- Blocks: Yes.

**H2 — Physical replicas and promoted standbys share `system_identifier`.**
- Classification: NOT VERIFIED (documented PostgreSQL behavior, not checkable from this repository).
- Next step: demonstrate on a disposable primary/standby pair (T7, GM-09).
- Blocks: Yes. Endpoint binding depends on it.

**H3 — Disposable-test isolation is enforced by code.**
- Classification: MISSING OR INCOMPLETE.
- Where: `config/settings_isolated_test.py` lines 16, 26–28; `config/test_runner.py` 9–30.
- Evidence: the host denylist is an exact string match on six names. Any other name or address for the same server (container IP, FQDN, alternate alias) passes. The runner checks `cluster_name` (a server-set value) and that the role is not a superuser. Neither check proves that the server is not the development or production database. The test settings also import `config.settings`, which reads environment configuration.
- Next step: retain network-level isolation evidence (separate network, no route, firewall) together with the server's `system_identifier`, compared to the known real systems' identifiers by a DBA (GM-08).
- Blocks: Yes. It is a precondition for any trusted disposable run.

**H4a — The production Compose definition runs `migrate --noinput` on web startup, and both services reference `DJANGO_DB_USER`.**
- Classification: VERIFIED FROM SOURCE.
- Where: `docker-compose.prod.yml` lines 32–34 (`python manage.py migrate --noinput &&` then gunicorn); line 8 (`POSTGRES_USER: ${DJANGO_DB_USER}` on the `db` service); lines 35–36 (`env_file: .env.prod` on the `web` service, which `config/settings.py` reads as `DJANGO_DB_USER`, line 121).
- Blocks: Yes. Migrations run automatically with the application's database login.

**H4b — The web container's database login equals the database bootstrap user.**
- Classification: NOT VERIFIED.
- Evidence: the two values come from different mechanisms. `${DJANGO_DB_USER}` on the `db` service is Compose variable substitution, taken from the invoking shell, the project `.env` file, or an `--env-file` argument. The `web` container receives `DJANGO_DB_USER` from `env_file: .env.prod`. They are equal only if Compose is invoked with matching values. The source cannot show how Compose is invoked, and `.env.prod` was not read.
- Next step: DBA records the login used by the deployed web container and the bootstrap role on the target (GM-12, production access required).
- Blocks: Yes.

**H5 — The bootstrap user is a superuser, and production matches the compose file.**
- Classification: NOT VERIFIED.
- Evidence: superuser creation is the official `postgres` image's documented behavior, not repository source. Production equality was not checked, and `.env.prod` was not read. If H4b holds, the web container's migrate login would be that superuser; H4b is itself NOT VERIFIED.
- Next step: DBA catalog dump of `pg_roles` for the application role on the target (GM-12, production access required).
- Blocks: Yes.

**H6 — No read-only or execution role is defined in the repository.**
- Classification: VERIFIED FROM SOURCE.
- Evidence: no `CREATE ROLE`, `GRANT`, `REVOKE`, or `ALTER ROLE` outside the audit documents.
- Blocks: Yes.

**H7 — Rev7 privilege checklist (§8) and execution-role lifecycle (§9).**
- Classification: REASONABLE DESIGN PROPOSAL.
- Blocks: Yes.

**H8 — Column-level `UPDATE` is enough for `SELECT … FOR UPDATE NOWAIT`, and `pg_control_system()` is executable by a non-superuser.**
- Classification: NOT VERIFIED.
- Evidence: PostgreSQL documentation describes the row-lock clauses as needing `UPDATE` on at least one column. That is documentation, not a run. Phase 3 §10.9 says `system_identifier` was readable by a non-superuser on the disposable server, with no retained evidence.
- Next step: T15 and the §8.3 checklist on a disposable cluster of the target major version (GM-10).
- Blocks: Yes.

**H9 — The importer and the correction share the advisory key; the lock does not cover snapshot-to-apply.**
- Classification: VERIFIED FROM SOURCE.
- Where: `import_wordpress_complete.py` 161–179 (session-level `pg_try_advisory_lock`, `pg_advisory_unlock` in `finally`); command line 88 and line 369 (transaction-level lock).
- Blocks: No. A procedural window is still required (GM-14).

**H10 — The disposable server was PostgreSQL 16 (`server_version_num` 160015), the same major version as `books-db-1`, with no route to it.**
- Classification: NOT VERIFIED.
- Where: Phase 3 §10.9.
- Evidence: no retained log, container inspect output, or network evidence is tracked.
- Blocks: Yes, for adopting any Phase 3 PostgreSQL test result.

### I. Audit durability

**I1 — Exclusive create, file-only `fsync`, no directory `fsync`, no record checksum.**
- Classification: VERIFIED FROM SOURCE.
- Where: `Outputs.reserve` 302–314 (`open('xb')` at line 310); `Outputs.write` 316–320.
- Blocks: Yes.

**I2 — `RUN_STARTED` is written with `flush()` and `os.fsync()` before the transaction; the terminal marker after.**
- Classification: VERIFIED FROM SOURCE.
- Where: `_apply` 1276–1278; `_rollback` 1347–1349; `Outputs.write` 316–320.
- Scope limit: this verifies the calls, not durability. Whether the record survives a crash or power loss is NOT VERIFIED (I4).
- Blocks: No by itself.

**I3 — If the terminal marker cannot be written after a commit, the remaining file is one that rollback accepts.** (New detail in Revision 8.)
- Classification: VERIFIED FROM SOURCE.
- Where: `_finish` 1204–1206 calls `_write_marker` with no error handling. An `OSError` (for example a full disk) propagates, nothing about the commit is printed, and the file ends at `RUN_STARTED`. E1 and E3 then let rollback restore from row values.
- Blocks: Yes.

**I4 — A returned `fsync` is not universal durability.**
- Classification: NOT VERIFIED. It is a limitation statement that depends on the operator's operating system, filesystem, and storage.
- Next step: name the operator host and storage, and test power-loss behavior or accept it formally (GM-22).
- Blocks: Yes.

**I5 — Rev7 `PRE_COMMIT`, terminal record, and `HALT` design.**
- Classification: REASONABLE DESIGN PROPOSAL.
- Where: Rev7 plan §5.2.
- Blocks: Yes.

### J. Test evidence and the 332-test result

**J1 — "The full suite ran 332 tests with 2 failures … All correction, audit, import, safety and PostgreSQL tests passed."**
- Classification: NOT VERIFIED.
- Where: Phase 3 §11. Repeated as unverified in Rev7 plan §2 and §13, and Rev7 findings §9.
- Evidence for provenance:
  - No test log, JUnit or XML result file, coverage file, or CI workflow is tracked. `.github` does not exist.
  - A static count of `def test_` methods in tracked test files at HEAD gives exactly **332**: accounts 12, api 26, cart 23, core 27, orders 36, payment 33, products/tests 42, tests_import_orders 24, tests_order_amount_audit 24, tests_order_amount_correction 34, tests_order_amount_correction_pg 14, tests_order_amount_correction_safety 37.
  - 332 equals only the static number of `def test_` definitions. The number of tests the Django test runner would collect was not derived, and no pass, fail, or skip result was established. In the three correction test files, the shared fixture classes (`CorrectionFixtureMixin`, `SafetyScenarioMixin`) define no `test_` methods; the other test files were not checked for inherited tests. The count does not show that any test ran, which tests were skipped (the PostgreSQL tests use `skipUnless(POSTGRES)`), which server was used, or what the results were.
  - The run predates the first commit of these files (A4), so the tested bytes cannot be tied to `2c3b9fd` or `90987a6`.
  - Local agent transcripts may contain the run output. They were deliberately not read (§2), and they would not be reproducible evidence anyway.
- Next step: rerun on a disposable cluster that passes GM-08, at a named commit and image digest. Retain JUnit output, the runner's identity line, and per-test skip/pass/fail status (GM-09).
- Blocks: Yes, for treating any test as evidence. A passing suite would still never authorize execution.

**J2 — Phase 3 §10.9: the real commit-time failure (23503) "gives `RUN_COMMIT_UNKNOWN`, an unchanged database, a no-op rollback, and then a successful retry."**
- Classification: CONTRADICTED BY SOURCE.
- Where: `tests_order_amount_correction_pg.py` 219–234, `test_real_commit_time_failure_is_reported_as_unknown`.
- Evidence: that test asserts the `COMMIT_UNKNOWN` message, the last status, unchanged totals, and a fresh preview with `PROPOSED` rows. It runs no rollback and no retry. The rollback-then-retry sequence is in the mocked `CommitOutcomeTest` (safety tests 393–418).
- Blocks: No. It lowers the weight of the Phase 3 test narrative.

**J3 — Commit-failure coverage is mocked; a lost acknowledgement is not exercised.**
- Classification: VERIFIED FROM SOURCE.
- Where: safety tests 393–418 patch `db.commit` to raise `OperationalError`. Django's real `rollback()` then succeeds on a live session. The PostgreSQL test (pg 219–234) uses a deferred foreign-key failure, which the server rejects; the connection stays alive. Neither drops the socket around `COMMIT`.
- Blocks: Yes (T4 is required).

**J4 — Rev7 test matrix T1–T15.**
- Classification: MISSING OR INCOMPLETE. No implementation, no tests, nothing executed.
- Where: Rev7 plan §11.
- Next step: add D3 (`InterfaceError` at commit), D4 (reconnect inside `__exit__`), C5 (xid function family and future/foreign xid), C6 and C7 (halt scoped to the target database identity; a new snapshot, preview, approval, or report path does not clear it), G4a and G4b (line-ending identity), H1 (refusal when `pg_is_in_recovery()` is true or endpoint, backend PID, or database identity differs from the signed payload), and I3 (terminal-marker write failure after commit) to the matrix.
- Blocks: Yes.

**J5 — A test asserts that `EXECUTION_ENABLED` is false.**
- Classification: VERIFIED FROM SOURCE (assertion present; not run).
- Where: `tests_order_amount_correction.py` line 518. Other tests patch it to `True` inside the test process only (lines 252, 262, 578).
- Blocks: No.

## 6. Corrections to Revision 7

Revision 7 remains a sound NO-GO record. These items must be corrected before it can be used as a design baseline:

1. **Reconnect inside `Atomic.__exit__` (D4).** Rev7 §4.7–§4.8 record that the old driver connection is closed but omit that, after a failed rollback, Django can open a new session during the same `__exit__` call. Evidence for "same connection, same PID" must be captured before `__exit__`, or the write path must not rely on `transaction.atomic()` for its outermost transaction.
2. **`InterfaceError` from `commit()` (D3).** It bypasses Django's commit-error rollback and needs its own row and test. On that path the connection is not set to `None` before `set_autocommit(True)` is attempted.
3. **xid function family (C5).** Use one consistent pair (`pg_current_xact_id` with `pg_xact_status`, or `txid_current` with `txid_status`), and treat an error result like NULL: `COMMIT_UNKNOWN` and halt.
4. **`ROLLED_BACK` path (C3).** Under the settings reviewed in D6 and assuming no pooler (D7), current code never produces `ROLLED_BACK` after a sent `COMMIT`. The real gap is the missing durable record of that fact.
5. **Identity (G4a, G4b, G5).** Line-ending normalization and commit metadata must be part of source and image identity.
6. **Docstring contradiction (E2).** The in-code docstring of `load_execution_report` contradicts its own behavior.
7. **Baseline (A1).** Review records must name `90987a6` or later.
8. **Preview is not a remedy for `COMMIT_UNKNOWN` (C6, C7).** Rev7 §5.1 says a new preview does not clear the halt. The command's message (lines 1214–1216) and Phase 3 §10.6 and §10.9 say the opposite. Rev7 §5.2 scopes the halt "for this batch". It must instead be scoped to the target database identity (`system_identifier` plus database oid), and cleared only through the recovery gate GM-24. Those identifiers define the scope; they are not endpoint authentication.

## 7. All claims not verified by this audit

These remain open. None may be treated as a passed control:

- Any historical test pass, including "332 tests, 2 failures, all correction tests passed" (J1), and the Phase 3 PostgreSQL test narrative (J2, H10).
- The disposable server's version, isolation, absence of a route to `books-db-1`, and non-superuser role (H3, H10).
- `txid_status` / `pg_xact_status` behavior and signatures on the target major version (C5).
- Real-socket behavior of commit loss, rollback failure, and the reconnect inside `__exit__` (D3, D4, J3), including whether `set_autocommit(True)` on an already-closed connection raises again and replaces the original `commit()` error (D3).
- The uncertain-outcome recovery procedure (C6, C7, gate GM-24). It is proposed only: not implemented, not rehearsed, not verified.
- Presence of an external pooler on the target path (D7).
- `system_identifier` sharing by replicas and promoted standbys (H2).
- Whether the web container's login equals the database bootstrap user (H4b); superuser status of the production application role, and production equality with `docker-compose.prod.yml` (H5).
- Commit history of `import_wordpress_complete.py`, `audit_imported_order_amounts.py`, and `products/tests_order_amount_audit.py` (A4 scope limit).
- Byte differences between images built from CRLF and LF checkouts of the same commit (G4b), and any commit metadata attached to a built image outside the repository's build definitions (G5).
- The number of tests the Django runner would collect at HEAD (J1).
- Column-level `UPDATE` sufficiency for row locks; `pg_control_system()` executability by a non-superuser (H8).
- Live roles, grants, RLS, triggers, rules, `SECURITY DEFINER` functions on the target (Rev7 §8.3, all items).
- Durability of `os.fsync` on the operator host (I4).
- Reproducible build, image digests, and package versions inside any image (G7, A5).
- Trust-anchor custody and approver independence (F5).
- Remote branch state (A2).
- Contents of `.env`, `.env.prod`, and the local agent transcripts (deliberately not read).
- Business inputs carried from Phase 3: H1 (IRR = Rial), H2 (IRHT = thousand Toman), the two anomaly WordPress ids, R4/R5/R7 decisions, the 18 large IRHT orders, and the wholesale threshold.

## 8. Work performed for this revision

- Files created: `audit_reports/KASRA_ORDER_CORRECTION_REV8_FINDINGS.md` (this file) and `audit_reports/KASRA_ORDER_CORRECTION_REV8_GATE_MATRIX.md`.
- Files modified: no implementation file and no pre-existing document was changed.
- Tests: none run. Database: none contacted. Python: not executed. Migrations, importer, correction, rollback: not run. Flags, registries, approvals, roles: unchanged. Commit, merge, push: none.

### 8.1 Documentation corrections (2026-10-13)

A read-only consistency review of these two reports identified corrections R8C-01 to R8C-15. Applying them was separately authorized as documentation-only work. Only this file and `audit_reports/KASRA_ORDER_CORRECTION_REV8_GATE_MATRIX.md` were edited.

Changes in this file:
- C6 now defines the halt scope (target database identity) and states that a new snapshot, preview, approval, or report path cannot clear it. C7 was added for the preview-as-remedy contradiction (R8C-01).
- C3 and D3 now block until the GM-03 design covers them (R8C-05). C3 and section 6 item 4 carry the D6/D7 condition (R8C-10). D3 states that the `InterfaceError` path does not set the connection to `None`; the re-raise outcome is marked NOT VERIFIED (R8C-11).
- D4 is reclassified as MISSING OR INCOMPLETE, with the specific Rev7 rows (R8C-04).
- H4 is split into H4a and H4b (R8C-07). H1 points to the GM-04 stop condition (R8C-08).
- G4 is split into G4a and G4b; G5 is reworded (R8C-12). G7 points to the GM-07 requirement (R8C-06).
- I2 wording no longer asserts durability (R8C-13).
- Section 2, A4, and J1 provenance wording are corrected (R8C-14).

These corrections were made from the documents and the source cited in them. No test, database command, or Python ran for them. They close no gate and authorize nothing.

**Final status: NO-GO — NO EXECUTION AUTHORIZED.** This document records findings only. It does not satisfy any gate, and completing or correcting it is not execution approval.
