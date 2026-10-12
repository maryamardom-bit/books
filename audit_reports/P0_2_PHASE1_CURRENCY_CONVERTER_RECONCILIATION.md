# P0-2 Phase 1 — Safe Currency Converter & Read-Only Reconciliation

Date: 2026-10-11 · Branch: `cursor/payment-hardening-and-architecture-review` (HEAD `9cbcdbc`, uncommitted)

Status: implementation and tests only. **NO-GO remains in force for every stored monetary correction.**
No order amount, status, payment, wallet, coupon or product price was changed. No migration was
created or applied. The reconciliation command has **not** been run against the development or
production database; it has only been exercised against Django's throwaway test database.

## 1. Files

| File | Change |
| --- | --- |
| `core/money.py` | New. Pure converter `woo_amount_to_toman`, plus `parse_amount`, `normalize_currency`, exceptions. |
| `products/management/commands/audit_imported_order_amounts.py` | New. Read-only reconciliation command and its pure functions. |
| `core/tests.py` | Added `WooAmountToTomanTest` (16 tests). |
| `products/tests_order_amount_audit.py` | New. 23 tests for reconciliation, CSV and command behaviour. |
| `audit_reports/P0_2_PHASE1_CURRENCY_CONVERTER_RECONCILIATION.md` | This report. |

The P0-1 changes (`orders/models.py`, `payment/services.py`, `orders/tests.py`, `payment/tests.py`,
`accounts/templates/accounts/order_history.html`) were not touched in this phase.

## 2. Converter

`core.money.woo_amount_to_toman(raw, currency) -> int`

| Code | Meaning (provisional) | Toman per unit |
| --- | --- | --- |
| `IRR` | Rial | 0.1 |
| `IRT` | Toman | 1 |
| `IRHR` | thousand Rial | 100 |
| `IRHT` | thousand Toman | 1000 |

- Decimal arithmetic only, `ROUND_HALF_UP` to whole Toman; the precision is widened per input
  so large amounts never round silently.
- Accepts `int`, `Decimal` and plain decimal strings (`[+-]?digits[.digits]`, surrounding spaces allowed).
  Floats go through `repr()` (their shortest round-tripping decimal string); non-finite floats are rejected.
- Rejects with `InvalidAmountError`: negatives, NaN/±Infinity, empty or malformed strings
  (thousand separators, exponent notation, Persian digits, `.5`, `5.`), `bool`, `None` and other types.
- Rejects unknown or missing currency codes with `UnsupportedCurrencyError`; a currency is never guessed
  and never defaults to Toman. Codes are trimmed and upper-cased.
- Both exceptions subclass `MoneyConversionError(ValueError)`.
- `woo_price_to_toman` (the importer's size-based heuristic) is not used.

Examples (all covered by tests): `("1965000","IRR")`→196500, `("1425","IRHT")`→1425000,
`("29028.2","IRHT")`→29028200, `("1965005","IRR")`→196501, `("0", any)`→0.

## 3. Reconciliation command

`python manage.py audit_imported_order_amounts --export <WXR> [--output <csv>] [--overwrite] [--skip-db] [--wholesale-threshold <Toman>] [--database <alias>]`

What it reads:
- From the export: post id, status, `_order_currency`, `_order_total` and `_payment_method` of each
  `shop_order`; post id, parent, `_order_currency` and `_refund_amount` of each `shop_order_refund`.
  Billing fields, customer notes and comments are never read.
- From the database: `wordpress_id` and `total_price` of orders with a non-null `wordpress_id`, and nothing else.
  It issues a single SELECT. On PostgreSQL outside an existing transaction, the read runs inside
  `SET TRANSACTION READ ONLY`. The `status` column is not read, because `orders.0008` is not yet
  applied on the development DB.

Classifications (one per row):

| Classification | Meaning |
| --- | --- |
| `MATCH` | stored == converted source total |
| `RAW_IRR` / `RAW_IRHT` | stored == source number truncated to an integer, i.e. imported without conversion |
| `MISMATCH` | compared, but neither of the above |
| `MISSING_IN_DB` | in export, no imported order with that id |
| `MISSING_IN_EXPORT` | imported order whose id is not in the export |
| `DUPLICATE_IN_EXPORT` / `DUPLICATE_IN_DB` | id occurs more than once; reported as errors, never compared |
| `SOURCE_INVALID` | bad id, unparseable amount, or unknown/missing currency |
| `NOT_COMPARED` | `--skip-db` was used |
| `NOT_APPLICABLE` | refund row whose parent order is not in the export |

**Zero-total policy:** a zero source total converts to 0 in every currency. A stored value of 0 is `MATCH`,
with the flag `ZERO_TOTAL`. A non-zero stored value is `MISMATCH`. `RAW_*` is never assigned to a zero total.

Flags (several per row are possible):
- `ZERO_TOTAL`, `REFUNDED_STATUS` and `HAS_REFUND_RECORD`.
- `WHOLESALE_SIZED`: converted total is strictly above 20,000,000 Toman, configurable.
- `CANCELLED_SEP_ANOMALY`: wholesale-sized, `wc-cancelled`, `IRHT`, and a SEP gateway.
- `IRR_NOT_DIVISIBLE_BY_10` and `REFUND_WITHOUT_PARENT`.
- `INVALID_SOURCE_AMOUNT`, `INVALID_SOURCE_CURRENCY` and `INVALID_SOURCE_ID`.

Console summary:
- Counts by classification.
- Counts and Decimal sums by currency: source, expected Toman, stored and discrepancy.
- Counts by export status, and counts by flag.
- Database count and duplicates.
- Expected, stored and discrepancy totals over the compared rows.
- Assumptions and unavailable data.

CSV columns: `record_type, wordpress_id, parent_wordpress_id, source_status, source_currency, source_amount,
expected_toman, stored_total, discrepancy, classification, flags, note`.
- No names, emails, phones or addresses.
- Text starting with `= + - @ TAB CR` is prefixed with `'` so spreadsheets don't execute it as a formula.
- Standard CSV quoting.
- Rows are sorted deterministically, so repeated runs produce byte-identical files.
- An existing output file is refused unless `--overwrite` is passed.

A missing, malformed or order-less export stops with `CommandError: ... Reconciliation cannot be completed.`
In that case no output file is created.

## 4. Assumptions and items needing owner approval

1. **IRHT = thousand Toman is not verified for this store.** The factor 1000 rests on the Persian WooCommerce
   code convention and the continuity analysis in the P0-2 audit. The owner should confirm the store's
   currency settings history, for example from a WooCommerce settings screenshot or the `woocommerce_currency`
   option history.
2. The currency switch date (around 2026-04) is inferred from the data, not documented.
3. The 20M Toman wholesale threshold is a review heuristic taken from the audit distribution.
4. The two cancelled SEP IRHT orders (4,400,125 and 2,401,625 IRHT) need manual review. They may have been
   entered in the wrong unit.
5. Refunds, shipping and discounts are not imported into Django and are not reconciled. Line items are not
   in the export.
6. `RAW_*` assumes the importer's `int(float(_order_total))` truncation.

## 5. Tests (run inside `books-web-1` against the throwaway `test_postgres` DB, dummy SEP/SMS env)

| Run | Result |
| --- | --- |
| `core.tests.WooAmountToTomanTest` + `products.tests_order_amount_audit` | 39 tests, OK |
| `payment orders core accounts` (includes the P0-1 tests, gateway Rial multiplier test, order model/state machine/admin tests) | 108 tests, OK |
| Full suite | 222 tests: 220 OK, 2 failures |

The 2 full-suite failures are the pre-existing locale tests `products.tests.CatalogDiscoveryTest.test_category_library_page`
and `test_home_exposes_editorial_context`. They expect English strings that the `fa` locale translates.
Both failed before this phase too, and they are unrelated.

There are no existing importer tests in the repository, so no importer regression could be run.

`makemigrations --check --dry-run` reports only the pre-existing, unrelated `products/0013_alter_product_category`.
This phase adds no model change, and no migration was written.

## 6. Proposed next step (requires separate authorization)

This is a read-only run against the **development** database, with the export copied into the container's
`/tmp` (not into the repository, and the DB is not touched):

```
docker cp D:\copy_data_kasra\wordpress.2026-09-24.xml books-web-1:/tmp/wordpress.xml
docker exec books-web-1 python manage.py audit_imported_order_amounts --export /tmp/wordpress.xml --output /tmp/order_amount_audit.csv
docker cp books-web-1:/tmp/order_amount_audit.csv .\audit_reports\order_amount_audit.csv
```

`--skip-db` can be run first to check the export side alone. After that run, review the classification counts
and anomalies with the owner before designing any correction. A correction would need its own approval, a
verified backup and a dry-run plan.
