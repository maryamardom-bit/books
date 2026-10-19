# Kasra order-correction — Revision 8 gate matrix

Status: **NO-GO — NO EXECUTION AUTHORIZED.**

This matrix lists every prerequisite that must be independently closed before any execution of `correct_imported_order_amounts --apply` or `--rollback` could be considered. It is derived from the Revision 7 plan (§12, §15), the Phase 3 checklist (G1–G18), and the Revision 8 findings (`audit_reports/KASRA_ORDER_CORRECTION_REV8_FINDINGS.md`, cited below as "F8 <id>").

Reviewed baseline: `90987a6cd10a0671aebede477c9fe29754a44669` on `cursor/payment-hardening-and-architecture-review`, clean tree.

Every mechanism named in an evidence requirement below is a requirement for future work. Unless a row says otherwise, none of it exists in the current code or has been verified.

## Rules

1. A gate closes only on retained evidence that the named verifier has checked, recorded in the format in "Evidence record format". A statement in a plan, a passing review, or a test claim without a retained log does not close a gate.
2. A gate cannot close while any gate it depends on is open.
3. Any code change reopens GM-01 and every gate whose evidence names the old commit, source manifest, or image digest.
4. The verifier must not be the person who produced the evidence. "Operator" means the person who would run the command.
5. Closing GM-01 to GM-10 never authorizes execution. Execution additionally requires GM-11 to GM-20, GM-22, GM-23, and, where a halt exists for the target database identity, GM-24. GM-18 is the only gate that grants a time-bounded authorization.
6. Hitting a stop condition keeps the whole matrix at NO-GO. No owner instruction overrides a stop condition.
7. Writing, reviewing, or correcting these documents closes no gate.

## Evidence record format

Each gate-closure record must contain:

- the gate ID;
- the named verifier and the named evidence producer (different people, per Rule 4);
- the date, and the commit the evidence refers to;
- the path of every evidence file, with its SHA-256;
- the storage location of the record and evidence, which must be one the operator cannot modify;
- a verifier-authenticated record mechanism. Until GM-06 delivers the authorization signing scheme, an interim mechanism must be chosen and recorded. A signed Git tag created by the verifier is one **proposal** for that interim mechanism. It is not an existing control, and no such tag exists.

No verifier, evidence producer, storage location, signing key, or record has been named or created. Those are decisions for the owners listed in each row.

For GM-09, the list of permitted test skips must be written and approved by the GM-09 verifier **before** any future run. A skip not on that list is a stop condition.

## Matrix

"Without production access" means the gate can be fully verified with no connection to, credential for, or backup of the production or development database.

| ID | Prerequisite | Evidence requirement | Independent verifier | Depends on | Stop condition | Without production access | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GM-01 | Reviewed baseline pinned | `git rev-parse HEAD`, branch, clean `git status`, ancestry, and changed-file list recorded for the commit under review | Reviewer who did not author the change | none | HEAD, branch, or file list differs from the record; dirty tree | Yes | **Open.** The baseline was recorded by the Revision 8 author (F8 §1). It awaits independent verification. |
| GM-02 | Independent review of Rev7 and Rev8 | Review record naming `90987a6` (or later), dispositioning every Rev8 claim A1–J5, in the evidence record format | Engineer who did not write Rev7, Rev8, or the command | GM-01 | Any CONTRADICTED or MISSING item left without a disposition | Yes | Open |
| GM-03 | Corrected transaction-outcome design | Revised design covering: reconnect inside `Atomic.__exit__` (F8 D4), `InterfaceError` at commit (F8 D3), one consistent xid function family and error-as-unknown (F8 C5), durable "COMMIT not sent" record (F8 C3), halt latch scoped to the target database identity and not clearable by a new snapshot, preview, approval, or report path (F8 C6, C7) | Reviewer from GM-02 plus a DBA | GM-02 | Design still infers outcome from exceptions; reads "same connection" evidence after `__exit__`; scopes the halt to a batch; or lets a preview clear a halt | Yes | Open |
| GM-04 | Outcome evidence and environment identity implemented | Code that captures xid, backend PID, driver identity, recovery state, and endpoint inside the transaction; durable `PRE_COMMIT` before `COMMIT`; terminal record; `HALT` keyed to `system_identifier` plus database oid and honored by every later apply and rollback against that identity. The current code does none of this (F8 C2, H1). | Code reviewer not the implementer | GM-03 | Any path labels `COMMITTED` without status confirmation of a recorded xid; any write after `COMMIT_UNKNOWN`; a halt clearable by a new snapshot, preview, approval, or report path; a write proceeds when `pg_is_in_recovery()` is true, or when the endpoint, backend PID, or database identity differs from the signed authorization payload (F8 H1) | Yes | Open |
| GM-05 | Rollback hardening | Rollback refuses reports ending at `RUN_STARTED` or `RUN_COMMIT_UNKNOWN` (F8 E1–E3); docstring fixed (F8 E2); separate rollback authorization and per-order reconciliation (Rev7 §10); terminal-marker write failure handled (F8 I3); rollback honors the GM-04 halt | Code reviewer not the implementer | GM-03, GM-04, GM-06 | Any rollback write possible from an incomplete or unknown-outcome report, with the apply approval, or while a halt exists | Yes | Open |
| GM-06 | Authorization design and trust anchor | Security-owner decision on algorithm, key custody, trust-anchor location, revocation publisher, nonce-ledger storage; implementation of Rev7 §6 checks | Security owner (decision); code reviewer (implementation) | GM-02 | Authorization still satisfiable by editing source or a JSON file; operator can modify the trust anchor; nonce not consumed before data change | Yes | Open |
| GM-07 | Source, build, and image identity | Normalized source manifest (line-ending policy via `.gitattributes`, F8 G4a, G4b); hashed lockfile (F8 G2); digest-pinned base images (F8 G3); commit and manifest recorded as image metadata (F8 G5); measured registry digest; and **either** an independent rebuild yielding the same digest **or** a recorded security-owner acceptance of a non-reproducible but digest-pinned image (F8 G7) | Release owner, not the operator; security owner for any acceptance | GM-01 | Same commit yields different manifests on two builders; tag instead of digest; missing lockfile hashes; neither a matching independent rebuild nor a recorded security-owner acceptance exists | Yes | Open |
| GM-08 | Disposable-environment isolation proof | Network evidence (separate network, no route, firewall rules) to every real database; disposable server `system_identifier` recorded and confirmed different from the real systems by a DBA; non-superuser role catalog dump | DBA | GM-01 | Any route to a real database; identity matches a real system; test role is a superuser; reliance on the host-name denylist or `cluster_name` alone (F8 H3) | Partly. Setup and network evidence need no database access. Comparing against the real systems' `system_identifier` values needs a DBA who already holds them. | Open |
| GM-09 | Reproducible test evidence | At a named commit and image digest: full-suite JUnit output with per-test pass/skip/fail, runner identity line, PostgreSQL version; the permitted skip list approved before the run; Rev7 T1–T15 plus Rev8 additions (F8 J4) with retained statement logs and audit files | Reviewer not the implementer | GM-04, GM-05, GM-06, GM-07, GM-08 | Any failure; any skip not on the pre-approved list; missing log; evidence from a different commit or digest. Replaces the unverified "332 tests" claim (F8 J1). | Yes | Open |
| GM-10 | Privilege model proven on disposable cluster | Rev7 §8.3 checklist output for read-only and execution roles on the target major version, including `FOR UPDATE` under column grants and `pg_control_system()` access (F8 H8) | DBA, not the operator | GM-08 | Any write path beyond `orders.total_price`; role can disable `default_transaction_read_only` and write; any superuser or inherited privilege | Yes | Open |
| GM-11 | Target endpoint and identity | Named target environment; endpoint (host, port), pooler presence (F8 D7), `system_identifier`, database oid, `pg_is_in_recovery() = false`, server version | DBA and business owner | GM-02 | Target not named; pooler unknown; endpoint can resolve to a replica or another cluster | No | Open |
| GM-12 | Production role and credential lifecycle | Catalog dump showing the execution role absent or `NOLOGIN`, zero grants and memberships; the deployed web container's login and the bootstrap role recorded (F8 H4a, H4b, H5); application/migrate role not superuser, or a superuser exception approved by the DBA and security owner; credential store access list | DBA and security owner | GM-10, GM-11 | Any usable write login exists before GM-18; migrate role inherits the execution role; application/migrate role is superuser without an approved exception. Any exception is a future decision; none exists. | No | Open |
| GM-13 | Owner business decisions | Recorded owner decisions with settlement evidence: H1, H2, R4, R5, R7, rounding, the 18 large IRHT orders, wholesale threshold, the two anomaly WordPress ids (Phase 3 G1–G3, G13, G17) | Business owner; checked by a second person against the evidence | None for the decisions themselves; GM-11 for the anomaly-id check against the target | Any decision inferred rather than supplied; ids guessed | Partly. Decisions need no database access; checking the anomaly ids against the target does. | Open |
| GM-14 | Importer and concurrency window | Importer non-overwrite behavior proven in GM-09; agreed maintenance window with no importer, admin bulk action, or payment activity (Phase 3 G5, G10) | Operations owner | GM-09 | Window not agreed; importer scheduled; payments enabled | Partly. Code behavior yes; the window needs production operations. | Open |
| GM-15 | Target schema state | `orders 0008` and `payment 0001` applied to the target through the approved deployment process (Phase 3 G15) | Release owner | GM-07, GM-11 | Pending migrations on target; migrations applied by the correction operator | No | Open |
| GM-16 | Backup and restore rehearsal | Backup identity and hash; restore onto a disposable target; fingerprint match; apply-then-rollback rehearsal on the restore (Phase 3 G7, G11, G18) | DBA | GM-11, GM-15 | Fingerprint mismatch; restore not rehearsed; backup taken before the final schema state | No | Open |
| GM-17 | Fresh snapshot and preview on target | Read-only snapshot and preview with the read-only role; hashes bound to GM-07 identities and GM-11 identity; reconciliation equals Phase 2 counts (Phase 3 G8, G9) | Second person re-checks hashes | GM-10, GM-11, GM-12, GM-13, GM-14, GM-15, GM-16 | Conflicts, fingerprint drift, identity mismatch, any blocker other than the disabled-execution ones, or a halt in force for the target database identity | No | Open |
| GM-18 | Signed execution authorization | Signed apply payload per Rev7 §6.2 with unused nonce, window, revocation generation; credential released by a second person inside the window; reviewed change enabling execution for this run only (Phase 3 G14, G16) | Approver who is not the operator, plus DBA | GM-01 to GM-17, GM-22, GM-23; and GM-24 if a halt exists for the target database identity | Expired, revoked, replayed, or mismatched payload; credential released early; execution enabled without a signed payload; a halt in force for the target database identity | No | Open |
| GM-19 | Execution with outcome evidence | Durable `PRE_COMMIT`; status of the recorded xid confirmed `committed`; terminal record; credential revoked after the run | Second person observing; DBA for revocation | GM-18 | Any `COMMIT_UNKNOWN`, NULL or error status, endpoint change, or audit write failure: halt with no retry. Only GM-24 can clear that halt. | No | Open |
| GM-20 | Post-execution reconciliation | Read-only per-order comparison to the signed post-state; non-target fingerprint unchanged | Second person | GM-19 with `COMMITTED` evidence | Any mismatch: halt, no "fix forward" | No | Open |
| GM-21 | Rollback authorization (only if needed) | Separate signed rollback payload and fresh reconciliation record (Rev7 §10.2–§10.3) | New approver action, not the operator | GM-05; and GM-20 when the apply outcome is `COMMITTED`, or GM-24 when the apply outcome is unknown | Apply outcome unknown and GM-24 not closed, report incomplete, or any order in an unexpected state: no rollback write | No | Open |
| GM-22 | Audit storage durability | Named operator host and storage; directory and file sync behavior documented or tested; acceptance of residual risk recorded (F8 I1, I4) | Security owner or platform owner | GM-04 | Audit directory on network or volatile storage without accepted risk | Yes. Needs the operator host, not database access. | Open |
| GM-23 | Credential exposure remediation | Phase 3 §6 rotations completed or explicitly waived; production `SECRET_KEY` confirmed distinct (Phase 3 G12) | Security owner | none | Exposed credentials still valid on any system the run touches, without a recorded waiver | No | Open |
| GM-24 | Uncertain-outcome recovery | A recorded halt for the target database identity (`system_identifier` plus database oid). **Either** (a) the durably recorded xid, re-identification of the primary (approved endpoint, `system_identifier`, database oid, `pg_is_in_recovery() = false`), and its transaction-status result from one consistent function family (F8 C5), **or** (b) a separately authorized restore that was rehearsed under GM-16, with a matching fingerprint. A new snapshot, preview, approval, or report path is never evidence for this gate (F8 C6, C7). This procedure is proposed only: not implemented, not rehearsed, not verified. | Independent DBA, plus an approver who is not the operator | GM-19 (halt recorded); GM-04 (recording mechanism); GM-16 for path (b) | Missing transaction id; NULL, error, or `in progress` status; uncertain endpoint or recovery state; conflicting evidence; an unrehearsed or unauthorized restore. In each case the halt stays in force. `system_identifier` and database oid alone are not endpoint authentication (F8 H1, H2). | No | Open |

## Dependency order

Design and code track: GM-01 → GM-02 → GM-03 → GM-04 and GM-06 → GM-05 (GM-05 depends on GM-03, GM-04, and GM-06).

Identity and isolation track, which can start once GM-01 is closed: GM-07 and GM-08. GM-10 follows GM-08.

Both tracks join at GM-09, which depends on GM-04, GM-05, GM-06, GM-07, and GM-08.

Target track: GM-11 depends only on GM-02 and may proceed in parallel with GM-03 to GM-10, but under this revision it may not be started (it needs production access). GM-12 depends on GM-10 and GM-11. GM-15 depends on GM-07 and GM-11. GM-16 depends on GM-11 and GM-15.

Convergence: GM-17 depends on GM-10, GM-11, GM-12, GM-13, GM-14, GM-15, and GM-16. Then GM-18 → GM-19 → GM-20 → GM-21 (only if needed).

Parallel gates:
- GM-13: no prerequisite for the decisions; GM-11 for the anomaly-id check. Must close before GM-17.
- GM-14: depends on GM-09. Must close before GM-17.
- GM-22: depends on GM-04. Must close before GM-18.
- GM-23: no prerequisite. Must close before GM-18.

Recovery: GM-24 applies only after a halt (GM-19 stop condition). GM-18 requires GM-24 to be closed when a halt exists for the target database identity. GM-21 requires GM-24 when the apply outcome is unknown.

## Current position

- Closed: none.
- Open: GM-01 through GM-24, including GM-24 (uncertain-outcome recovery).
- Fully verifiable without production access: GM-01 to GM-07, GM-09, GM-10, and GM-22.
- Partly verifiable without production access: GM-08, GM-13, and GM-14.
- Need production access: GM-11, GM-12, GM-15 to GM-21, GM-23, and GM-24. None of them may be started under this revision.
- None of these gates, open or closed, can authorize execution except GM-18 after every gate it depends on is closed.

**Final status: NO-GO — NO EXECUTION AUTHORIZED.** This matrix is not an approval. Completing or correcting this document closes no gate.
