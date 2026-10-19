# Kasra Publishing — Remediation Blueprint (Complete)

**Status: `NO-GO — NO EXECUTION AUTHORIZED`**

| Final status field | Value |
| --- | --- |
| Commercial release | `NO-GO` |
| Historical-order correction | `NO-GO` |
| Execution authorization | `NONE` |
| S4 gates closed by this document | `NONE` |

**Document type:** Planning and analysis only. Completing or consolidating this document does not authorize code edits, migrations, database access or modification, Git operations, test execution, package installation, secrets inspection, deployment, rollback, restoration, importer execution, historical order correction, payment enablement, production cutover, or production changes. Authorization Boundaries A–E are each separate; none are granted here.

**Evidence labels (mandatory):**
| Label | Meaning |
| --- | --- |
| **REPORTED** | Claim taken from a supplied audit report; not re-proven as current HEAD truth by this document |
| **NOT VERIFIED** | Cannot be confirmed without a separately authorized inspection, run, owner statement, or external system |
| **PROPOSED** | Remediation design suggestion; not implemented and not a control |
| **OWNER DECISION REQUIRED** | Must be supplied by the owner; must not be guessed |

**Established owner decisions (accepted inputs to this blueprint):**
1. Document and confirm the store’s monetary unit and SEP’s expected gateway unit before payment release.
2. Implement shipping charges before commercial release. Do not invent shipping rates or rules.
3. Keep the existing domain and preserve legacy URLs and SEO.
4. Run database migrations as a separate operation, only after a verified backup and separate explicit approval.

**Workstream separation:** Workstream A = commercial release remediation. Workstream B = historical imported-order amount correction/recovery. They must not share authorization, runbooks, or release gates. Historical correction is not part of go-live.

**Primary supplied sources:**
- `audit_reports/WORDPRESS_DJANGO_FEATURE_GAP_AUDIT.md`
- `audit_reports/P0_2_PHASE1_CURRENCY_CONVERTER_RECONCILIATION.md`
- `audit_reports/P0_2_PHASE2_READ_ONLY_RECONCILIATION.md`
- `audit_reports/P0_2_PHASE3_CORRECTION_PLAN.md`
- `audit_reports/KASRA_ORDER_CORRECTION_REV8_FINDINGS.md`
- `audit_reports/KASRA_ORDER_CORRECTION_REV8_GATE_MATRIX.md`

**Baseline note:** Rev8 recorded inspected commit `90987a6` on branch `cursor/payment-hardening-and-architecture-review`. Feature-gap audit dated 2026-10-11. This blueprint does **not** claim those baselines equal any current working tree. Past audit “VERIFIED” / “test passed” labels are **REPORTED** prior claims, not retained evidence for this document (Rev8 J1: no claim reached “VERIFIED FROM EXISTING REPRODUCIBLE EVIDENCE”). This consolidation revision does **not** independently reverify the current repository, runtime, database, payment gateway, backup, or server configuration; historical audit findings remain labelled **REPORTED** (previously reported), not independently reverified.

---

## Authorization Boundaries

Each of the following is a **separate** authorization boundary. Authorization for one boundary must **never** imply authorization for another. Every authorization must identify, in writing: **scope**, **environment**, **target version or image**, **time window**, and **approver**. No authorization under any boundary is granted by this document.

| ID | Boundary | What it covers (planning definition only) | Current authorization |
| --- | --- | --- | --- |
| **A** | Non-production testing | Non-prod test runs, disposable DB exercises, mocked or sandbox payment drills, staging dress rehearsals that do not touch production data or traffic | **NONE** |
| **B** | Production migration | Production (or production-bound) schema migrate as a separate operation after verified backup; never via web start (see R-07; owner decision 4) | **NONE** |
| **C** | Payment enablement | Enabling live customer payment / SEP production credentials or traffic that can capture real funds | **NONE** |
| **D** | Production cutover | DNS/traffic cutover, production TLS go-live, public commercial release switch | **NONE** |
| **E** | Historical-order correction (Workstream B) | Any `correct_imported_order_amounts` preview against production, `--apply`, rollback, or related recovery under Rev8 GM-18+ | **NONE** |

### Separate-authorization rule

- Closing a planning finding, accepting a PROPOSED design, or completing documentation does **not** authorize A, B, C, D, or E.
- Closing one S4 gate (see Independent-Review Record) does **not** authorize B, C, D, or E; does **not** close dependent or sibling gates by implication; and does **not** authorize Workstream B.
- Boundary A (non-prod testing) does **not** authorize C (payment enablement) or D (cutover).
- Boundary B (production migration) does **not** authorize C, D, or E.
- Boundary C does **not** authorize D or E.
- Boundary D does **not** authorize E.
- Boundary E remains isolated from Workstream A release gates (R-12).

**No waiver is currently granted** under any boundary (see Waiver rule below).

---

## Section 0 — Owner contracts inventory (blocking inputs)

This section completes the owner-evidence collection **as a planning checklist**. No owner answers are invented.

### 0.1 Monetary / SEP unit contract — OWNER DECISION REQUIRED (decision 1)

| Item | Status | Notes from supplied reports |
| --- | --- | --- |
| Store application unit | **REPORTED** Phase 3 §1.1: app models/comments treat checkout, order total, payment amount as Toman; gateway uses `PAYMENT_AMOUNT_MULTIPLIER` default 10 (Toman→Rial) | **NOT VERIFIED** against current settings module or live SEP terminal |
| Hypothesis H1: IRR = Rial | **REPORTED** Phase 3: strong hypothesis, not bank/SEP-confirmed | **OWNER DECISION REQUIRED** with settlement sample |
| Hypothesis H2: IRHT = thousand Toman | **REPORTED** Phase 3: hypothesis, unverified; rules depending on H2 **BLOCKED** | **OWNER DECISION REQUIRED** |
| Currency switch date ~2026-04 | **REPORTED** Phase 3 H3: data boundary only | **OWNER DECISION REQUIRED** |
| SEP expected gateway unit | **REPORTED** feature-gap T-05 text assumes total×10 for SEP; Phase 3 notes order notes cannot reveal gateway unit | **OWNER DECISION REQUIRED** with gateway docs or settlement |

**Evidence artifact required before payment release (PROPOSED):** signed one-page contract naming store unit, gateway unit, formula, rounding, and sample settlement IDs. Without it, R-01 remains open.

### 0.2 Shipping rates and rules — OWNER DECISION REQUIRED (decision 2)

| Item | Status |
| --- | --- |
| Live methods (post, express, courier, Tipax, flat, free) | **REPORTED** feature-gap B.2 / CC-08 counts from export |
| Current rates, free threshold, region/weight rules | **NOT VERIFIED** (feature-gap J-2: WP admin not inspected) |
| Product weight units for `_weight` | **NOT VERIFIED** |

**Do not invent rates.** Implementation of R-05 is blocked until owner supplies current WooCommerce shipping settings (or a written replacement schedule).

### 0.3 Coupon launch policy — OWNER DECISION REQUIRED

| Option | Meaning |
| --- | --- |
| **A** | Do not activate migrated restricted coupons until rule parity exists |
| **B** | Implement listed restriction rules before enabling any migrated coupon |

No “safe subset” may be guessed. Smart Coupons store-credit (1,167 **REPORTED**) fate is also **OWNER DECISION REQUIRED**.

### 0.4 Guest checkout / bank transfer / installment — OWNER DECISION REQUIRED

| Item | Status |
| --- | --- |
| Guest checkout day-one vs post-launch | **OWNER DECISION REQUIRED** (58% historical guest orders **REPORTED**) |
| Bank transfer day-one vs post-launch | **OWNER DECISION REQUIRED** (~31% historical bacs **REPORTED**); instructions text **NOT VERIFIED** (J-3) |
| Installment | Feature-gap recommends hide until real; still **OWNER DECISION REQUIRED** to confirm hide-at-launch |

### 0.5 TLS termination / domain — OWNER DECISION REQUIRED (decision 3)

| Item | Status |
| --- | --- |
| Keep existing domain | **Established** (decision 3) |
| Exact hostname list | **OWNER DECISION REQUIRED** (feature-gap cites `kasrapublishing.ir` as live) |
| TLS terminates at: in-compose Nginx / host proxy / CDN | **OWNER DECISION REQUIRED** |
| Cert issuer and renewal owner | **OWNER DECISION REQUIRED** |
| Live cert expiry at audit time | **REPORTED** expired Let’s Encrypt E7; **NOT VERIFIED** as of this document’s date |

### 0.6 Backup / monitoring / migrate approver — OWNER DECISION REQUIRED (decision 4)

| Item | Status |
| --- | --- |
| RPO / RTO | **OWNER DECISION REQUIRED** |
| Backup storage location and restore operator | **OWNER DECISION REQUIRED** |
| Monitoring product / alert route | **OWNER DECISION REQUIRED** |
| Who approves migrate after backup | **OWNER DECISION REQUIRED** (decision 4 process) |

### 0.7 Owner-contracts completion criteria (planning)

This todo is **complete as a planning inventory** when the checklist above is recorded. It is **not** complete as a release gate until owner-signed answers exist. Gates remain open.

---

## Finding R-01 — Payment units and SEP amount conversion

### Finding ID and severity
- **IDs:** DM-01; Phase 1–3 currency work; Phase 3 §1.1 gateway multiplier; feature-gap T-05 acceptance note.
- **Severity:** **P0** — blocks payment release.

### Reported source evidence (REPORTED)
- Importer copies `_order_total` with `int(float(...))` and ignores `_order_currency` (feature-gap DM-01; Phase 3 cites `import_wordpress_complete.py:311`).
- Export currencies: IRR majority; IRHT for 90 orders in 2026 (feature-gap B.2; Phase 2/3).
- Phase 1 provisional factors: IRR ÷ 10, IRHT × 1000 — explicitly temporary/unconfirmed.
- Phase 3 §1.1: application treats amounts as Toman; `PAYMENT_AMOUNT_MULTIPLIER` default 10 converts to Rial for SEP initiate/verify comparison.
- Feature-gap T-05 acceptance text: “SEP amount equals that × 10”.

### Unverified assumptions (NOT VERIFIED)
- Live WooCommerce `woocommerce_currency` history and current setting.
- SEP terminal’s actual expected unit for this merchant.
- Whether current HEAD still uses multiplier 10 and Toman labels consistently.
- Phase 2 “expected Toman” aggregates (conditional on unconfirmed H1/H2).
- H2 (IRHT = thousand Toman) — Phase 3 marks rules depending on H2 as **BLOCKED**.

### Required owner decisions (OWNER DECISION REQUIRED)
- Confirm store unit and SEP gateway unit with settlement evidence (established decision 1).
- Confirm or reject H1 and H2; provide IRHT change date if known.
- Rounding rule when amounts are not divisible (Phase 3 cites one IRR order not divisible by 10 for historical work — keep out of release payment path via R-04).

### Proposed remediation (PROPOSED)
1. Record a signed monetary-unit contract (store unit, gateway unit, formula, rounding).
2. Single conversion helper used only at gateway request and verify boundaries.
3. Keep catalog/order/`Payment.amount` in the documented store unit.
4. Do **not** treat historical imported total correction as the payment-release fix; use R-04 to block repayment of imported orders.
5. Native checkout amounts follow the contract independently of Workstream B.

### Acceptance criteria
- Written contract on file.
- Staging/sandbox SEP initiate and verify amounts match the contract for a known cart total.
- Amount-mismatch tests use the contracted conversion.
- No production payment enablement without the contract.

### Required tests and dependencies
- **Tests (non-prod, needs separate auth):** unit tests for conversion/rounding; mocked SEP request body amount; mocked verify comparison; authorized SEP sandbox smoke.
- **Depends on:** owner decision 1 / Section 0.1.
- **Release impact:** blocks payment go-live.
- **Independent of:** Workstream B `--apply`.

### Separate authorization required?
**Yes** — for any code change, sandbox payment, or production payment enablement.

---

## Finding R-02 — Callback replay, concurrency, amount mismatch, reversal failure, multiple pending payments

### Finding ID and severity
- **IDs:** PO-01, PO-02, PO-03, PO-04, PO-21; feature-gap §F edge cases.
- **Severity:** **P0/P1** for payment resilience before release.

### Reported source evidence (REPORTED)
- Feature-gap: SEP callback reference-matched; idempotent replay; duplicate `transaction_id` rejected; verify amount check with reversal on mismatch; verify timeout keeps payment pending; last-copy row lock (`test_callback_replay_is_idempotent`, `test_duplicate_transaction_id_rejected`, `test_amount_mismatch_is_rejected_and_reversed`, `test_verify_timeout_keeps_payment_pending_for_retry`, `test_last_copy_sold_once`).
- Feature-gap status for those items was “VERIFIED” **with gateway mocked** during that audit.
- PO-21 PARTIAL: `used_count` incremented after payment without re-checking `max_uses` under concurrency.
- PO-01: real SEP terminal untested at feature-gap time.

### Unverified assumptions (NOT VERIFIED)
- Those tests were not re-run for this blueprint; Rev8 J1: historical suite claims lack retained JUnit/logs; “332 tests” is only a static `def test_` count at Rev8 baseline.
- Concurrent double-callback under real DB locking.
- Reverse-API failure after amount mismatch (fail-closed vs partial complete).
- Multiple `PENDING` payments per order under retry paths.
- Real SEP sandbox behaviour.

### Required owner decisions (OWNER DECISION REQUIRED)
- Policy when reverse fails after mismatch (halt completion + escalate vs retry reverse).
- Policy for multiple pending payments / unpaid retry (keep, coalesce, or expire).
- Whether unpaid auto-cancel (PO-14) is required at launch (**NOT VERIFIED** on live hold-stock setting).

### Proposed remediation (PROPOSED)
1. Re-verify payment invariants at a **named commit** with **retained** JUnit: one PAID per order; callback idempotency; amount mismatch → reverse → non-paid; reverse failure → fail-closed; concurrent callback/stock.
2. Add explicit reverse-failure and multi-pending cases if missing from suite.
3. Harden coupon usage atomicity (PO-21) if coupons are enabled at launch (see R-09).
4. Map each invariant to an SEP sandbox checklist item.

### Acceptance criteria
- Retained non-prod evidence for replay, concurrency, mismatch, reverse-failure, multi-pending.
- SEP sandbox checklist executed under separate auth with logs retained.
- No payment gate marked passed without artifacts.
- Expected-outcome matrix below satisfied for every scenario, with retained evidence identifiers.

### R-02 expected-outcome matrix (planning; not executed)

Outcomes below are **PROPOSED / REPORTED** invariants for validation planning. They are **not** proof that current HEAD or any runtime already behaves this way (**NOT VERIFIED** by this document). Recovery procedures that lack an owner-approved runbook are marked **OWNER DECISION REQUIRED** — this document does **not** invent recovery procedures.

| Scenario | Expected payment status | Expected order status | Fulfillment prevention behavior | Evidence required | Owner-approved recovery procedure |
| --- | --- | --- | --- | --- | --- |
| **Callback replay** | After a successful first callback: replay must leave exactly one successful/PAID payment for that order intent; duplicate callback must not create a second PAID payment (idempotent / rejected duplicate) — **REPORTED** feature-gap intent; **NOT VERIFIED** now | Order must remain in the post-success paid/fulfillable state from the first success only; replay must not create a second paid order or regress a completed payment to unpaid without an explicit authorized recovery path | Fulfillment may proceed only from the single successful payment outcome; replay must not trigger a second fulfill/ship/stock-decrement cycle | Retained non-prod (Boundary **A**) logs + DB snapshots: first callback result, replay request/response, payment row count/status, order status, stock delta; named commit/image; test id/JUnit or equivalent digest | **OWNER DECISION REQUIRED** |
| **Concurrent callbacks** | Under concurrent duplicate callbacks for the same payment intent: at most one payment reaches PAID/success; losers remain non-paid / rejected / pending per implemented fail-closed rules — **PROPOSED**; **NOT VERIFIED** under real DB locking | At most one order transition to paid for that intent; no double-paid order pair from the race | Stock/fulfillment decrements at most once; concurrent loser must not fulfill | Concurrent test harness output + DB lock/transaction evidence retained; payment/order/stock before/after; named commit/image | **OWNER DECISION REQUIRED** |
| **Amount mismatch** | Payment must **not** remain successfully PAID when verify amount mismatches contracted expected amount; mismatch path must attempt reversal and leave payment non-paid / failed / reversed per design — **REPORTED** feature-gap intent; **NOT VERIFIED** now | Order must **not** be treated as paid/ready-to-fulfill solely from a mismatched callback | Fulfillment must be blocked while payment is non-paid after mismatch; no ship/download release on mismatch success | Mocked/sandbox verify mismatch case logs; reverse request evidence; final payment + order status; amount fields vs R-01 contract; named commit/image | **OWNER DECISION REQUIRED** |
| **Payment reversal failure** | If reverse API fails after mismatch (or equivalent reverse-required path): system must **fail closed** — payment must not be left as successfully PAID; escalation/hold state must be observable — **PROPOSED**; exact hold statuses **OWNER DECISION REQUIRED** for naming | Order must not be fulfillable as paid while reverse failure is unresolved | Fulfillment prevented until an owner-approved recovery resolves the hold | Reverse-failure injection evidence; final payment/order status; alert/escalation artifact if monitoring exists; named commit/image | **OWNER DECISION REQUIRED** (includes halt-vs-retry-reverse policy already listed above) |
| **Multiple pending payments** | Behavior when multiple `PENDING` payments exist for one order under retry: coalesce / expire / keep — **OWNER DECISION REQUIRED**; until decided, expected terminal payment status set is **NOT** fixed by this document. Invariant that must still hold once any path succeeds: **at most one PAID** payment per order intent (**PROPOSED**) | Order paid transition only from the single successful payment; abandoned pendings must not flip the order to paid | Fulfillment only after the single successful paid outcome; pending-only orders must not fulfill | Multi-pending create/pay test evidence; enumeration of payment rows per order; final statuses; named commit/image | **OWNER DECISION REQUIRED** |

### Required tests and dependencies
- **Tests:** payment suite re-run at named commit + digest; reverse-failure; concurrent callbacks; multi-pending create/pay; optional PO-21 concurrent coupon.
- **Depends on:** R-01 contract (amounts meaningful only after unit contract).
- **Release impact:** blocks payment release.
- **Authorization:** Boundary **A** for non-prod evidence; Boundary **C** separately for any live payment enablement — neither granted here.

### Separate authorization required?
**Yes** — test runs, code changes, and sandbox exercises (Boundary **A** at minimum; **C** never implied).

---

## Finding R-03 — Duplicate order submission and idempotency

### Finding ID and severity
- **IDs:** feature-gap §F “Duplicate order submission”; PO-14.
- **Severity:** **P1**.

### Reported source evidence (REPORTED)
- Each checkout POST creates a new `PENDING_PAYMENT` order; cart cleared after first submit so second submit hits empty cart (`orders/views.py:114` cited in feature-gap).
- Unpaid duplicates can accumulate; assessment “Acceptable” at audit time, with PO-14 unpaid expiry unverified.

### Unverified assumptions (NOT VERIFIED)
- Double-submit before cart clear (slow network / double-click).
- Browser back/resubmit; API clients.
- Live WooCommerce hold-stock / unpaid cancel behaviour (PO-14 / J-5).

### Required owner decisions (OWNER DECISION REQUIRED)
- Accept accumulate-and-pay-from-history, **or** require single open pending order / idempotency key per user+cart fingerprint.
- Unpaid expiry policy and TTL if any.

### Proposed remediation (PROPOSED)
1. Record chosen policy in the release runbook.
2. If tighten: refuse second create while unpaid order exists for same user/session cart hash; redirect to pay-existing.
3. Optional scheduled cancel of stale pendings only after owner confirms live behaviour.
4. Ensure R-02 one-PAID rule still prevents double charge even if duplicate orders exist.

### Acceptance criteria
- Policy recorded and signed.
- Automated double-POST test matches policy.
- No path charges twice for one customer intent (ties to R-02).

### Required tests and dependencies
- **Tests:** double-submit integration; pay-from-history; optional expiry dry-run in non-prod.
- **Depends on:** soft dependency on R-02; not a substitute for R-04.
- **Release impact:** conversion/support risk if left loose; not a substitute for P0 monetary/shipping/TLS.

### Separate authorization required?
**Yes** for implementation and tests.

---

## Finding R-04 — Imported-order payability and historical totals (Workstream A safety; Workstream B separate)

### Finding ID and severity
- **IDs:** DM-01, DM-02, DM-03 (feature-gap P0); Phase 2/3; Rev8 Workstream B / GM-*.
- **Severity:** **P0** for commercial release safety. Correction `--apply` remains Workstream B **NO-GO**.

### Reported source evidence (REPORTED)
- DM-03: cancelled 212 + on-hold 64 imports keep default `PENDING_PAYMENT`; order history shows Pay; migration 0008 back-filled PAID only for paid orders; refunded imported as paid.
- DM-01: unconverted totals → wrong re-payment amount.
- DM-02: WXR has no line items → empty shells.
- Phase 2: read-only reconciliation with provisional factors; NO-GO for stored amount correction.
- Rev8: `EXECUTION_ENABLED = False`; empty approvals; GM-01–GM-24 all **Open**; J1 historical tests **NOT VERIFIED**; C7 preview-as-remedy **CONTRADICTED BY SOURCE**.

### Unverified assumptions (NOT VERIFIED)
- Current DB contents of any environment.
- Whether Pay UI/endpoints still expose imported orders at current HEAD.
- Rev8 A4 scope: first-commit history of some importer/audit files.
- GM-13 business inputs (H1, H2, R4, R5, R7, anomalies, wholesale threshold).

### Required owner decisions (OWNER DECISION REQUIRED)
- **Release path:** confirm archival / non-payable policy for all imported orders (block Pay without correcting amounts).
- **DM-02:** import line items from WP DB dump **or** label historical orders archival/read-only.
- **Workstream B only (later, do not guess):** H1, H2, R4, R5, R7, anomaly WordPress ids, wholesale threshold, rounding.

### Proposed remediation (PROPOSED) — release path only
1. Mark imported orders non-payable (explicit flag and/or correct status mapping).
2. Payment process endpoint refuses imported/historical non-payable orders.
3. Hide Pay button in order history for those orders.
4. If no line items: archival labelling in UI.
5. **Do not** run `correct_imported_order_amounts --apply` for release.
6. Workstream B continues under Rev8 gate matrix only (see R-12).

### Acceptance criteria (release)
- No imported order offers Pay.
- Payment process rejects them with a safe error.
- UI shows archival/status correctly.
- **Not** acceptance criteria for release: historical totals numerically corrected (Workstream B).

### Required tests and dependencies
- **Tests:** importer fixture per WC status; payment refusal; template Pay absence.
- **Forbidden without separate Workstream B auth:** correction apply, production preview against prod, rollback.
- **Depends on:** owner non-payable/archive decision.
- **Release impact:** P0 blocker for customer-facing payment.

### Separate authorization required?
- **Yes** for release hardening code/tests.
- **Separate, stricter auth (GM-18+)** for any Workstream B execution — currently unreachable.

---

## Finding R-05 — Shipping implementation and checkout total consistency

### Finding ID and severity
- **IDs:** CC-08, PD-14, H-5, H-6, T-05.
- **Severity:** **P0** (established decision 2: shipping before commercial release).

### Reported source evidence (REPORTED)
- Live: six shipping methods; non-zero shipping on 1,978 orders (feature-gap B.2).
- Django: no shipping model/method/cost; total = items − discount (CC-08).
- `weight` field exists; neither importer maps `_weight` for 539 products (PD-14) — blocks weight-based shipping.
- T-05 acceptance (feature-gap): order total = items − discount + shipping; SEP amount equals that × 10; free-shipping threshold works — ×10 remains subject to R-01 contract.

### Unverified assumptions (NOT VERIFIED)
- Current live rates, free threshold, region rules (J-2).
- Weight units.
- Whether structured address (CC-07) is required for the owner’s rate table.

### Required owner decisions (OWNER DECISION REQUIRED)
- Supply current methods, rates, free threshold, region/weight rules (**do not invent** — decision 2).
- Confirm weight unit for import.
- Confirm whether shipping display is required on cart, checkout, and order summary (recommended yes).

### Proposed remediation (PROPOSED)
1. After rates provided: shipping method configuration (model or reviewed config).
2. Checkout selection UI; compute shipping server-side.
3. Persist shipping method and amount on order; include in `total_price`.
4. Payment amount uses R-01 conversion of full total including shipping.
5. Import weights only after unit confirmation (PD-14).
6. Consistent display on cart/checkout/order/payment summary.

### Acceptance criteria
- Order total = items − discount + shipping per owner rules.
- Payment amount matches contracted conversion of that total.
- Free-shipping threshold behaves per owner rules.
- No silent zero shipping when a charged method is selected.

### Required tests and dependencies
- **Tests:** per-method unit tests from owner table; checkout display; mocked SEP amount includes shipping.
- **Depends on:** Section 0.2 rates; R-01 for payment amount; soft dependency on CC-07 if region-based.
- **Release impact:** blocks commercial release.

### Separate authorization required?
**Yes.**

---

## Finding R-06 — HTTPS, TLS, Nginx, and proxy configuration

### Finding ID and severity
- **IDs:** SE-02; SE-01 (related hardening).
- **Severity:** **P0**.

### Reported source evidence (REPORTED)
- Feature-gap SE-02: `nginx/nginx.conf` listens on 80; placeholder `server_name yourdomain.com`; empty `certbot/`; `SECURE_SSL_REDIRECT=True` → unreachable or redirect-loop risk.
- Live site TLS certificate reported expired at feature-gap audit (independent urgency).
- Owner decision 3: keep existing domain; preserve SEO (implies correct HTTPS on that domain).

### Unverified assumptions (NOT VERIFIED)
- Whether any deployed host still matches the reported compose/nginx layout.
- `SECURE_PROXY_SSL_HEADER` / forwarded proto correctness in production settings as deployed.
- DNS readiness; current live certificate state today.
- Exact production hostname list.

### Required owner decisions (OWNER DECISION REQUIRED)
- Hostname list; TLS termination point; cert issuer/renewal owner (Section 0.5).

### Proposed remediation (PROPOSED)
1. Real `server_name` for the kept domain.
2. HTTPS server block **or** documented upstream TLS termination with Django trusting proxy headers correctly.
3. HTTP → HTTPS redirect without loop.
4. Align `X-Forwarded-Proto` (or equivalent) with `SECURE_PROXY_SSL_HEADER` / `SECURE_SSL_REDIRECT`.
5. Certificate auto-renewal process named in runbook.
6. Staging dress rehearsal before cutover.

### Acceptance criteria
- HTTPS serves the site on the agreed domain.
- No redirect loop.
- Staging `manage.py check --deploy` clean.
- `request.is_secure()` true behind the proxy for HTTPS clients.

### Required tests and dependencies
- **Tests:** staging TLS checklist; header/`is_secure` checks; renewal dry-run.
- **Depends on:** Section 0.5; decision 3.
- **Release impact:** blocks public cutover.
- **Independent of:** Workstream B.

### Separate authorization required?
**Yes** — staging/prod TLS and Nginx changes need ops authorization.

---

## Finding R-07 — Separate database migration procedure

### Finding ID and severity
- **IDs:** Rev8 H4a, H4b, H5; feature-gap DM-11 (pending migration note at that audit); owner decision 4.
- **Severity:** **P0** for release ops hygiene.

### Reported source evidence (REPORTED)
- Rev8 H4a (baseline `90987a6`): `docker-compose.prod.yml` web command ran `python manage.py migrate --noinput &&` then gunicorn; both db and web referenced `DJANGO_DB_USER`.
- H4b/H5: whether web login equals bootstrap superuser — **NOT VERIFIED** in Rev8.
- Owner decision 4: migrations only after verified backup + separate explicit approval.

### Unverified assumptions (NOT VERIFIED)
- Whether any environment that will be cut over still auto-migrates on start.
- Application/migrate role privileges on the target (Rev8 GM-12).
- Pending migration set at current HEAD (feature-gap noted pending `0013` at its audit — **NOT VERIFIED** now).

### Required owner decisions (OWNER DECISION REQUIRED)
- Migrate approver identity; migrate role (not casual web login); maintenance window (Section 0.6).

### Proposed remediation (PROPOSED)
1. Ensure web service startup does **not** run migrate (compose/command/entrypoint).
2. Document migrate as a separate one-shot/job with prerequisites: verified backup hash, written approval, named commit/image.
3. Rehearse migrate on disposable DB only before any production migrate auth.
4. Do **not** treat closing this item as closing Rev8 GM-12/GM-15 (Workstream B).

### Acceptance criteria
- Web start path contains no migrate.
- Migrate runbook requires backup evidence + written approval (decision 4).
- Staging proves web boots without migrate.

### Required tests and dependencies
- **Tests:** compose/entrypoint review under auth; staging boot without migrate; disposable migrate job path.
- **Depends on:** R-11 backup rehearsal before any real migrate; decision 4.
- **Release impact:** prerequisite to production schema change.

### Separate authorization required?
- **Yes** for compose/entrypoint change.
- **Additional explicit auth** for any real migrate (decision 4).

---

## Finding R-08 — Legacy URL redirects, media, canonical URLs, robots.txt, and sitemap

### Finding ID and severity
- **IDs:** SEO-01–08, SEO-10, SEO-13, SR-06, T-07, T-08, T-33; feature-gap Section G.
- **Severity:** **P1**, elevated to release-required by owner decision 3 (keep domain + preserve SEO).

### Reported source evidence (REPORTED)
- Product URLs `/product/<persian-slug>/` vs Django `/products/<pk>/`; no product slug stored (SEO-01).
- Category, page, tag, post patterns 404 (SEO-02–05).
- `/wp-content/uploads/` not served (SEO-07); description PDF links depend on WP uploads (PD-08).
- `robots.txt` 404 (SEO-08); canonical includes query strings (SEO-10); Unicode bundle slug risk (SEO-13).
- Live sitemaps also 404 (SEO-09 NOT APPLICABLE for parity; optional improvement).
- Section G proposes 301 maps from export data.

### Unverified assumptions (NOT VERIFIED)
- Full crawl of live vs Django at current HEAD.
- Media copy completeness on any host.
- Search Console / inbound link inventory.
- App/bot/`wp-json` consumers (IN-02, IN-03, IN-05).

### Required owner decisions (OWNER DECISION REQUIRED)
- Fate of `/app/`, `/bot/`, `/wp-json` (410 vs retain vs rebuild) — T-21/IN-*.
- Whether to add XML sitemap despite live 404 (recommended **PROPOSED** yes as improvement, not parity).
- Confirm Section G 301 map acceptance under decision 3.

### Proposed remediation (PROPOSED)
1. Store WP `post_name` + `_wp_old_slug` on products; data-driven 301 table/middleware.
2. Static 301s for shop/cart/checkout/account/page Persian slugs per Section G.
3. Copy uploads; Nginx/`location` to serve `/wp-content/uploads/` or 301 to `/media/...`.
4. Add `robots.txt`; strip query params from canonicals.
5. Optional `django.contrib.sitemaps`.
6. Fix Unicode slug routing for packages (SEO-13).

### R-08 SEO validation requirements (strengthened; planning only)

These validation steps are **PROPOSED** gate evidence requirements. They are **not** executed by this document. No crawl, media inventory, or robots/canonical inspection of a live or staging host is claimed here (**NOT VERIFIED**).

1. **Freeze export-derived legacy URL inventory**  
   - Produce a frozen inventory of legacy URLs derived from the authorized export (products, categories, pages, tags/posts as in scope, attachment/media paths).  
   - Record a durable **inventory identifier** and **content hash** (e.g. SHA-256 of the frozen file) in the release evidence pack.  
   - Re-runs must cite the same frozen inventory id/hash or document a new freeze with owner acknowledgement.

2. **Document exclusions + owner acknowledgement**  
   - List every URL class or path excluded from redirect/content validation (e.g. `/app/`, `/bot/`, `/wp-json`, intentional 410s, admin-only, known dead export rows).  
   - Exclusions require **owner acknowledgement** in writing. Unacknowledged exclusions leave R-08 open. Fate of `/app/`, `/bot/`, `/wp-json` remains **OWNER DECISION REQUIRED** until acknowledged.

3. **Validate final destination content and destination type**  
   - For each in-scope legacy URL: follow redirect chain; record final status, final URL, and **destination type** (product, category, page, media, other).  
   - Validate that final destination **content** matches the legacy resource intent (same product/page/category identity), not merely a 200 OK.

4. **Reject irrelevant homepage redirects**  
   - Redirects whose final destination is the site homepage (or equivalent generic landing page) are **failures** unless that specific URL is on an **owner-approved** exception list.  
   - Blanket “send unknowns to `/`” is not acceptable under decision 3 without explicit per-class or per-URL approval (**OWNER DECISION REQUIRED** for any such exceptions; none are granted here).

5. **Validate media URLs, robots, canonicals, and query-string handling**  
   - **Media:** `/wp-content/uploads/` (and agreed equivalents) return 200 or an intentional, owner-consistent 301 to the correct media object — not a soft 404 HTML page.  
   - **Robots:** `robots.txt` returns 200 with expected directives for the kept domain; behavior under staging vs production hostnames documented.  
   - **Canonical:** HTML canonical URLs omit sort/filter/session query noise (SEO-10); Unicode/package slug cases covered (SEO-13).  
   - **Query-string handling:** document how unknown and known query params affect redirects and canonicals; validation must include representative query variants from the frozen inventory or an agreed sample set.

6. **Retain crawl logs and coverage summary**  
   - Keep raw crawl/redirect logs and a **coverage summary** (inventory size, tested count, pass/fail/excluded, homepage-redirect rejects, media/robots/canonical results) suitable for **independent review** (S4).  
   - Coverage summary must cite the frozen inventory id/hash.

### Acceptance criteria
- Frozen export-derived legacy URL inventory id + hash recorded.
- Exclusions listed with owner acknowledgement (or R-08 remains open).
- In-scope URLs: redirect chain → correct destination type + content match; no unapproved homepage redirects.
- Media URL checks pass per rules above; `robots.txt` 200 with documented behavior; canonicals and query-string handling validated.
- Crawl logs + coverage summary retained for independent review.
- (**Prior weaker criteria retained as subset:**) product/category/page URLs → 301 → 200 where that is the correct destination type.

### Required tests and dependencies
- **Tests:** `resolve()`/HTTP redirect tests; fixture slug redirects; staging link crawl against frozen inventory; media/robots/canonical/query cases; coverage summary generation.
- **Depends on:** media copy ops; decision 3; owner app/bot decisions and exclusion acknowledgements for those paths.
- **Release impact:** required for domain-preserving cutover.
- **Authorization:** Boundary **A** for staging crawl evidence; Boundary **D** separately for production cutover — neither granted here.

### Separate authorization required?
**Yes.**

---

## Finding R-09 — Coupon restrictions and launch policy

### Finding ID and severity
- **IDs:** CC-05, DM-04, AD-02, PO-21; Phase 3 §1.6 imported fixed-amount coupons note.
- **Severity:** **P0**.

### Reported source evidence (REPORTED)
- 2,025 coupons; restrictions: min spend 1,174; per-user 1,986; category 1,225; exclude-sale 1,996; individual use 2,012; Smart Coupons store credit 1,167 (feature-gap).
- `DiscountCode` = percent/amount/max uses/expiry only; importer maps only those; amounts may be unconverted (DM-04; Phase 3: 13 usable fixed amounts 100,000–500,000 applied as Toman — possible 10× if Rial-era).
- No coupon admin (AD-02).
- PO-21 concurrency race on `max_uses`.

### Unverified assumptions (NOT VERIFIED)
- Which coupons must be live on day one.
- Desired post-launch Smart Coupons / wallet semantics (PO-16 wallet credited but not spendable — PARTIAL).

### Required owner decisions (OWNER DECISION REQUIRED)
- Policy **A** (inactive until parity) or **B** (implement rules then enable).
- Fate of Smart Coupons / store credit.
- Whether any new (non-migrated) coupons are allowed at launch under the limited model.

### Proposed remediation (PROPOSED)
- Until owner picks A/B: a **PROPOSED** (not approved) engineering-safe path is migrated coupons **inactive** (or not imported for active use); allow only newly created coupons whose rules the model can enforce; register admin; later parity. This path is **not** converted into approved policy by this document; Section 0.3 A/B remains **OWNER DECISION REQUIRED**.
- If **B**: implement min spend, per-user, category, exclude-sale, individual-use, max discount, expiry before activation; convert amounts per R-01/unit policy; fix PO-21 atomicity.
- Never activate unrestricted imports of restricted WooCommerce coupons.

### Acceptance criteria
- No migrated coupon grants more discount than WooCommerce equivalent, **or**
- Zero migrated coupons active with owner sign-off on that policy.
- Admin can create/disable coupons if marketing requires day-one codes under enforceable rules.

### Required tests and dependencies
- **Tests:** inactive-by-default import; rule-by-rule unit tests if B; PO-21 concurrent usage if coupons enabled.
- **Depends on:** Section 0.3; category taxonomy if category rules (feature-gap T-22 dependency for B).
- **Release impact:** P0 revenue risk.

### Separate authorization required?
**Yes.**

---

## Finding R-10 — Guest checkout, bank transfer, and installment scope

### Finding ID and severity
- **IDs:** CC-06, CC-07, PO-05, PO-19, CC-13.
- **Severity:** **P1** (installment hide is consumer-protection / support risk).

### Reported source evidence (REPORTED)
- 3,408/5,838 guest orders; checkout `@login_required`; `Order.user` required (CC-06).
- Checkout fields partial vs live billing meta (CC-07).
- Bank transfer ~1,790 orders; no customer-facing option; admin mark-paid offline only (PO-05); offline paid may not decrement stock (PO-19).
- Installment UI shown but charged in full online (CC-13; `orders/views.py:66` comment cited).

### Unverified assumptions (NOT VERIFIED)
- Day-one necessity of guest and/or bacs vs accepted conversion loss.
- Live bank-transfer instructions (J-3).
- AsanPardakht still active (PO-06 UNVERIFIED).

### Required owner decisions (OWNER DECISION REQUIRED)
- Launch scope for guest and bank transfer (Section 0.4).
- Bank-transfer instructions text.
- Confirm hide installment at launch.

### Proposed remediation (PROPOSED)
1. Hide installment UI before launch is a **PROPOSED** remediation aligned with the feature-gap recommendation; Section 0.4 installment confirmation remains **OWNER DECISION REQUIRED** and is not approved by this document.
2. Implement guest + structured address **only if** owner marks in-scope.
3. Implement bank transfer → awaiting/on-hold + instructions **only if** in-scope; offline mark-paid must decrement stock (PO-19).
4. Document accepted revenue risk if deferred.

### Acceptance criteria
- Checkout shows only real methods (no false installment promise).
- If in-scope: logged-out order path and/or transfer→awaiting→paid pass staging; stock correct on offline pay.

### Required tests and dependencies
- **Tests:** installment absence; guest checkout if in-scope; transfer status machine; stock on offline pay.
- **Depends on:** owner scope; CC-07 for guest/shipping region; does **not** unblock R-01/R-05/R-06.
- **Release impact:** P1 conversion/parity; installment hide should still ship with safety set.

### Separate authorization required?
**Yes.**

---

## Finding R-11 — Backup/restore, monitoring, and release runbook

### Finding ID and severity
- **IDs:** SE-03, SE-08, H-17, T-18, T-40; distinct from Rev8 GM-16.
- **Severity:** **P1** (prerequisite to migrate/cutover under decision 4).

### Reported source evidence (REPORTED)
- No backup job in production compose at feature-gap (SE-03); H-17 no backups.
- Console logging only; no ADMINS/Sentry (SE-08).
- Feature-gap launch checklist includes backups and restore drill.

### Unverified assumptions (NOT VERIFIED)
- Host-level backups outside the repository.
- RPO/RTO; alert routing.

### Required owner decisions (OWNER DECISION REQUIRED)
- RPO/RTO; backup storage; restore operator; monitoring product; cutover communications (Section 0.6).

### Proposed remediation (PROPOSED) — release runbook outline
1. **T−backup:** take DB + media backup; record identity and hash.
2. **Restore rehearsal:** restore onto disposable target; fingerprint/smoke match (non-prod).
3. **R-07:** confirm web does not auto-migrate.
4. **Separate migrate auth (decision 4):** only after backup verified.
5. **Monitoring:** error tracking live in staging; alert test.
6. **Staging dress:** TLS (R-06), payments sandbox (R-01/R-02), shipping totals (R-05), SEO sample crawl (R-08).
7. **Cutover:** DNS/traffic; watch alerts; rollback criteria (restore from rehearsal-proven backup).
8. **Explicit exclusion:** Workstream B correction apply is **not** in this runbook.

### Acceptance criteria
- Runbook document approved by release owner.
- Restore rehearsal evidence retained.
- Staging alert fires on injected error.
- Migrate never in web start; production migrate only with decision-4 approval.

### Required tests and dependencies
- **Tests:** disposable restore drill; staging alert test.
- **Depends on:** R-07; Sections 0.5–0.6; before production migrate/cutover.
- **Do not conflate** with Rev8 GM-16 correction fingerprint rehearsal.

### Separate authorization required?
**Yes** for non-prod rehearsal; **explicit release auth** for production backup/cutover/migrate.

---

## Finding R-12 — Workstream B conflicts, recovery safeguards, and missing artifacts

### Finding ID and severity
- **IDs:** Rev8 A4, C1–C7, D3–D4, E1–E6, F1–F5, G1–G7, H1–H10, I1–I5, J1–J4; GM-01–GM-24.
- **Severity:** Blocks **any** correction execution. Must **not** be folded into commercial release except shared hygiene (e.g. R-07 mindset).

### Reported source evidence (REPORTED) — conflicts and gaps
| Area | Rev8 claim (short) | Classification in Rev8 |
| --- | --- | --- |
| A4 | Phase 3 “uncommitted” stale; tests not tied to commit | VERIFIED FROM SOURCE; blocks using historical tests |
| C1–C2 | Outcomes from exceptions only; no xid/PID/recovery | VERIFIED FROM SOURCE; blocks |
| C6–C7 | No halt; preview wrongly offered as remedy | VERIFIED / CONTRADICTED BY SOURCE; blocks |
| D3–D4 | `InterfaceError` path incomplete; reconnect inside `Atomic.__exit__` omitted | MISSING OR INCOMPLETE; blocks |
| E1–E4 | Rollback accepts incomplete/unknown reports; apply approval authorizes rollback | VERIFIED FROM SOURCE; blocks |
| F1–F3 | SHA-256 allowlist; no signature/nonce; approval reusable | VERIFIED FROM SOURCE; blocks |
| G1–G7 | No source/image identity; unhashed pins; mutable tags; CRLF risk | blocks |
| H1–H5 | Identity omits endpoint/recovery; migrate-on-start at Rev8 baseline; roles unverified | blocks |
| I1–I3 | Audit fsync limits; terminal-marker failure → rollback-acceptable file | blocks |
| J1–J4 | No retained test artifacts; T1–T15 missing; commit-loss not exercised | blocks |
| GM-01–GM-24 | All **Open**; GM-18 only execution gate | matrix status |

### Unverified assumptions (NOT VERIFIED)
- Everything in Rev8 §7 (pooler, xid behaviour on target major, roles, remote branch, `.env`, trust custody, business inputs, image digests, etc.).
- Uncertain-outcome recovery GM-24: proposed only — not implemented, not rehearsed.

### Required owner decisions (OWNER DECISION REQUIRED)
- Whether Workstream B proceeds after commercial launch at all.
- GM-13 business inputs; GM-06 trust-anchor custody and approver independence (F5).

### Proposed remediation (PROPOSED) — isolation and future path only
1. **Hard isolation:** no correction apply/rollback in release runbook; no shared “GO” with Workstream A.
2. Follow Rev8 dependency order: GM-01→02→03 design → GM-04/06 → GM-05 → GM-07/08 → GM-09/10 → target gates GM-11+ only with production access authorization.
3. Halt scoped to target DB identity; preview never clears halt (C6/C7); GM-24 only recovery.
4. Do not schedule historical amount correction for cutover.
5. Shared lesson only: remove unsafe auto-migrate patterns (R-07) — closing R-07 does **not** close GM-12/GM-15.

### Acceptance criteria
- **For commercial GO:** none from Workstream B (must remain NO-GO).
- **For future B:** gates closed with Rev8 evidence-record format; independent verifier ≠ producer.

### Required tests and dependencies
- Only after GM-08 isolation proof; Rev7 T1–T15 + Rev8 additions; never against production under current auth.
- **Release impact:** parallel track; must not delay or contaminate Workstream A except documented shared hygiene.

### Separate authorization required?
**Always.** GM-18 is the only time-bounded execution authorization; currently unreachable. This blueprint does **not** grant it.

---

## Dependency-ordered remediation plan (Workstream A)

```text
[0] Owner contracts (Sections 0.1–0.6)
      │
      ├─► [1] R-04 non-payable/archival imported orders
      ├─► [1] R-10 hide installment (and scope guest/bacs)
      └─► [1] R-09 coupon policy A or B (default safe: inactive)
      │
      ▼
[2] R-01 monetary/SEP contract signed
      │
      ▼
[3] R-02 payment callback/concurrency/mismatch/reverse evidence (retained)
      │
      ├─► [3b] R-03 duplicate-order policy
      └─► [4] R-05 shipping (only after owner rates) → totals include shipping
      │
      ▼
[5] R-07 web start without migrate
      │
      ▼
[6] R-11 backup/restore rehearsal + monitoring + release runbook
      │
      ▼
[7] R-06 TLS/Nginx/proxy on staging (kept domain)
      │
      ▼
[8] Decision-4 authorize migrate (separate) — after backup evidence
      │
      ▼
[9] R-08 legacy redirects/media/robots/canonical/(optional sitemap)
      │
      ▼
[10] Owner-scoped R-10 guest/bacs if required; other feature-gap P1 as separate auths
      │
      ▼
[11] Release GO/NO-GO review (separate authorization) — not granted here

PARALLEL (never merges into [11] cutover):
[B] R-12 Workstream B under Rev8 GM-01…GM-24 — remains NO-GO
```

### Sequencing rules
1. Do not implement shipping rates before Section 0.2 (no invented rates).
2. Do not enable payment before R-01 + R-02 + R-04.
3. Do not run production migrate from web start; only via decision 4 after R-11.
4. Do not run Workstream B apply in any release step.
5. Do not mark any gate passed without retained evidence and independent verification where Rev8/feature-gap require it.
6. Diagram labels such as “default safe: inactive” for coupons are **PROPOSED** sequencing hints only — not owner-approved policy (Section 0.3 remains open).

---

## Gate closure, waivers, and independent review

### Gate-closure non-implication rule

Closing **one** gate (finding acceptance criteria, S4 review, or Rev8 GM entry) does **not**:

- authorize production migration (Boundary **B**);
- authorize payment enablement (Boundary **C**);
- authorize production cutover (Boundary **D**);
- authorize historical-order correction / Workstream B (Boundary **E**);
- close any **dependent** or **sibling** gate by implication.

Each gate requires its own evidence pack and, where this blueprint or Rev8 requires it, an Independent-Review Record. Commercial release GO and Workstream B GO remain separate decisions.

### Waiver rule

Any waiver of a gate, acceptance criterion, or authorization prerequisite requires **separate, explicit authorization** identifying:

| Waiver field | Required content |
| --- | --- |
| Decision-maker | Named approver (role + identity) |
| Affected gate | Exact finding/GM/S4 gate id |
| Scope | What is waived and what remains required |
| Environment | Non-prod / staging / production as applicable |
| Rationale | Why the waiver is requested |
| Impact | What changes in risk, sequencing, or customer effect |
| Accepted residual risk | Explicit residual risk statement |

**No waiver is currently granted.** Proposed remediation text is not a waiver.

### S4 Independent-Review Record (template)

Use one record per review event. The **reviewer must differ from the producer** of the evidence under review. Completing this template in planning form does **not** close any gate and does **not** grant Boundaries A–E.

```text
S4 INDEPENDENT-REVIEW RECORD
============================
Record id:                    ______________________________
Date (UTC):                   ______________________________

1. Reviewer identity (must ≠ producer)
   Reviewer name/role:        ______________________________
   Producer name/role:        ______________________________
   Independence attestation:  Reviewer did not produce the
                              evidence pack under review: [ ] yes

2. Evidence identifiers and hashes
   Evidence pack id:          ______________________________
   Artifact paths/ids:        ______________________________
   Content hashes (algo):     ______________________________
   Named commit / image:      ______________________________
   Frozen URL inventory id/hash (if R-08 in scope): __________

3. Exact scope and gates reviewed
   Workstream:                [ ] A  [ ] B  [ ] other: ______
   Findings/gates in scope:   ______________________________
   Findings/gates out of scope: ____________________________
   Authorization boundaries considered (A–E): ______________
   Note: reviewing a gate ≠ authorizing B/C/D/E.

4. Findings, unresolved exceptions, and impact
   Findings (pass/fail/blocked): ____________________________
   Unresolved exceptions:     ______________________________
   Impact of each exception:  ______________________________
   Owner decisions still open: ______________________________

5. Explicit decision and limitations
   Decision:                  [ ] PASS  [ ] FAIL  [ ] INCOMPLETE
   Gates closed by THIS record: ____________________________
   (If none: write NONE)
   Limitations / non-claims:  ______________________________
   Waivers relied upon:       [ ] NONE  [ ] list ids: _______
   Authorization granted?:    [ ] NONE (expected default)
```

**S4 gates closed by this document: `NONE`.**

---

## Explicit release decision

| Question | Decision |
| --- | --- |
| Commercial release | **`NO-GO`** — open P0s: monetary/SEP contract (R-01), shipping rates (R-05), TLS (R-06), imported payability (R-04), coupon policy (R-09); payment runtime evidence not retained for this document (R-02); SEO validation inventory/crawl not executed (R-08). |
| Historical-order correction | **`NO-GO`** — Rev8 GM-01–GM-24 open; conflicts unresolved (R-12); Boundary **E** unauthorized. |
| Execution authorization | **`NONE`** — Boundaries A–E all **NONE**; this document authorizes documentation only. |
| S4 gates closed by this document | **`NONE`** |
| Owner contracts complete for release? | **NO** — inventory recorded; signed answers still **OWNER DECISION REQUIRED**. |
| Waivers granted? | **NONE** |
| Final status | **`NO-GO — NO EXECUTION AUTHORIZED`** until a separately authorized review establishes otherwise. |

Unresolved owner decisions (non-exhaustive; remain explicitly unresolved — no proposed default is approved policy): Section 0.1 H1/H2/SEP unit; 0.2 shipping rates; 0.3 coupon A/B and Smart Coupons; 0.4 guest/bacs/installment; 0.5 hostname/TLS termination; 0.6 RPO/RTO/backup/monitoring/migrate approver; R-02 reverse-failure and multi-pending recovery policies; R-03 duplicate-order policy; R-04 archival/non-payable and Workstream B business inputs; R-08 exclusions and any homepage-redirect exceptions; R-12 whether Workstream B proceeds after launch.

---

## Work performed for this blueprint revision

### Prior blueprint creation (REPORTED context; not re-executed here)
- Original planning deliverable created as documentation only; historical audit sources cited as **REPORTED**.

### This consolidation revision (documentation only)
- Changed file: `audit_reports/KASRA_REMEDIATION_BLUEPRINT.md` only.
- Added Authorization Boundaries A–E and separate-authorization rule.
- Added R-02 expected-outcome matrix (recovery procedures left **OWNER DECISION REQUIRED** where unapproved).
- Strengthened R-08 SEO validation (frozen inventory hash, exclusions, destination content/type, homepage-redirect rejection, media/robots/canonical/query, crawl log retention).
- Added Gate-closure non-implication rule, Waiver rule (no waivers granted), and S4 Independent-Review Record template.
- Preserved final status: commercial **NO-GO**; historical-order correction **NO-GO**; execution authorization **NONE**; S4 gates closed **NONE**.
- Unresolved owner decisions left explicitly unresolved; proposed defaults not converted to approved policy.
- Historical audit findings kept as **REPORTED** / previously reported — this task did **not** inspect current repository runtime behavior, database contents, payment gateway, backups, or server configuration beyond reading this planning document.
- Application code, tests, settings, migrations, data, secrets, deployment files, and other documents **not** modified.
- Tests not run. Databases not contacted. Migrations, importer, correction, rollback, payment operations, deployment, and production access **not** performed.
- Per task authorization: **no git commit or push** for this consolidation revision.

**End of blueprint.**
