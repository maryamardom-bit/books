# P0-2 Phase 3 — Evidence-Based Correction Plan (no data changes)

Date: 2026-10-11, about 09:20–09:40 UTC.
Branch: `cursor/payment-hardening-and-architecture-review`, HEAD `9cbcdbc`. P0-1, Phase 1 and the Phase 2 report are uncommitted.

Inputs:
- `audit_reports/P0_2_PHASE2_READ_ONLY_RECONCILIATION.md`.
- The Phase 2 CSV at `/tmp/order_amount_audit_p0_2_phase2_20261011.csv` in `books-web-1` (SHA-256 `4fd2b471…be2d`, re-verified).
- The WXR copy at `/tmp/wordpress.xml` (SHA-256 `dcd36385…0f53`, identical to `D:\copy_data_kasra\wordpress.2026-09-24.xml`).

**Status: NO-GO for every data modification.** This document is a plan. No record was changed and no migration was created or applied.

**Update (Phase 4, 2026-10-11):** the correction command `correct_imported_order_amounts` now exists in the working tree (uncommitted). `--apply` and `--rollback` are disabled in code (`EXECUTION_ENABLED = False`) and blocked by several further gates. Sections 1–4 remain the evidence base. Where sections 5 and 7 differ from the implementation, **section 10 is authoritative**.

---

## 1. Verified findings

### 1.1 The canonical unit is Toman, everywhere in the application

| Area | Evidence | Unit |
| --- | --- | --- |
| Order total | `orders/models.py:72-74` says "Amount the customer pays, in Toman, after discounts". `BigIntegerField`. | Toman |
| Native checkout total | `orders/views.py:105` stores the cart total, built from catalogue prices. | Toman |
| Order item price | `orders/models.py:139` (`PositiveIntegerField`). It is populated from catalogue prices. | Toman |
| Payment amount | `payment/models.py:33-34` ("Same unit as Order.total_price (Toman)"). It is created from `order.total_price` in `payment/services.py:85`. | Toman |
| Gateway conversion | `payment/gateways/base.py:49-51` returns `amount * PAYMENT_AMOUNT_MULTIPLIER`. `config/settings.py:226-227` sets the default to 10. `payment/gateways/sep.py:49`. Callback verification compares in Rial (`payment/services.py:173-175`). | Toman → Rial |
| Wallet | `accounts/models.py:20` (`PositiveIntegerField`, so 32-bit). It is displayed as Toman in `accounts/templates/accounts/dashboard.html:20`. | Toman |
| Discount codes | `products/models.py:492` `amount` is applied as Toman in `apply_discount` (`products/models.py:520-533`). | Toman, but the imported values are raw (see 1.6) |
| Shipping, discount and tax per order | Not stored (TODO at `orders/models.py:73`). | n/a |
| Refunds | No refund model (TODO at `payment/models.py:13-14` and `orders/models.py:170-171`). | n/a |
| Admin and reports | `orders/admin.py:110-111`, `services/sms.py:111,122,133`, `accounts/templates/accounts/order_history.html:25`, `accounts/templates/accounts/dashboard.html:47`, `orders/templates/orders/request_return.html:14`, API `api/serializers.py:156`. | All labelled Toman |
| SEO price | `products/views.py:145-146` converts Toman to IRR (×10) for schema.org. | Toman → Rial |

There are no signal handlers in `orders`, `payment`, `accounts` or `services`, so a bulk update to `total_price` triggers no SMS and no side effects.

### 1.2 How the importer stored historical totals

- `products/management/commands/import_wordpress_complete.py:311` runs `total = int(float(_order_total))`; `_order_currency` is ignored. Line 335 writes it to `total_price`.
- Line 339 uses `update_or_create(wordpress_id=..., defaults=...)`. **Every importer re-run overwrites `total_price` with the raw value again, which would silently undo any correction.**
- Line 324 sets `is_paid` from the status (`wc-completed`, `wc-refunded`, `wc-processing`). The pending migration `orders/migrations/0008_order_status_orderitem_title_protect.py:6-9` would set `status='PAID'` for those orders, imported refunded orders included. It does not touch `total_price`.
- Phase 2 measured the result in the dev DB: 5,630 `RAW_IRR` plus 83 `RAW_IRHT` exact raw copies, 125 zeros, and 0 mismatches.

### 1.3 Dev database state (read-only aggregates)

These were read in a `READ ONLY` transaction; the WAL position `0/B8EEFD0` was identical before and after.

| Fact | Value |
| --- | --- |
| Orders | 5,838. All are imported; there are 0 native orders. |
| `is_paid` on imported orders | True 5,562; False 276 |
| `OrderItem` rows | 0 in total, so imported orders have no line items |
| `ReturnRequest` rows | 0 |
| Users with `wallet_balance > 0` | 0 |
| `payment_payment` table | Does not exist (`payment 0001` is unapplied), so there are 0 payment records |
| Imported order with `total_price` above the 32-bit limit (2,147,483,647) | 1 (2,227,500,000 raw IRR) |
| Imported orders created within the 3-day return window | 0 |
| Fixed-amount discount codes | 1,162. Of these, 13 are active and unexpired (amounts 100,000–500,000) and 9 still have uses left. |
| Product prices | 259 priced; median 550,000; none below 20,000 (the importer multiplied them by 1,000) |

### 1.4 The source export: currency timeline and amounts

| Fact (from `/tmp/wordpress.xml`) | Value |
| --- | --- |
| IRR orders | 5,748, dated from 2018-05-29 09:09:44 to **2026-04-05 13:26:00** |
| IRHT orders | 90, dated from **2026-04-06 00:00:00** to 2026-09-23 10:47:40 |
| Interleaving | None: 0 IRR orders after the first IRHT order, and 0 IRHT orders before the last IRR order |
| `_order_version` | `3.0.7` on every order in both currencies |
| Payment methods | IRR: `sep_gateway` 3,743, `bacs` 1,737, `WC_Sep_Payment_Gateway` 138, `asanpardakht` 121, `other` 9. IRHT: `bacs` 53, `WC_Sep_Payment_Gateway` 37. |
| Non-zero order medians | IRR 2,000,000 (Q1–Q3 1,020,000–3,950,000). IRHT 1,625 (Q1–Q3 675–15,370). |
| Monthly non-zero medians around the switch | 2026-03 IRR 8,425,000. 2026-04 IRHT 1,330 (plus one IRR order at 3,950,000). 2026-05 IRHT 1,462.5. |
| `_order_shipping` | IRR: non-zero on 1,932 orders, median 249,000; most common values 300,000, 500,000, 119,000. IRHT: non-zero on 46 orders, 40 of them exactly `125`. |
| `_cart_discount` | IRR: non-zero on 1,041 orders, median 1,315,000. IRHT: non-zero on 39 orders, median 7,140. |
| `_order_tax` | 0 everywhere |
| Fractional totals | None in either currency |
| Refunds | 72 (71 IRR, 1 IRHT). 0 with a currency different from the parent order. 43 full, 28 partial, 0 larger than the parent. 1 orphan (2021, parent missing from the export). |
| Products in export | 623, of which 259 are priced. Median `_price` is 550; 256 of 259 are below 20,000. |
| Order notes | No note on any order records the charged amount at any multiplier (×1, ×10, ×100, ×1,000, ×10,000), so the notes cannot reveal the gateway unit. |

### 1.5 The two cancelled SEP IRHT anomalies (no identifiers)

| Fact | Order A | Order B |
| --- | --- | --- |
| Raw total / currency | 4,400,125 IRHT | 2,401,625 IRHT |
| Date | 2026-04-27 09:27 | 2026-05-05 17:31 |
| Status / method / created via | `wc-cancelled` / `WC_Sep_Payment_Gateway` / `checkout` | same |
| Shipping / discount / tax | 125 / 0 / 0 | 125 / 0 / 0 |
| `_paid_date`, `_date_paid`, `_transaction_id`, `sep_trace_number`, `PayGateTranID` | all empty | all empty |
| `_order_stock_reduced`, `_recorded_sales`, `_date_completed` | empty | empty |
| Refund records | 0 | 0 |
| Order notes | 2. Both follow templates shared by hundreds of ordinary orders. One note contains a single 10-digit number (not printed). | 2, same templates. One 12-digit number (not printed). |
| Note contains the total at any multiplier | No | No |
| Other SEP IRHT orders (35) | All totals between 320 and 3,130 | |

**Verified:** both were storefront checkouts that were **never paid**. No payment date, no transaction or trace id, stock never reduced, sales never recorded.

**Arithmetic observation only, not evidence:** total minus shipping is 4,400,000 and 2,401,500.

**Not determinable:** the intended amount. The export has no line items and the notes contain no amount. **No corrected value may be inferred.** The reference numbers in the notes can be looked up by the owner in the WooCommerce admin or the SEP panel.

### 1.6 Related risks found (outside this correction's scope)

1. **Importer re-run reverts corrections** (`import_wordpress_complete.py:339`). This is a blocker for any correction.
2. **Wallet credit uses the raw total.** `orders/admin.py:247-249` credits `wallet_balance += order.total_price` when a return is approved. For an imported IRR order that is 10× the Toman value. For the order above 2,147,483,647 the update would overflow the 32-bit wallet column. Today's exposure is nil, because there are 0 return requests and the 3-day window (`orders/views.py:146-148`, `orders/models.py:203-206`) excludes every imported order.
3. **Imported fixed-amount coupons are raw** (`import_wordpress_complete.py:242-249`). 13 are usable now, with amounts of 100,000–500,000 that the app applies as Toman. If they were created in the Rial era, they are worth 10× too much. This is a separate item, and coupon behaviour is not changed here.
4. The pending migration 0008 backfill maps imported refunded orders to `status='PAID'` (`0008...py:9`).

---

## 2. IRR and IRHT: facts vs hypotheses

| # | Statement | Status |
| --- | --- | --- |
| F1 | Every order carries exactly one of `IRR` or `IRHT` in `_order_currency`. | **Verified** (export) |
| F2 | The codes switch once with no overlap: last IRR 2026-04-05 13:26:00, first IRHT 2026-04-06 00:00:00 (WordPress local `post_date`). | **Verified** (export) |
| F3 | The importer stored both codes unconverted. | **Verified** (code and Phase 2 reconciliation) |
| F4 | Refund records use the same currency as their parent order. | **Verified** (export) |
| H1 | `IRR` means Iranian Rial for this store. | **Strong hypothesis.** It is the ISO 4217 code and WooCommerce's core meaning. Not confirmed against a bank or SEP settlement for this store. |
| H2 | `IRHT` means thousand Toman. | **Hypothesis, unverified.** Supporting evidence: (a) the Persian WooCommerce code convention (external knowledge, not in the repo); (b) the importer comment "Storefront displays these units as «هزار تومان»" (`import_wordpress_wxr.py:48`), with a matching scraper rule (`import_wordpress.py:131-132`), but no stored storefront sample was found; (c) internal consistency: the order median moves from 842,500 Toman (2026-03) to 1,330,000 under H2, but to 133,000 under "thousand Rial"; product median 550 gives 550,000 Toman per book under H2. Contrary or open signals: shipping becomes 125,000 Toman under H2, against typical IRR-era shipping of 30,000–50,000 Toman. No document, settings history or settlement record confirms H2. |
| H3 | The store's currency setting changed on 2026-04-05/06. | **Data boundary only.** The first IRHT timestamp is exactly `00:00:00`, which may indicate manual entry. The actual settings change date is unknown. |
| H4 | `_order_total` is the gross total before refunds. | **Consistent with WooCommerce behaviour** (no refund exceeds its parent, 28 partial refunds exist). Not separately verified. |

**Boundary conclusion:** the data shows a clean code boundary, but nothing proves which unit amounts entered just after the switch were really in. Rules depending on H2 are **BLOCKED**.

---

## 3. Proposed correction matrix

Each order is assigned to exactly one bucket, in the precedence order shown. Counts and sums are actual values from the Phase 2 CSV. "Proposed" values use the provisional factors and are **not** approved.

| Rule | Bucket (precedence) | Orders | Stored sum | Proposed sum | Proposed action | Status |
| --- | --- | --- | --- | --- | --- | --- |
| R7 | Anomalous: `CANCELLED_SEP_ANOMALY` | 2 (IRHT cancelled) | 6,801,750 | — | **Exclude. Keep the raw value.** Owner looks up both orders in the WC admin and the SEP panel. No inferred value. | **BLOCKED** |
| R3 | Zero total | 125 (IRR: 105 completed, 12 on-hold, 1 cancelled; IRHT: 2 completed, 5 on-hold) | 0 | 0 | **No change** (0 is 0 in every unit). Owner review of why 107 completed or on-hold orders are zero, e.g. full-value coupons. | No-op |
| R8 | Uncertain currency or unit: not `RAW_IRR`/`RAW_IRHT` (`SOURCE_INVALID`, `MISMATCH`, `MISSING_*`, `DUPLICATE_*`) | 0 now | 0 | — | **Exclude.** If any appear at execution time, abort the run. | Guard |
| R6 | Has payment records | 0 (table absent in dev; P0-1 prevents new ones) | — | — | **Exclude.** If any `Payment` row exists for a target order at execution, abort: `Payment.amount` would disagree with the order. | Guard |
| R5 | Refund-related: `wc-refunded` or has a refund record | 67 (IRR: 44 refunded, 22 completed with partial refunds; IRHT: 1 refunded) | 3,653,908,250 | 366,140,750 | Separate batch, only with explicit owner approval. `total_price` stays the **gross** amount; refunds are not represented anywhere in Django and are documented, not corrected. The IRHT order is also subject to R2. | **CONDITIONAL** (IRR) / **BLOCKED** (IRHT) |
| R4 | Cancelled | 209 (IRR 198, IRHT 11) | 1,132,926,465 | 129,231,053 | Not automatic. The owner chooses: (a) convert for consistent history display, or (b) leave raw and mark as historical-cancelled. One IRR order (74,025) is not divisible by 10 and needs a rounding decision. | **CONDITIONAL** (IRR) / **BLOCKED** (IRHT) |
| R2 | Verified IRHT, completed or on-hold | 69 (53 completed, 16 on-hold) | 1,229,647 | 1,229,647,000 | ×1,000, **only after H2 is confirmed** | **BLOCKED** |
| R1b | IRR, completed or on-hold, wholesale-sized | 82 (75 completed, 7 on-hold) | 35,162,975,000 | 3,516,297,500 | ÷10 after the owner spot-checks a sample against bank or SEP records (the threshold only picks the sample; it is not a rule) | **CONDITIONAL** |
| R1a | IRR, completed or on-hold, other | 5,284 (5,260 completed, 24 on-hold) | 29,074,742,000 | 2,907,474,200 | ÷10, exact: every value is divisible by 10, so no rounding | **CONDITIONAL** (on H1 confirmation by sample) |
| | **Total** | **5,838** | | | | |

### Excluded records and their treatment

- R7 (2), R3 (125), R6 and R8 (0 today) are never modified by the batch.
- R4 and R5 are modified only in their own separately approved batches.
- R2 is blocked until H2 is confirmed.
- The 72 refund records and the orphan refund are not in Django. There is nothing to correct; this is a documented limitation.
- Discount codes, wallet balances, product prices, payment records and order statuses are out of scope and untouched.

---

## 4. Schema assessment: is a migration needed?

- `total_price` is a `BigIntegerField`. The largest proposed value for R1 or R2 is 222,750,000. Every proposed IRR value is exact, except one cancelled order that needs a rounding decision. IRHT has no fractions. **The schema can represent the corrected values.**
- Reversibility and idempotency can be achieved without schema changes:
  - an immutable before-state export plus a verified backup;
  - a compare-and-set update that only changes a row whose current value equals the approved "before" value.
- **No migration is necessary.** A per-order audit trail in the database (source currency, raw amount, correction run id) would be useful, but no evidence makes it necessary, and it was previously ruled out of scope. If the owner wants it, it needs its own approved design.
- Sequencing with the pending `orders 0008` and `payment 0001` migrations: they don't touch `total_price`. Either order works, but the backup must be taken **after** whichever schema state is in place at execution time, and the plan must be generated against that same state.

---

## 5. Correction procedure (to run only after every GO item in §7 is met)

This needs a new command, e.g. `correct_imported_order_amounts`.

> **Superseded in part.** The command is now implemented; its actual interface, artifacts, lock semantics and rollback procedure are described in section 10. Notably, step 5.5.1 is wrong for the implementation: the correction does **not** take a session-level lock. It takes a transaction-level lock (`pg_try_advisory_xact_lock`) inside its write transaction. The order importer takes the session-level lock on the same key.

### 5.1 Preconditions (code)

1. Fix the importer so a re-run cannot overwrite `total_price` on existing imported orders, or so it converts by `_order_currency`. This needs separate approval. Until then, importer runs are forbidden on any corrected database.
2. The correction command has dry-run as its default, and these properties:
   - an explicit `--apply`;
   - a `--plan` CSV input;
   - a mandatory `--plan-sha256`;
   - `--approval-ref`;
   - `--rule` to select one bucket per run.

### 5.2 Backup and restore test

1. Agree a maintenance window. The web container serves no traffic, and no importer or admin bulk actions run.
2. Run `pg_dump -Fc` of the target database from `books-db-1` to a file **outside the repository and container**. Record its SHA-256.
3. Validate the dump with `pg_restore --list`.
4. Restore test: restore into a scratch database (needs approval, because it creates a database) and compare the order fingerprint against the source. The fingerprint is the count, the `wordpress_id` count, the `total_price` sum, and an md5 over (id, wordpress_id, total_price, is_paid). Drop the scratch database only after the comparison is recorded.

### 5.3 Immutable before-state

1. Re-run `audit_imported_order_amounts` with a new output file. The classification counts must equal Phase 2, otherwise stop.
2. Export the before-state for the target bucket: (`order id`, `wordpress_id`, `total_price_before`, `currency`, `status`, `proposed_after`, `rule`, `reason_code`). It contains no personal data. Record its SHA-256 and store it read-only outside the repository.
3. Record the WAL position and the full-table fingerprint.

### 5.4 Dry-run preview

- Produce per-order rows with a reason code, e.g. `R1A_IRR_DIV10`, `EXCL_R7_ANOMALY`, `EXCL_R3_ZERO`.
- Produce per-bucket counts and sums before and after, and an exclusion list with reasons.
- The owner signs off on the preview **file hash**. The apply step refuses any plan whose hash differs.

### 5.5 Execution

1. Take a session-level advisory lock, `pg_try_advisory_lock(<constant>)`. If it isn't acquired, exit, so two runs can't execute at once.
2. Use **one transaction per rule batch**, at `REPEATABLE READ`.
3. Lock the targets with `SELECT ... FOR UPDATE NOWAIT` on the plan's ids. If any lock fails, roll back.
4. Re-check the guards inside the transaction:
   - no `Payment` row for any target (R6);
   - the classification is still `RAW_*` (R8);
   - `wordpress_id` is not null;
   - the current `total_price` equals the plan's `before` value.
5. Use a compare-and-set update per row: `UPDATE orders_order SET total_price = :after WHERE id = :id AND wordpress_id = :wp AND total_price = :before`. Every row must report exactly 1 row updated, otherwise the whole batch rolls back.
6. Idempotency: if every target already equals `after`, report "already applied" and change nothing. A mix of `before` and `after` values aborts.
7. Inside the transaction, assert that the batch's sums equal the preview's sums before committing.
8. Do not use `save()`: it would trigger `auto_now` on `datetime_modified` and run model logic. There are no signals, so a compare-and-set update has no side effects.

### 5.6 Post-change verification

1. Re-run the reconciliation. Corrected rows must move to `MATCH`; excluded buckets must be unchanged.
2. The fingerprint of non-target rows must be identical to the before-state.
3. Check that the order history, admin display and API show Toman values for 5 sampled orders the owner already verified.
4. Archive the CSVs, hashes and logs with the approval reference.

### 5.7 Rollback

- **Logical rollback (preferred):** apply the before-state file in reverse with compare-and-set (`WHERE total_price = :after`), in one transaction. Afterwards, the reconciliation must show the original `RAW_*` counts again and the fingerprint must equal the before-state.
- **Physical rollback (last resort):** restore the verified dump into a new database, verify its fingerprint, then switch `DJANGO_DB_NAME` during a window. Never restore over the live database without a second backup.

---

## 6. Credential exposure review (no values reproduced)

During Phase 2, a failed PowerShell filter printed the whole environment of `books-web-1` into this session's terminal output. Those values are also stored in the local agent transcript on this machine.

The variable **names** exposed were: `DJANGO_SECRET_KEY`, `DJANGO_DB_PASSWORD`, `DJANGO_DB_USER`, `DJANGO_DB_NAME`, `DJANGO_DB_HOST`, `DJANGO_DB_PORT`, `DJANGO_DEBUG`, `SEP_TERMINAL_ID`, `KAVENEGAR_API_KEY` and `KAVENEGAR_SENDER`.

| Credential | Observed character (Phase 2) | Rotation need |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` (dev) | Development key with the `django-insecure` prefix | **Rotate the dev key.** It also signs JWTs (`config/settings.py:286`), sessions and password-reset tokens. **The owner must confirm that production (`.env.prod`, not present locally) uses a different key.** If they are shared, rotate production too. |
| `DJANGO_DB_PASSWORD` (dev) | The default value, already committed in `docker-compose.yml:19` and `:32` | **Rotate.** The dev database holds real customer data (5,838 orders with names, phones and addresses), and `docker-compose.yml:33-34` publishes port 5432 on all host interfaces. Also bind it to `127.0.0.1` or remove the port mapping. |
| `KAVENEGAR_API_KEY`, `SEP_TERMINAL_ID` | Appeared to be test placeholders | Rotate only if the owner confirms they are real. A Kavenegar key is rotated in its panel. A SEP terminal id is an identifier rather than a secret; consult SEP if it is the live one. |
| `KAVENEGAR_SENDER` | A sender line number (an identifier, not a secret) | None |

The automated review gate **blocked** an additional check in this phase: comparing values against `.env`, `.env.example` and git history without printing them. So it is **unverified** whether these values appear in tracked files or git history, or match `.env.example`. `.gitignore:7-8` excludes `.env` and `.env.prod`. The owner can run `git log --all -- .env .env.prod` locally to confirm they were never committed.

**Safe rotation procedure** (dev only, non-disruptive to other environments):
1. Generate a new key locally and write it straight into `.env` without echoing it to a terminal. Don't touch `.env.prod`.
2. In a planned dev window, recreate only the `web` service of compose project `books` so it picks up the new environment. Expected effects: dev sessions, JWTs and reset links are invalidated.
3. For the DB password: change the password of the dev `postgres` role, update the compose environment to match, and restrict the port binding. This requires explicit approval, because changing a role password is a database write and recreating containers is a service restart.
4. Production: rotate only through its own change process, after confirming the key is shared.
5. Recommended separate code hardening: make `config/settings_production.py` refuse keys that start with `django-insecure` or are shorter than 50 characters.
6. Consider redacting the local agent transcript that contains the printed values.

---

## 7. GO/NO-GO checklist for any future data modification

All items must be **GO** for the specific rule batch being applied.

| # | Item | Current status |
| --- | --- | --- |
| G1 | Owner confirms H1 (IRR = Rial) with a sample of at least 10 IRR orders checked against bank or SEP settlement records | NO-GO |
| G2 | Owner confirms H2 (IRHT = thousand Toman) with settings history or a settlement for at least 3 IRHT orders (required for R2 and the IRHT parts of R4 and R5) | NO-GO |
| G3 | Owner decisions recorded for R4 (cancelled), R5 (refund-related), R7 (anomalies), and the rounding of the one non-divisible order | NO-GO |
| G4 | Target environment named explicitly: dev and/or a production Django database, each separately approved | NO-GO |
| G5 | Importer can no longer overwrite `total_price` (code change merged and tested) | NO-GO. Implemented and tested in the working tree (existing orders keep `total_price` and `is_paid`; the importer is mutually exclusive with the correction). Not committed, not reviewed. |
| G6 | Correction command implemented with dry-run default, compare-and-set, advisory lock and plan hash, with tests including idempotency and rollback | NO-GO. Implemented and tested in the working tree, including PostgreSQL-specific tests on a disposable server (section 10.9). Not committed, not independently reviewed. |
| G7 | Verified backup, with a restore test fingerprint match | NO-GO |
| G8 | Fresh reconciliation equals Phase 2 counts; before-state file hashed and archived | NO-GO |
| G9 | Dry-run preview approved by the owner by file hash | NO-GO |
| G10 | Maintenance window, no concurrent importer, admin or payment activity | NO-GO |
| G11 | Post-change verification and rollback steps rehearsed on the restored scratch copy | NO-GO |
| G12 | Dev credential rotation completed, or explicitly waived by the owner | NO-GO |
| G13 | Owner supplies and approves the WordPress ids of the two anomalous orders (section 1.5); a reviewed code change records exactly those 2 ids in `APPROVED_ANOMALY_WORDPRESS_IDS` | NO-GO. The registry is empty; the ids were never provided. |
| G14 | The approval file for the batch is recorded in `AUTHORIZED_APPROVALS` (approval SHA-256 → `approval_ref`) by a reviewed code change, and the owner confirms that change | NO-GO. No approval exists. |
| G15 | `orders 0008` and `payment 0001` applied to the target through the approved deployment process (the command refuses while they are pending) | NO-GO. Both are unapplied in dev. |
| G16 | A reviewed code change sets `EXECUTION_ENABLED = True` for the approved run only, and resets it afterwards | NO-GO |
| G17 | Owner decides the 18 large IRHT orders (`REVIEW_LARGE_IRHT`) and the wholesale threshold value (`REVIEWED_WHOLESALE_THRESHOLD`) | NO-GO |
| G18 | Rollback rehearsed end-to-end on the restored scratch copy (apply, then rollback, then reconciliation equals the before-state) | NO-GO |

---

## 8. Owner decisions required

1. Confirm the meaning of IRR and IRHT for this store, and the actual date of the currency setting change (G1, G2).
2. Look up the two anomalous orders in WooCommerce and the SEP panel, using the reference numbers in their notes. Decide whether to leave them raw or set an owner-provided value.
3. For cancelled orders, choose between converting and leaving raw. Set a rounding policy for the one 74,025-Rial order.
4. Refund-related orders: confirm that `total_price` should remain the gross amount, and accept that refunds are not represented.
5. Explain the 107 zero-total completed or on-hold orders, or accept them as they are.
6. Name which database(s) a correction applies to.
7. Authorize the importer fix and the correction command as separate code changes.
8. Decide separately on imported coupon amounts (13 usable) and on the wallet credit path for imported orders.
9. Confirm that the production `SECRET_KEY` differs from dev, and approve the dev credential rotation.
10. Supply the WordPress ids of the two anomalous orders and approve their exclusion (G13).
11. Decide the 18 large IRHT orders and confirm the wholesale threshold value (G17).
12. Confirm the reviewed code change that records an approval in `AUTHORIZED_APPROVALS`, and the one that enables execution (G14, G16).

## 9. Work performed in this phase

- **Files changed:** only this report (new file).
- **Commands:**
  - read-only inspection of code and git history;
  - three analysis scripts over the hash-verified WXR copy inside `books-web-1`, printing only counts, codes, dates and booleans;
  - one analysis of the Phase 2 CSV;
  - one set of read-only DB aggregates inside `SET TRANSACTION READ ONLY` (WAL `0/B8EEFD0` before and after).
- **Blocked:** two credential-comparison commands were blocked by the review gate and were not retried.
- **Tests:** none run in this phase.
- **Database:** read-only aggregates only. No inserts, updates or deletes.
- **Migrations:** none created or applied. `orders 0008`, `payment 0001` and `token_blacklist` remain unapplied.

---

## 10. The correction workflow as implemented (Phase 4 hardening)

This section describes the code in `products/management/commands/correct_imported_order_amounts.py`, `audit_imported_order_amounts.py` and `import_wordpress_complete.py` as they stand in the working tree. It addresses findings F1–F7 of the independent safety review. **No real database was connected, read or written in Phase 4.** Every test ran against a disposable PostgreSQL server (section 10.9).

### 10.1 Command interface

| Mode | Invocation (required options) | Database access | Writes files |
| --- | --- | --- | --- |
| Snapshot | `--snapshot --export <wxr> --before-state <csv>` | `REPEATABLE READ, READ ONLY` | `<csv>` and `<csv>.manifest.json` |
| Preview (default) | `--before-state <csv> --before-state-sha256 <sha> --preview <csv> [--rule R…]` | `REPEATABLE READ, READ ONLY` | `<preview>`, `<preview>.summary.json`, `<preview>.approval-request.json` |
| Apply | `--apply --rule <one rule> --before-state … --before-state-sha256 … --approval-file … --approval-sha256 … --execution-report <csv>` | Read-only phase, then one write transaction | Execution report |
| Rollback | `--rollback --rule <one rule> --before-state … --before-state-sha256 … --approval-file … --approval-sha256 … --execution-report <csv> --execution-report-sha256 <sha> --rollback-report <csv>` | Read-only phase, then one write transaction | Rollback report |

Common rules:

- Output files are created exclusively before any work starts. An existing path is refused. Incomplete outputs are removed when a run refuses before writing.
- `--wholesale-threshold` affects the snapshot only. `--database` selects the Django alias.
- **`--apply` and `--rollback` are refused unconditionally while `EXECUTION_ENABLED = False`**, before any input is read. A test asserts that the constant is `False`.
- The command refuses to run inside an existing transaction, because `SET TRANSACTION` must be the first statement of its transaction.

### 10.2 Artifacts and how they bind together

1. **Before-state** (`kasra-order-amount-before-state/v2`). One row per imported order, with its original values (`total_price_before`, `is_paid_before`), rule, reason code, factor and proposed value. The manifest records:
   - the CSV's SHA-256, row count, per-rule counts and sums;
   - the wholesale threshold used;
   - a fingerprint of all imported orders (SHA-256 over `pk, wordpress_id, total_price, is_paid`, plus count and sum);
   - the **classification policy** and its SHA-256 (section 10.3);
   - the **database identity** (section 10.4).
2. **Preview.** Deterministic rows separated into `PROPOSED`, `ALREADY_APPLIED`, `CONFLICT`, `OWNER_REVIEW`, `REJECTED`, `NOT_SELECTED` and `NO_CHANGE`, and a summary. The summary lists `apply_blockers`. Today these are always at least:
   - `EXECUTION_DISABLED_IN_CODE`
   - `ANOMALY_REGISTRY_NOT_OWNER_APPROVED`
   - `NO_AUTHORIZED_APPROVAL_RECORDED`

   Conditionally, it also lists `WHOLESALE_THRESHOLD_NOT_REVIEWED`, `DATABASE_IDENTITY_NOT_VERIFIED`, `IMPORTED_ORDERS_CHANGED_SINCE_BEFORE_STATE` and `CONFLICTS_PRESENT`.
3. **Approval request.** Lists every value an approval must bind. It is unsigned and is not an approval.
4. **Approval file** (`kasra-order-amount-correction-approval/v2`). It must contain exactly these keys:
   - `format`, `approval_ref`, `rules` (one rule)
   - `before_state_sha256`, `preview_sha256`
   - `currency_factors`
   - `classification_policy_sha256`, `wholesale_threshold_toman`, `anomaly_wordpress_ids`
   - `database_identity`, `imported_orders_fingerprint_sha256`

   Each value must equal the corresponding before-state or manifest value.
5. **Authorization, separate from integrity.** `--approval-sha256` only proves that the file is intact. Apply and rollback also require the approval's SHA-256 to be recorded in `AUTHORIZED_APPROVALS` (SHA-256 → `approval_ref`), and the recorded `approval_ref` must equal the file's.
   - That registry can only change through a reviewed code change.
   - **It is empty.** The repository has no other designated approval process.
   - The owner must confirm the reviewed change that adds an entry (G14).

### 10.3 Classification and exclusion rules

The precedence is R7, R3, R8, R6, R5, R4, R2, R1B, R1A. The full policy is hashed: version, precedence, anomaly ids, anomaly flag, large-IRHT limit, reviewed threshold, reason codes and factors. The hash is bound into the before-state manifest and the approval, and every later step refuses if the hash or the policy changes ("Classification policy changed since the before-state was recorded").

**R7, the two cancelled SEP IRHT anomalies (F1).** Two independent exclusion paths, both checked before any other rule:

1. **Stable id registry.** `APPROVED_ANOMALY_WORDPRESS_IDS` → `EXCL_R7_APPROVED_ANOMALY_ID`, regardless of status, payment method, amount or threshold. **It is empty: the ids were never provided or approved.** Phase 3 deliberately did not record them.
2. **Heuristic flag.** `CANCELLED_SEP_ANOMALY` → `EXCL_R7_ANOMALY`. The flag is raised for a cancelled IRHT order above 20,000 source units with "sep" in its payment method. **It no longer depends on `--wholesale-threshold`**, which closes the high-threshold bypass.

Apply and rollback additionally refuse, via `check_anomaly_registry`, unless all of the following hold:

- the registry holds exactly 2 ids;
- each registry id is an R7 row of the before-state;
- every flagged row is in the registry.

So the payment-method bypass (an anomaly whose method is edited away from SEP) is stopped by the id registry once it is filled, and **nothing can be applied while the registry is empty**. At apply time each target is re-classified from the before-state under the current policy (`assert_batch_eligible`), so a hand-edited before-state cannot carry an R7 row into a batch.

**Large IRHT totals (F3).** Any IRHT order above 20,000 source units that would otherwise be R2, R4 or R5 keeps its rule but gets `REVIEW_LARGE_IRHT` (`OWNER_REVIEW`, no proposed value), whatever its status, payment method or the threshold.
- The limit is fixed, measured in source units, and part of the policy hash.
- From the Phase 2 reconciliation this covers the **18** non-cancelled IRHT orders above that size (6 completed, 12 on-hold). The 2 cancelled ones are the R7 anomalies.
- These counts come from the Phase 2 report; they were not re-measured in Phase 4.

**Wholesale threshold.** It only splits R1A from R1B. Apply and rollback refuse a before-state built with any value other than `REVIEWED_WHOLESALE_THRESHOLD` (20,000,000 Toman). That value is itself still an owner decision (G17).

**Factors.** Still `PROVISIONAL_UNAPPROVED`. The approval must state the factor of every currency in the batch. **IRHT × 1000 is not approved.** R2 and the IRHT parts of R4 and R5 stay blocked by G2.

### 10.4 Database identity (F4)

The snapshot records:
- `database_name`
- `database_oid`
- `server_version_num`
- `cluster_name`
- `system_identifier` (from `pg_control_system()`)

Inside the write transaction, after the advisory lock, the live identity is re-read and compared. The command refuses in three cases:
- **Not PostgreSQL:** "Only a PostgreSQL target can be verified".
- **A required key is missing:** "identity is incomplete". The keys are name, oid, system identifier and version.
- **Any of the five values differs:** "not the database recorded in the before-state".

The approval also carries the identity, so an approval cannot be reused against another database.

### 10.5 Transaction and lock semantics (actual)

- **Reads.** Each read phase is its own transaction. Its first statement is `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY`, so orders and payments come from one snapshot.
- **Writes**, in order, in one transaction:
  1. `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` (first statement).
  2. `pg_try_advisory_xact_lock(ADVISORY_LOCK_KEY)`. If it is not acquired, refuse. The lock is released automatically at commit or rollback.
  3. Identity check.
  4. `SELECT … FOR UPDATE NOWAIT` on the target ids, in chunks of 1,000 (`ID_CHUNK`).
     - A row locked elsewhere fails immediately ("locked by another transaction (NOWAIT)", 55P03).
     - A row changed by a transaction committed after the snapshot fails with a serialization failure (40001).
     - A missing row refuses.
  5. Payment re-check: if any `Payment` row exists for a target, or the payment table is missing, refuse.
  6. Compare-and-set per row: `filter(pk, wordpress_id, total_price=<before>, is_paid=<before>).update(total_price=<after>)`. Every row must report exactly 1 update.
  7. Post-update sum check against the preview.
- **Importer exclusion.** The order importer holds the **session-level** `pg_try_advisory_lock` on the same key for the whole order import, and refuses to start if it cannot get it. Correction or rollback and the order import are therefore mutually exclusive.
  - Advisory locks are re-entrant within one session, so this protects against *other* sessions only.
  - On non-PostgreSQL databases the importer does not lock; the correction refuses to write there anyway.
- **Schema.** Before reading, apply and rollback refuse while migrations of `orders` or `payment` are unapplied. In dev, `orders 0008` and `payment 0001` are unapplied, so **apply refuses against the dev database as it is today** (G15).
- `save()`, signals, timestamps, `is_paid`, status and payment rows are never touched. Only `total_price` is updated.

### 10.6 Execution reports and outcome status (F7.8, F7.9)

Apply writes `INTENDED` rows and a `RUN_STARTED` marker **before** the transaction, then exactly one final marker:

| Final marker | Meaning |
| --- | --- |
| `RUN_COMMITTED` | Committed |
| `RUN_ROLLED_BACK` | The body failed (including an interruption); nothing changed |
| `RUN_COMMIT_UNKNOWN` | The body finished but the commit raised. The outcome is unknown; do not retry blindly. A preview shows which values the orders hold. |
| `RUN_NOOP_ALREADY_APPLIED` | Every target already held its corrected value; nothing written |

- A report that ends at `RUN_STARTED` (process killed) is accepted by rollback, which resolves the state from the database.
- Rollback refuses a report ending in `RUN_ROLLED_BACK`.
- Rollback reports use the same scheme: `ROLLBACK_INTENDED`, `ROLLBACK_STARTED`, then `ROLLBACK_COMMITTED`, `ROLLBACK_ROLLED_BACK`, `ROLLBACK_COMMIT_UNKNOWN` or `ROLLBACK_NOOP_ALREADY_RESTORED`.
- Each command prints `execution_report_sha256=` or `rollback_report_sha256=`. Record this value: rollback requires it.

### 10.7 Rollback procedure (F2)

**Rollback is a separate, explicit mode and is disabled in code like apply.** It must never be run against a real database without the full GO checklist. It is not a substitute for the verified backup.

1. Keep the before-state, its manifest, the approval file, the execution report and the recorded `execution_report_sha256` unchanged and read-only.
2. Run `--rollback` with the same rule, before-state, approval, the execution report and its SHA-256, and a new `--rollback-report` path.
3. The command validates the execution report:
   - its hash;
   - header and column count;
   - marker sequence and totals;
   - binding to this approval, before-state and preview;
   - no duplicate order or WordPress ids;
   - every row is in the approved batch, with values equal to the before-state;
   - the batch is complete.

   Tampered, ambiguous or incomplete reports are refused.
4. It reads the current state and classifies every target. It refuses if any order is:
   - missing;
   - has a changed `wordpress_id` or `is_paid`;
   - has a payment;
   - holds neither its corrected nor its original value.

   It also refuses a **mixed** state (some corrected, some original); in that case, restore from the verified backup.
5. If every order already holds its original value, it writes `ROLLBACK_NOOP_ALREADY_RESTORED` and changes nothing, so repeated rollbacks are safe.
6. Otherwise it restores in one write transaction with the semantics of section 10.5, using compare-and-set `filter(pk, wordpress_id, total_price=<after>, is_paid=<before>).update(total_price=<before>)`. A post-rollback sum check follows. Any failure rolls the whole batch back.
7. Afterwards, re-run the reconciliation. It must equal the before-state for the batch.

### 10.8 Maintenance window and drift detection (F5)

**Rule:** no order import, admin bulk action or payment activity may run from the snapshot until post-change verification is complete, or until the rollback is verified. The advisory lock enforces mutual exclusion with the importer only *while* a correction or rollback is running. Between snapshot, preview, approval and apply, the protection comes from drift detection:

- An order added after the snapshot appears as `NOT_IN_BEFORE_STATE`. A deleted target, a changed `total_price`, `is_paid` or `wordpress_id`, or a new payment appears as a `CONFLICT`. Apply refuses with the conflict counts, and the fingerprint must also match.
- Rows of *other* batches corrected after this before-state make the snapshot stale, and apply refuses. **Each batch, R1A then R1B, needs its own fresh snapshot, preview and approval.**
- A changed source export or policy produces a different classification or policy hash, so the old approval no longer matches.
- An importer re-run never overwrites `total_price` or `is_paid` of existing orders. It refreshes only `order_notes` and `payment_method`, and reports differences as `STORED_PRESERVED`. This is tested on corrected orders.

### 10.9 PostgreSQL validation performed (F6) and its limits

Environment:

- Docker container `kasra-p0-2-disposable-pg`, PostgreSQL 16 (`server_version_num` 160015, the same major version as `books-db-1`), with `cluster_name=kasra_p0_2_disposable`.
- It is on the internal network `kasra-p0-2-disposable-net`, with no route to `books-db-1`. It uses a non-superuser role and a throw-away password.
- The settings module `config/settings_isolated_test.py` refuses known real hosts. `config/test_runner.py` verifies the cluster name and that the role is not a superuser before creating `test_kasra_p0_2`. The verified `system_identifier` is printed in every run.

Covered by **real PostgreSQL behaviour**, in `products/tests_order_amount_correction_pg.py`:

- **Read transaction:** `REPEATABLE READ` + `READ ONLY` (a write fails with 25006). `SET TRANSACTION` after a query fails with 25001, and the command refuses to run nested.
- **Write transaction:** `REPEATABLE READ`, with the advisory lock acquired immediately after the `SET TRANSACTION`.
  - While the write transaction runs, a second session cannot take the advisory lock, and a concurrent `UPDATE` of a target row fails with 55P03.
  - The lock is released at commit.
- **Advisory lock held by another session:** apply and rollback are both refused.
- **Importer exclusion:** the importer is refused while the lock is held, holds the lock for the whole order import, and releases it afterwards.
- **Row locks:** a row locked by another transaction fails immediately under `NOWAIT`.
- **Serialization failure:** a commit by another session after the snapshot gives a serialization failure and a rolled-back run.
- **Payment re-check:** a payment committed between the read phase and the write transaction is caught inside the write transaction.
- **Real commit-time failure:** a deferred foreign-key violation (23503) gives `RUN_COMMIT_UNKNOWN`, an unchanged database, a no-op rollback, and then a successful retry.
- **Large id lists:** 6,002 orders are locked in 7 chunks, applied and rolled back.
- **Schema:** with migrations applied, the check passes and the column types are as expected (`total_price` and `amount` are `bigint`). A pending migration refuses apply.

Covered with **mocks** (logic only, not proof of PostgreSQL behaviour): a commit failure injected on the connection, `KeyboardInterrupt` in the middle of a batch, a failure mid-batch, and a concurrent compare-and-set miss.

**Limits.**
- The tests ran on PostgreSQL 16.x on Linux in Docker, not on the dev or production server, and the dev data was not used.
- `system_identifier` is readable by a non-superuser here; whether the production role can read it must be checked before any run. If it cannot, the command refuses.
- A commit that succeeds on the server but whose acknowledgement is lost cannot be distinguished from a failed commit. It is reported as `COMMIT_UNKNOWN`, and a fresh preview is needed.

### 10.10 Backup and restore requirements

These are unchanged from sections 5.2 and 5.6, and still required (G7, G11, G18). Rollback is the first-line remedy for a committed batch whose rows are untouched since. The verified `pg_dump` and a rehearsed restore are required for every other case:
- a mixed state;
- `COMMIT_UNKNOWN` with inconsistent rows;
- a lost report;
- rows changed after the correction.

### 10.11 Known limitations and NO-GO conditions

Execution is NO-GO while **any** of the following holds. Today, all of them hold.

- `EXECUTION_ENABLED = False` (G16).
- `APPROVED_ANOMALY_WORDPRESS_IDS` is not exactly the 2 owner-approved ids (G13). **This input is missing:** the ids were never supplied and must not be inferred.
- No entry in `AUTHORIZED_APPROVALS` for the approval file (G14).
- `orders 0008` or `payment 0001` is unapplied on the target (G15).
- The before-state used a threshold other than the reviewed one, or the threshold itself is not owner-approved (G17).
- The identity of the target database cannot be read completely, or differs from the before-state.
- Any conflict, fingerprint drift or stale batch.
- H1 or H2 unconfirmed (G1, G2). Owner decisions missing for R4, R5, R7, rounding and the 18 large IRHT orders (G3, G17).
- No verified backup or restore rehearsal (G7, G11, G18). No maintenance window agreed (G10).
- The code is uncommitted and has not been independently reviewed (G5, G6).

Other limitations:

- The fingerprint covers `pk, wordpress_id, total_price, is_paid` of imported orders. It does not cover notes or payment method, which the importer may refresh.
- The maintenance window between snapshot and apply is procedural; only drift detection, not a lock, protects it.
- Refunds, coupons and wallet credits remain out of scope (section 1.6).

## 11. Work performed in Phase 4

- **Code changed:**
  - `correct_imported_order_amounts.py` (rewritten: v2 artifacts, policy binding, anomaly registry, identity binding, authorization registry, rollback mode, chunked locks, commit-outcome tracking, schema check);
  - `audit_imported_order_amounts.py` (the anomaly flag no longer depends on the threshold);
  - `import_wordpress_complete.py` (advisory-lock exclusion around the order import; protection of existing orders unchanged).
- **Tests:**
  - updated `products/tests_order_amount_correction.py`;
  - added `products/tests_order_amount_correction_safety.py` and `products/tests_order_amount_correction_pg.py`;
  - one test added to `products/tests_order_amount_audit.py`.
- **Test infrastructure:** `config/settings_isolated_test.py` and `config/test_runner.py`, both for the disposable server only.
- **Results on the verified disposable PostgreSQL:** the full suite ran 332 tests with 2 failures. Both are `products.tests.CatalogDiscoveryTest` locale assertions that expect English text while `LANGUAGE_CODE = 'fa'`. They are unrelated to this work: neither file was changed. All correction, audit, import, safety and PostgreSQL tests passed.
- **Database:** no real database was connected. No migration was created or applied to any real database.
