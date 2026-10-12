# Kasra Publishing — WordPress vs Django Feature Gap Audit

| | |
|---|---|
| Audit date | 2026-10-11 |
| Live site | https://kasrapublishing.ir/ (WordPress + WooCommerce, theme `terashop-1`, LiteSpeed) |
| Django project | `D:\django_project\books` (Django 6.0.2, Python 3.14, PostgreSQL 16) |
| Source export | `D:\copy_data_kasra\wordpress.2026-09-24.xml` (WXR, full site export) |
| Mode | Read-only audit. No application code, settings, templates, models, migrations, dependencies or database records were changed. This report is the only file written inside the project. |

---

## How to read this report

**Status vocabulary** (applies to the Django rewrite, measured against the live site):

| Status | Meaning |
|---|---|
| **VERIFIED** | Implemented, and the relevant workflow passed an automated test run during this audit (SQLite test database, payment gateway mocked) or a direct URL-resolution check. |
| **PARTIAL** | Implemented, but incomplete, inconsistent with live behaviour, or broken for part of the data. |
| **MISSING** | Required behaviour confirmed on the live site / export, and confirmed absent in Django code. |
| **UNVERIFIED** | Two kinds, counted together: **UNVERIFIED (implemented)** = code exists but no test or runtime check exercised it; **UNVERIFIED (evidence)** = insufficient evidence on the live side (e.g. checkout form not inspected) to decide. Never counted as missing. |
| **NOT APPLICABLE** | Live site does not have it (Django-only enhancement), or it is not relevant to the rewrite. |

**Priority:** P0 = blocks safe launch (broken core workflow, data loss, transactional/security risk). P1 = required for launch parity. P2 = important, can follow shortly after launch. P3 = optional / polish.

**Evidence sources:** live HTTP GET requests (read-only, no forms submitted, nothing added to the cart); aggregate scans of the WXR export (no personal data copied into this report); static reading of the Django source; `python manage.py test` against a temporary SQLite database; `makemigrations --check --dry-run`; `django.urls.resolve()` checks.

**Provisional conclusions** (see Section J): live cart/checkout form fields, authenticated WooCommerce account pages and WP admin were not inspected; the Django PostgreSQL container was stopped, so no Django database counts are reported; the WXR export contains no order line items.

---

## A. Executive Summary

**Bottom line:** the Django rewrite has a solid, well-tested core (catalog, Persian search, session cart, SEP payment with idempotent callbacks, order state machine), but it is **not ready to replace the live store**. Six P0 issues block a safe launch. Four of them are data-migration problems that could charge customers incorrect amounts or silently destroy business rules. The other two are missing shipping charges and a production web server that cannot serve HTTPS.

### Feature counts (150 features assessed)

| Status | Count |
|---|---|
| VERIFIED | 21 |
| PARTIAL | 48 |
| MISSING | 40 |
| UNVERIFIED | 35 (22 implemented-but-untested, 13 insufficient evidence) |
| NOT APPLICABLE | 6 |
| **Total assessed** | **150** |

### What to implement first (P0)

1. **Imported orders are payable again.** Imported cancelled and on-hold orders (212 + 64 in the export) keep the default status `PENDING_PAYMENT`. The order history page shows them a working **Pay** button. (DM-03)
2. **Imported order totals are 10× too large.** WooCommerce totals are stored in Rial (`IRR`), or in thousand-Toman for 90 orders from 2026 (`IRHT`). The importer copies them into a Toman field unconverted, so a re-paid historical order would charge 10× (or 1/1000×) the real amount. (DM-01)
3. **Historical orders have no line items.** The WXR export contains no line items, so 5,838 imported orders are empty shells. A WooCommerce database dump is needed, or an explicit decision to archive them as read-only. (DM-02)
4. **Coupons lose all their restrictions.** 2,025 live coupons carry restrictions: minimum spend on 1,174, usage-per-user limits on 1,986, category limits on 1,225, exclude-sale-items on 1,996, and Smart Coupons store credit on 1,167. The Django model and importer support only percent/amount, maximum uses and expiry, so every migrated coupon becomes **more permissive**. Django also has no admin screen for coupons. (CC-05, DM-04, AD-02)
5. **No shipping methods or shipping charges.** On the live store, 1,978 orders paid a shipping fee across six shipping methods (post, express post, courier, Tipax, flat rate, free). Django charges no shipping at all, and never imported product weights. (CC-08, PD-14)
6. **The production web server cannot serve the site.** `nginx/nginx.conf` listens only on port 80 with a placeholder `server_name`, while `settings_production.py` forces an HTTPS redirect. The site would be unreachable or stuck in a redirect loop. (SE-02)

### Then (P1, required for launch parity)

- **Legacy URLs (P1):** preserve every legacy URL or 301-redirect it, and keep serving the old `/wp-content/uploads/` media.
- **Catalog visibility:** hide the 334 private products that the importer published.
- **Product data:** add the editor (ویراستار) field.
- **Checkout:**
  - guest checkout (58% of live orders were guest orders);
  - structured address and postcode;
  - bank transfer as a payment method (31% of live orders).
- **Customer notifications:** email, plus SMS with the postal tracking code.
- **Trust and resilience:**
  - the Enamad trust seal;
  - self-hosted frontend assets (no runtime CDN dependency);
  - backups;
  - a plan for migrated customers, who have unusable passwords and no phone numbers.
- **Misleading UI:** the installment option charges the full amount, so hide it.
- **Integrations:** decide the fate of the WooCommerce-dependent mobile app and Telegram bots.

### Separate urgent finding on the live site

The live site's TLS certificate (Let's Encrypt E7) **has expired** (around May 2026). Browsers currently show a security warning. This is independent of the migration, but it affects customers today.

### Where Django is already better than the live site

- **Search:** live search finds nothing by ISBN, translator, or Arabic-variant spelling (for example ي instead of ی). Django handles all three, with Persian normalization and tests.
- **Payments:** Django has idempotent payment callbacks with amount verification and reversal.
- **Orders:** price snapshots on order items, and a status state machine.
- **Extras:** returns workflow, author index, best-seller and new-release pages, a FAQ chatbot, and a REST API.

---

## B. WordPress Inventory

### B.1 Platform

| Item | Evidence |
|---|---|
| Server / TLS | LiteSpeed; HTTP→HTTPS 301; Let's Encrypt E7 certificate **expired** |
| Theme | `terashop-1` (Persian WooCommerce theme); Elementor + Elementor Pro page builder |
| Commerce | WooCommerce; all 623 products are `simple` type (no variable, grouped, downloadable or virtual products) |
| Active plugins (from asset URLs / export meta) | WOOF product filter (`?swoof=`), meteor-slides, dFlip flipbook, woocommerce-product-slider, variation-swatches, wp-statistics, woocommerce-delivery-notes (invoices/packing slips), YellowPencil (CSS), WooCommerce Smart Coupons, Persian WooCommerce SMS & shipping, SEP (Saman) gateway, AsanPardakht gateway, WP All Import, mr2app "woo2app" (mobile app) |
| SEO | No Yoast/RankMath metadata. `robots.txt` disallows only `/wp-admin/`. `sitemap.xml`, `sitemap_index.xml`, `wp-sitemap.xml` all 404. Product pages have canonical, `og:type product.item`, JSON-LD Product/Offer/BreadcrumbList. Archives have BreadcrumbList but no canonical. |
| Public APIs | `/wp-json/wp/v2/product` public; WooCommerce Store API 404; `/feed/` RSS present |

### B.2 Content and data volumes (WXR export, aggregate only)

| Entity | Count / detail |
|---|---|
| Products | 623 (289 published, 334 private; every private product is out of stock) |
| Product visibility terms | exclude-from-catalog 464, exclude-from-search 454 |
| Product categories | 14: root "کتاب‌های کتابکده کسری" + 13 children (architecture design, interior, urban, landscape, design guides, critique/theory, design basics, digital/parametric, sustainability, project samples, other books, bundles/collections, business & management) |
| Category usage | 110 published products have no category; 78 have more than one |
| Product tags | 4 promotional tags (new releases; special-discount subject bundles; special-discount series books; special-discount books), 51 assignments |
| Product attributes | author 778, translator 392, **editor 133 (101 published)**, size 587, binding 587, publisher 587, ISBN 581, pages 584, print number 583, print year 575, publication date 574, paper type 16, period 8 |
| Multiple contributors | 156 products with >1 author, 95 with >1 translator |
| Linked products | cross-sells on 105 products, upsells on 6 |
| Physical data | weight on 539 products; no dimensions |
| Media per product | thumbnail on 599, gallery on 3 |
| SKU | 581, no duplicates |
| Stock | `manage_stock=yes` on 613 |
| Pricing | 364 products with zero or empty regular price; 256 priced below 20,000 (thousand-Toman units); 3 priced at 20,000 or more; 139 with a sale price; no scheduled sale dates |
| Reviews | 27 product reviews (all approved), 16 with star ratings; reviews open on 282 products; guest reviews allowed (name + email) |
| Old slugs | `_wp_old_slug` on 14 products |
| Orders | 5,838 `shop_order` (completed 5,517; cancelled 212; on-hold 64; refunded 45) + 72 `shop_order_refund`; 2018–2026 |
| Order currency | `IRR` for all years; `IRHT` (thousand Toman) for 90 orders in 2026 |
| Customers on orders | 3,408 guest orders; 2,429 orders by registered customers |
| Payment methods | SEP ≈3,918; bank transfer (bacs) ≈1,790; AsanPardakht 121; other 9 |
| Shipping methods | free shipping 3,240; custom post 863; flat rate 848; courier 649; express post (پیشتاز) 228; Tipax 5; non-zero shipping charged on 1,978 orders |
| Discounts on orders | non-zero `_cart_discount` on 1,080 orders; no tax |
| Billing fields | email, phone, postcode, city, province, district, address almost always filled; company on 333 |
| Order notes | 25,706 (status changes 10,811, stock notes 7,576, postal tracking codes 3,703, SMS logs 3,266) |
| **Order line items** | **Not present in the export** |
| Coupons | 2,025 published: smart coupon / store credit 1,167, percent 838, fixed cart 19, fixed product 1 |
| Coupon restrictions | minimum amount 1,174; individual use 2,012; usage limit per user 1,986; expiry 2,001; category restriction 1,225; exclude sale items 1,996; free shipping 21; Smart Coupons location restriction, maximum discount, new-customer-only |
| Pages | 14 published, 2 private: contact, shop, cart, checkout, my-account, two home variants (the live home page is Elementor page 1138), app, bot, order terms, online payment guide, demo pages, about, cooperation; private Smart Coupons terms pages |
| Posts | 3 published (news and a digital-book appendix linking 3 Google Drive files), Jalali-date permalinks `/YYYY/MM/DD/slug/` |
| Menus | Main (home, root category, order terms, about, contact, cooperation); User guide (order terms, payment guide, Telegram bot, mobile app); Social (Facebook, Google+, Twitter, Instagram, Telegram) |
| Attachments | 981 (jpg 746, pdf 172, png 37, mp4 3, other); 666 attached to products, 300 unattached |
| Other content types | elementor_library 7, dflip 1, slide 1; no contact-form plugin; 4 WP author accounts (customers are **not** in the export) |

### B.3 Customer-facing behaviour observed on the live site

| Area | Observed behaviour |
|---|---|
| Home | Title + meta description + canonical, no OG/JSON-LD. Sections: "new releases" (driven by the new-releases tag, with a WOOF link) and "special discounts" (bundle grid driven by tags). Footer: quick links, about-store text, invitation to leave comments, **Enamad trust seal**, Instagram, WhatsApp, site-builder credit. |
| Navigation | Main menu items above + "join/account" link + cart counter + product search box (`s` + `post_type=product`). |
| Shop / archives | `/shop/`, `/product-category/<root>/`, `/product-category/<root>/<child>/`, `/product-category/<child>/`, `/product-tag/<tag>/` all 200; `/page/N/` pagination; 12 per page; sort by popularity, rating, date, price ↑, price ↓; WOOF checkbox filter on category and tag. Shop-card add-to-cart buttons hidden by theme CSS; attribute values on cards are not links. |
| Product page | `/product/<persian-slug>/`; breadcrumb Home / root / child / title; price; stock text; quantity + add-to-cart; description (often linking an intro/TOC PDF under `/wp-content/uploads/`); "additional information" tab with all attributes including editor, print year **and** publication date; guest reviews with rating; related products. |
| Search | Searches title and description only. ISBN → 0 results; Arabic-ي variant → 0; translator name → 0. A single result redirects straight to the product; empty results show a no-results page. |
| Cart / checkout | Cart page exists. `/checkout/` with an empty cart redirects (302) to `/cart/`. Checkout form **not inspected** (adding to cart was deliberately not performed). Checkout fields are inferred from order meta: name, phone, email, province, city, district, address, postcode, company, notes, shipping method, payment method. |
| Order terms page | Registration recommended; receipts by email; SMS with postal tracking code (mobile number required); buyer selects postal service type; dispatch next working day; refunds at month-end minus postage and transfer fees; re-shipping charged. |
| Account | Login with username **or** email + password + remember-me; registration with email + password; lost-password. Delivery-notes (invoice) plugin active. |
| Other pages | Payment guide; About; Contact (address, postal code, phone, WhatsApp, email; **no form**); Cooperation (email only, no form); `/app/` (Android APK from the mr2app CDN + iOS); `/bot/` (two Telegram bots). |
| Posts | `/1401/11/26/<slug>/` style permalinks; `/?p=ID` redirects to them; RSS feed. |

---

## C. Django Inventory

### C.1 Functional implementation (backed by code paths that run end-to-end)

| App | Implemented functionality | Test evidence |
|---|---|---|
| `products` | Product catalog (list, 12/page, sort by price/title/author/newest/oldest/rating, category + discount filters), product detail with related books, same-author books, blogs, approved comments, bundles containing the book, `Book` JSON-LD; Persian full-field search with Arabic-variant/ZWNJ/digit normalization (`products/search.py`, `core/text.py`); bundles (`Package`); contributor index and author pages (`products/contributors.py`); best sellers; new releases; login-required moderated comments; ISBN validation/uniqueness | 42 tests (2 fail, locale-dependent) |
| `cart` | Session cart; prices re-read from DB on every iteration; stock caps; `reconcile()` drops unavailable items; discount code apply (POST) / remove; JSON endpoints | 23 tests, all pass |
| `orders` | Login-required checkout (`orders/views.py:14`); server-side total; discount re-validation; `Order` state machine (`DRAFT` → … → `REFUNDED`); `OrderItem` title/price snapshot; 3-day return requests; admin status actions | 31 tests, all pass |
| `payment` | SEP (Saman) gateway: UUID reference, unique (gateway, transaction_id), one PAID payment per order, CSRF-exempt callback matched by reference, idempotent replays, row-locked stock check before verify, server-to-server verify with amount check and reversal, timeouts keep payment pending, zero-total orders bypass gateway; stock decrement + coupon usage + tier advance on completion | 23 tests, all pass (gateway mocked) |
| `accounts` | allauth email login/signup/password reset; custom user (phone, wallet balance, birth date, address, postal code, WordPress id); dashboard; profile edit; order history with Pay / Return buttons | 12 tests, all pass |
| `pages` | Home; about; contact; cooperation; order conditions; archive of imported WP pages/posts (`/p/`, `/p/<slug>/`) | **0 tests** |
| `api` | Read-only products/packages/blogs/FAQ; moderated comments; owner-scoped orders and returns; cart API with quantity limits; profile; JWT; throttling; Swagger | 26 tests, all pass |
| `core` | Persian normalization, ISBN utilities, `/health/` | 11 tests, all pass |
| `services/sms.py` | Kavenegar SMS (synchronous) for order registration, payment, birthday and occasion messages | not exercised (SMS disabled in tests) |
| Importers | `import_wordpress` (live REST scrape), `import_wordpress_wxr` (products from WXR), `import_wordpress_complete` (covers, comments, pages/posts, coupons, orders) | **no tests** |

### C.2 UI-only or non-functional features

| Feature | Why it is UI-only |
|---|---|
| Installment payment option (`orders/views.py:42-68`, `InstallmentPlan` model) | Checkout shows installment plans, but the code comment at `orders/views.py:66` confirms installment orders are charged the **full total** online. |
| Wallet balance (`CustomUser.wallet_balance`) | Credited when a return is approved, but never read by cart, orders or payment, so the credit can never be spent. |
| Tiered discounts (`TieredDiscount`, `products/models.py:536`) | Tier is advanced after payment but never applied to totals (TODO in code); not registered in admin. |
| Stock reservation (`Product.reserve_stock`, `products/models.py:270`) | Never called; `reserved_stock` is always 0. |
| Discount schedule (`discount_start_date`, `discount_end_date`) | Editable in admin but ignored by `is_on_sale()` / `get_discounted_price()` (`products/models.py:190-210`). |
| Home "sale books" and "featured packages" | Computed by the view, not rendered by `home.html` (only a link to `?discount=true`). |
| Checkout prefill | `OrderForm` accepts a `user` argument, but the view never passes it. |

### C.3 Test and build health (run during this audit)

- `python manage.py test` on a temporary SQLite DB: **168 tests, 166 passed, 2 failed**. Both failures (`CatalogDiscoveryTest.test_category_library_page`, `test_home_exposes_editorial_context`) assert English strings while the site language is Persian. They are environment/locale failures, not functional regressions.
- `pages` and `persian_translate` have no tests; none of the importers have tests.
- `makemigrations --check --dry-run`: **one pending migration** (`products/migrations/0013_alter_product_category.py`, alters `Product.category` choices). Not written.
- `manage.py check` warns that CKEditor 4 is unsupported (`ckeditor.W001`).
- Not run: tests against PostgreSQL (container `books-db-1` was stopped), real SEP sandbox, real SMS/SMTP.

---

## D. Gap Matrix

Column abbreviations: **Live** = live-site / export evidence; **Django** = Django evidence. "—" in Priority means no action needed.

### D.1 Catalog (CAT)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| CAT-01 | Shop listing, 12 per page | `/shop/`, 12/page, `/page/N/` | `ProductListView` paginate 12; test hits `/products/?category=` | VERIFIED | — | — | — | — | Test suite |
| CAT-02 | Sort options | popularity, rating, date, price ↑↓ | price ↑↓, title, author, newest, oldest, rating | PARTIAL | No popularity (sales) sort | Low | P3 | Add sales-count sort | Compare sort dropdowns |
| CAT-03 | Category hierarchy & archives | Root + 13 child categories, nested URLs | Fixed 13-value enum incl. PACKAGES; flat `/products/categories/<CODE>/` | PARTIAL | No hierarchy, no Persian category names in URL, categories not editable in admin | Navigation and SEO landing pages change | P1 | Category model (or mapping table) with WP term slugs | Each WP category URL returns matching product set |
| CAT-04 | Multiple categories per product | 78 published products in >1 category | Single `category` field | MISSING | Secondary categories lost | Products disappear from second category | P2 | M2M categories | Count per category vs export |
| CAT-05 | Product tags & tag archives | 4 promo tags, `/product-tag/<slug>/` | No tag model | MISSING | Promo collections (new releases, special discounts) not representable | Home merchandising and tag landing pages lost | P2 | Tag/collection model + import | Tag pages list same products |
| CAT-06 | Faceted filter | WOOF checkbox filter (category + tag) | Single category select + discount toggle | PARTIAL | No multi-select, no tag facet | Low | P3 | Multi-select filter | Manual UI check |
| CAT-07 | Hidden/private products | 334 private; 464 excluded from catalog, 454 from search | `import_wordpress_wxr.py:212` sets `active` for `publish` **and** `private` | MISSING | Private products published | 334 retired out-of-stock books become public | P1 | Import private as inactive; honour visibility terms | Active count = 289 |
| CAT-08 | Bundles/packages | "Special discount" bundle grid | `Package` model, list/detail, add to cart, stock on payment | VERIFIED | — | — | — | — | `test_add_package`, `test_package_stock_decrease` |
| CAT-09 | Related products | "محصولات مشابه" block | Same category/author query in `ProductDetailView` | UNVERIFIED (implemented) | — | — | — | Add test | View test |
| CAT-10 | Cross-sells / upsells | 105 / 6 products | No field; not imported | MISSING | Editorial recommendations lost | Low–medium | P3 | M2M + import | Count linked products |
| CAT-11 | Out-of-stock display & purchase block | "out of stock" label | Stock checks in cart and payment | VERIFIED | — | — | — | — | `test_add_out_of_stock_does_not_insert`, `test_out_of_stock_is_not_verified` |
| CAT-12 | Scheduled sale window | No sale dates used in export | Fields exist; ignored by `is_on_sale()` (`products/models.py:190`) | PARTIAL | Discounts never expire automatically | Revenue leak if staff schedule a sale | P2 | Respect dates or hide fields | Unit test with past end date |
| CAT-13 | Author index & author pages | Not present (attribute values unlinked) | `author_list_view`, `author_books_view` | NOT APPLICABLE | Django-only enhancement | — | — | — | — |
| CAT-14 | Best sellers / new releases pages | Not present as pages | `BestSellersView`, `NewReleasesView` | NOT APPLICABLE | Django-only enhancement | — | — | — | — |

### D.2 Product detail (PD)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| PD-01 | Core bibliographic attributes | author, translator, publisher, ISBN, pages, size, binding, print number | Fields on `Product`, shown in `product_detail.html` | UNVERIFIED (implemented) | — | — | — | Add render test | Compare 10 sample products |
| PD-02 | Editor (ویراستار) | 133 products (101 published) | No field; importer ignores attribute | MISSING | Editor credit lost | Contractual/credit accuracy | P1 | Add field + import | 101 published products show editor |
| PD-03 | Print year vs publication date | Separate attributes (575 / 574) | Importer writes one value into both `year_of_publication` and `publication_date` | PARTIAL | Distinction lost | Bibliographic accuracy | P2 | Map separately | Spot-check products where they differ |
| PD-04 | Paper type, period | 16 / 8 products | Not modelled | MISSING | Minor data loss | Low | P3 | Generic attribute table | Count |
| PD-05 | Multiple contributors | 156 multi-author, 95 multi-translator | Comma-separated `author` (200 chars, `products/models.py:112`); translator stored in `edition` (100 chars, `:123`), labelled "Translator / edition" | PARTIAL | No contributor entities; misnamed field; length limits | Data quality, admin confusion | P2 | Contributor model or renamed fields | Longest names fit; labels correct |
| PD-06 | Cover image | thumbnail on 599 | `image` field, importer downloads `_thumbnail_id` | UNVERIFIED (implemented) | — | — | — | Verify media after import | Count products without image |
| PD-07 | Product gallery | 3 products | Single image only | MISSING | Gallery images lost | Low | P3 | Gallery model | 3 products |
| PD-08 | Description with intro/TOC PDF links | PDFs under `/wp-content/uploads/` | Description HTML copied verbatim; links still point to WordPress uploads | PARTIAL | Links break when WordPress is retired | Lost sample chapters / TOCs | P1 | Migrate uploads (see SEO-07) | Crawl description links → 200 |
| PD-09 | Add to cart with quantity | Quantity + button | Cart add view, JSON | VERIFIED | — | — | — | — | `test_add_product`, `test_replace_quantity` |
| PD-10 | Regular + sale price display | Strikethrough price | `get_discounted_price`, sale badge | VERIFIED | — | — | — | — | Cart discount tests |
| PD-11 | Breadcrumb | Home / root / child / title | Breadcrumb in template (category only) | UNVERIFIED (implemented) | — | — | — | — | Visual check |
| PD-12 | Reviews | Guest reviews with name/email + rating | `CommentCreateView` is login-required, moderated | PARTIAL | Guests cannot review | Fewer reviews | P2 | Allow moderated guest reviews (with anti-spam) | Submit as guest in staging |
| PD-13 | Review moderation | Approved reviews shown | `active=False` until approved; API cannot self-approve | VERIFIED | — | — | — | — | `test_comment_cannot_self_approve` |
| PD-14 | Product weight | 539 products | `weight` field exists; **neither importer maps `_weight`** | MISSING | Weight data lost | Blocks weight-based shipping (CC-08) | P0 | Import `_weight` (units checked) | 539 non-zero weights |

### D.3 Search & navigation (SR)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| SR-01 | Title search | Works | `ProductSearchView` + `build_search_q` | VERIFIED | — | — | — | — | Search tests |
| SR-02 | ISBN / author / translator search | 0 results on live | Searches all text/numeric fields | VERIFIED | Django exceeds live | — | — | — | Search tests |
| SR-03 | Arabic/Persian variants, half-space | Arabic ي → 0 results | `normalize_persian`, variants | VERIFIED | Django exceeds live | — | — | — | `core` tests |
| SR-04 | Single-result redirect | Redirects to product | Always shows list | MISSING | Minor UX | Low | P3 | Redirect when exactly 1 hit | Manual |
| SR-05 | No-results state | No-results page | Template with suggestions | UNVERIFIED (implemented) | — | — | — | — | Manual |
| SR-06 | Legacy search URL `/?s=…&post_type=product` | Indexed / bookmarked format | `/` resolves to home and ignores `s` | MISSING | Old search links land on home | Low–medium | P2 | Redirect `/?s=` → `/products/search/?q=` | `resolve()` + HTTP check |
| SR-07 | Site-wide content search | Searches pages/posts too | Products only | PARTIAL | Pages/posts unsearchable | Low | P3 | Optional | Manual |
| SR-08 | Main menu + cart counter | Present | Present in `_base.html` | UNVERIFIED (implemented) | — | — | — | — | Visual |
| SR-09 | "User guide" secondary menu | Terms, payment guide, bot, app | Only order terms linked; others archived under `/p/wp-page-*` | PARTIAL | Guides unreachable from nav | Low | P3 | Link or retire | Visual |

### D.4 Cart & checkout (CC)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| CC-01 | Cart add/update/remove/clear | WooCommerce cart | Session cart, POST-only mutations | VERIFIED | — | — | — | — | 23 cart tests |
| CC-02 | Server-side price recalculation | WooCommerce recalculates | Prices re-read from DB per iteration; order totals server-side | VERIFIED | — | — | — | — | `test_item_keeps_title_and_price_after_catalog_change`, cart tests |
| CC-03 | Stock cap & cart reconcile | WooCommerce stock check | `reconcile()`, quantity caps | VERIFIED | — | — | — | — | `test_add_caps_quantity_at_stock`, `test_reconcile_drops_unavailable_title` |
| CC-04 | Coupon apply/remove | Coupon field | `apply_discount_code_view`; re-validated at checkout | VERIFIED | Basic only (see CC-05) | — | — | — | `test_apply_discount_code`, `test_empty_discount_code_is_rejected` |
| CC-05 | Coupon restriction rules | min spend 1,174; per-user limit 1,986; category 1,225; exclude-sale 1,996; individual use 2,012; max discount; location; new-customer | `DiscountCode` = percent/amount/max uses/validity only (`products/models.py:489`) | MISSING | Rules cannot be expressed | Coupons become more generous than intended → revenue loss | P0 | Extend model **or** do not migrate restricted coupons | Rule-by-rule unit tests |
| CC-06 | Guest checkout | 3,408 of 5,838 orders were guest orders | `@login_required` (`orders/views.py:14`); `Order.user` required | MISSING | Must register to buy | Conversion loss (58% of historical orders) | P1 | Guest checkout with email + phone | Place sandbox order logged out |
| CC-07 | Checkout fields | email, province, city, district, postcode, address, company, notes | first/last name, phone, free-text address (700), notes | PARTIAL | No email, province, city, postcode, company | Postal dispatch needs postcode; no receipt email | P1 | Structured address fields | Form shows fields; order stores them |
| CC-08 | Shipping methods & cost | 6 methods; shipping charged on 1,978 orders | No shipping model, method or cost; total = items − discount | MISSING | Shipping never charged | Direct revenue loss on every shipped order | P0 | Shipping methods with cost rules (weight/region/free threshold) | Totals include shipping; sandbox payment amount matches |
| CC-09 | Checkout prefill | WooCommerce prefills saved billing | Form supports `user` but view does not pass it | PARTIAL | Retyping each time | Minor UX | P3 | Pass user/profile defaults | Logged-in form prefilled |
| CC-10 | Phone validation | Mobile required for SMS | `CharField(max_length=15)` without validation (`orders/models.py:62`) | PARTIAL | Invalid numbers accepted | Failed SMS / delivery | P2 | Iranian mobile validator | Invalid number rejected |
| CC-11 | Terms acceptance | Not inspected | None | UNVERIFIED (evidence) | — | — | — | Inspect live checkout | Manual |
| CC-12 | Persistent cart across devices | WooCommerce persistent cart for logged-in users | Session only | PARTIAL | Cart lost on another device | Low | P3 | Optional DB-backed cart | Manual |
| CC-13 | Installment option | Not offered | Shown at checkout but charged in full (`orders/views.py:66`) | PARTIAL | UI promises something not delivered | Consumer-protection / support risk | P1 | Hide until implemented | Checkout shows no installment option |
| CC-14 | Cart weight display | Not shown | Shown | NOT APPLICABLE | Django-only | — | — | — | — |

### D.5 Payments & orders (PO)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| PO-01 | SEP online payment | ≈3,918 orders | `payment/gateways/sep.py`, `payment/services.py` | VERIFIED | Mocked only; real terminal untested | — | — | Sandbox test with real terminal | Payment tests + manual |
| PO-02 | Duplicate callback / replay | WooCommerce plugin | Reference-matched, idempotent | VERIFIED | — | — | — | — | `test_callback_replay_is_idempotent`, `test_duplicate_transaction_id_rejected` |
| PO-03 | Amount check, reversal, timeouts | Plugin | Verify amount; reverse on mismatch; timeout keeps pending | VERIFIED | — | — | — | — | `test_amount_mismatch_is_rejected_and_reversed`, `test_verify_timeout_keeps_payment_pending_for_retry` |
| PO-04 | Last-copy race | WooCommerce stock hold | Row locks (`payment/services.py:210`) | VERIFIED | — | — | — | — | `test_last_copy_sold_once` |
| PO-05 | Bank transfer (bacs) | ≈1,790 orders (31%) | No customer-facing option; only admin "mark paid offline" | MISSING | Offline payment unavailable | Loses customers who pay by transfer | P1 | Bank-transfer method → on-hold status + instructions | Place transfer order in staging |
| PO-06 | AsanPardakht | 121 orders | Not implemented | UNVERIFIED (evidence) | Unknown if still active | Low | P3 | Confirm with business | Check live gateway list |
| PO-07 | Order confirmation page | WooCommerce "order received" (standard) | Success → flash message + redirect to home (`payment/views.py:54-55`) | PARTIAL | No receipt page with order number/items | Support calls; no proof of purchase | P2 | Order confirmation view | Pay in sandbox → confirmation page |
| PO-08 | Order emails to customer | Terms page promises email receipts | `EMAIL_BACKEND` console (`config/settings.py:148`); no order emails anywhere | MISSING | No receipts or status emails | Trust, policy breach | P1 | Order emails (placed, paid, shipped) | Email captured in staging |
| PO-09 | New-order alert to shop | WooCommerce default (not verified) | None | UNVERIFIED (evidence) | — | Staff may miss orders | P1 (if confirmed) | Email/SMS to shop on payment | Confirm WooCommerce email settings |
| PO-10 | SMS notifications | Buyer SMS on status changes (`_buyer_sms_notify`, 3,266 SMS notes) | SMS on order creation (**before payment**) and on payment | PARTIAL | No status-change SMS; misleading pre-payment SMS | Customer confusion | P1 | SMS on paid/shipped/cancelled; drop pre-payment SMS | SMS log in staging |
| PO-11 | Postal tracking code | 3,703 tracking notes; promised in terms | No tracking field | MISSING | Cannot send tracking codes | Core post-sale service | P1 | Tracking field + SMS on ship | Admin enters code → SMS sent |
| PO-12 | Order status lifecycle | completed, processing, on-hold, cancelled, refunded | State machine with admin actions | VERIFIED | No on-hold equivalent | — | — | Add AWAITING_TRANSFER with PO-05 | `test_happy_path`, `test_cancelled_is_terminal` |
| PO-13 | Retry payment for unpaid order | WooCommerce "pay" link | `?order=` retry; owner check | VERIFIED | (see DM-03 for imported orders) | — | — | — | `test_cannot_pay_someone_elses_order` |
| PO-14 | Auto-cancel unpaid orders | WooCommerce hold-stock timer (not verified) | No expiry job | UNVERIFIED (evidence) | — | Stale pending orders | P3 | Scheduled cleanup | Check WooCommerce setting |
| PO-15 | Refund records | 72 refund documents | `REFUNDED` status only; no refund amount/reason model | PARTIAL | Partial refunds untracked | Accounting | P2 | Refund model | Admin can record partial refund |
| PO-16 | Store credit / gift card | 1,167 Smart Coupons | `wallet_balance` credited but never spendable | PARTIAL | Credit cannot be used | Customer complaints | P2 | Wallet at checkout or convert to coupons | Spend credit in staging |
| PO-17 | Invoice / delivery note printing | woocommerce-delivery-notes active | None | MISSING | No printable invoice/packing slip | Fulfilment workflow | P2 | Printable invoice view in admin | Print one order |
| PO-18 | Order notes / history trail | 25,706 notes | Importer merges notes into `order_notes` truncated to 700 chars (`import_wordpress_complete.py:334`); no note model | MISSING | No audit trail for status changes | Dispute handling | P2 | OrderNote model + import | Notes count per order |
| PO-19 | Stock decrement for offline-paid orders | WooCommerce reduces stock | Admin "mark paid offline" does not decrement stock | PARTIAL | Overselling | Inventory errors | P1 | Decrement in offline flow | Stock changes after admin action |
| PO-20 | Returns/refund policy | Refund at month-end minus postage/transfer fees | 3-day return window, approval credits wallet | PARTIAL | Policy mismatch | Legal/policy inconsistency | P2 | Align rules with published terms | Policy review |
| PO-21 | Coupon usage limit under concurrency | WooCommerce usage counter | `used_count` incremented after payment without re-checking `max_uses` (`payment/services.py:240`) | PARTIAL | Limited coupons can be over-used | Small revenue leak | P2 | Atomic check-and-increment | Concurrent payment test |

### D.6 Accounts (AC)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| AC-01 | Registration | email + password | allauth `email*`, `password1*` | UNVERIFIED (implemented) | — | — | — | Add test | Sign up in staging |
| AC-02 | Login | username **or** email | `ACCOUNT_LOGIN_METHODS={'email'}` (`config/settings.py:178`) | PARTIAL | Username login removed | Some customers cannot log in | P2 | Allow username + email | Login with both |
| AC-03 | Password reset | lost-password page | allauth reset; production SMTP not verified | UNVERIFIED (implemented) | — | Every migrated user depends on it | P1 | Verify SMTP in staging | Reset email received |
| AC-04 | Dashboard / profile edit | My-account pages | Dashboard, profile form | VERIFIED | — | — | — | — | `accounts` tests |
| AC-05 | Order history | My-account orders | `order_history.html` | UNVERIFIED (implemented) | Imported orders show "No items" (DM-02) | — | — | — | Manual with imported data |
| AC-06 | Saved addresses used at checkout | WooCommerce billing/shipping address | `address`, `postal_code` on user, not used by checkout | PARTIAL | Address book unused | UX | P2 | Use profile address at checkout | Prefilled checkout |
| AC-07 | Migrated customer login | Customers have WP password hashes (not in export) | Importer sets unusable passwords (`import_wordpress_complete.py:151`) | PARTIAL | All migrated customers must reset password | Login friction at launch | P1 | Password-hash migration or reset campaign | Migrated user logs in |
| AC-08 | Downloads tab | No downloadable products | — | NOT APPLICABLE | — | — | — | — | — |

### D.7 Content (CT)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| CT-01 | Home "new releases" shelf | Curated by tag | Latest by creation date | PARTIAL | Not curated; import date ≠ release date | Wrong books featured | P2 | Tag/flag-driven shelf | Same titles as live |
| CT-02 | Home special-offer grid | Tag-driven bundle grid | `sale_books`/`featured_packages` computed but not rendered | PARTIAL | Promotions not shown | Sales of bundles | P2 | Render sections | Visual |
| CT-03 | Home slider | meteor-slides assets + 1 slide; widget hidden by CSS | None | UNVERIFIED (evidence) | Likely unused | Low | P3 | Confirm | Visual on live |
| CT-04 | About page | Elementor/page 1996 | `AboutUs` singleton | UNVERIFIED (implemented) | — | — | — | Add test | Visual |
| CT-05 | Contact details | Address, postal code, phone, WhatsApp, email | Importer sets empty postal code and a hard-coded WhatsApp number that differs from live (`import_wordpress.py:519-521`) | PARTIAL | Wrong/missing contact data | Customers contact wrong number | P2 | Correct data in admin | Compare with live page |
| CT-06 | Contact form | None (no form plugin) | None | NOT APPLICABLE | — | — | — | — | — |
| CT-07 | Cooperation page | Single text | Importer copies same content into both `intro_text` and `invitation_text` (`import_wordpress.py:504-505`); template renders both | PARTIAL | Duplicated text | Cosmetic | P3 | Clear one field | Visual |
| CT-08 | Order terms page | Page | `OrderCondition` singleton | UNVERIFIED (implemented) | — | — | — | — | Visual |
| CT-09 | Payment guide, app, bot pages | Linked in user-guide menu | Archived as `/p/wp-page-<id>/`, not linked | PARTIAL | Unreachable | Low | P3 | Link or retire with redirect | Visual |
| CT-10 | Blog posts | 3 posts | Imported as `SitePage` (`/p/wp-post-<id>/`) | PARTIAL | No date URLs, categories, or list styling | Low | P3 | Keep archive + redirects | Redirect check |
| CT-11 | RSS feed | `/feed/` | None | MISSING | Feed readers break | Low | P3 | `django.contrib.syndication` | Feed validates |
| CT-12 | Custom 404 page | Branded 404 with search | No `templates/404.html` | MISSING | Default Django 404 in production | Poor UX for broken links (many expected post-migration) | P2 | Branded 404 | Request unknown URL with DEBUG off |
| CT-13 | Enamad trust seal | Footer seal | None | MISSING | Trust badge missing | Shaparak/IPG and customer-trust requirement | P1 | Re-register domain/seal and embed | Seal verifies on new site |
| CT-14 | Footer social links | Instagram, WhatsApp | Instagram, Telegram, WhatsApp | UNVERIFIED (implemented) | — | — | — | — | Click-through |
| CT-15 | Persian RTL, Persian digits, Jalali dates | Yes | `LANGUAGE_CODE='fa'`, `translate_number`, jalali_date | UNVERIFIED (implemented) | 2 tests assert English strings | — | — | Fix tests | Visual |
| CT-16 | Flipbook | dFlip (1 item) | None | UNVERIFIED (evidence) | Usage unknown | Low | P3 | Confirm | Locate on live |

### D.8 Admin (AD)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| AD-01 | Product management | WooCommerce product editor | `ProductAdmin` with filters, search, inline comments | UNVERIFIED (implemented) | Missing fields listed in PD/CAT | — | — | — | Admin smoke test |
| AD-02 | Coupon management | 2,025 coupons managed in WooCommerce | `DiscountCode` **not registered** in admin | MISSING | Staff cannot create/disable coupons | Marketing blocked | P1 | Register admin | Create coupon in admin |
| AD-03 | Order management | WooCommerce orders | `OrderAdmin` with state actions | VERIFIED | Lacks shipping/tracking (see PO) | — | — | — | Order state tests |
| AD-04 | Review moderation | WP comments | `CommentAdmin`, inline on product | UNVERIFIED (implemented) | — | — | — | — | Admin smoke test |
| AD-05 | Inventory management | `manage_stock`, stock notes (7,576) | `stock` field; `reserved_stock` unused; no movement log | PARTIAL | No stock history | Hard to trace stock errors | P2 | Stock movement log | Ledger matches stock |
| AD-06 | Bulk import/export & bulk edit | WP All Import used | Only `list_editable` active | MISSING | No bulk price/stock update | Staff effort | P2 | CSV import/export | Round-trip CSV |
| AD-07 | Shop-manager role | "Sale manager" WP user role | Staff flag + raw permissions, no groups | PARTIAL | No least-privilege role | Security/ops | P2 | Create groups | Staff user sees only shop models |
| AD-08 | Editorial pages | WP pages/Elementor | Singleton admins + `SitePage` | UNVERIFIED (implemented) | — | — | — | — | Admin smoke test |
| AD-09 | Site statistics | wp-statistics | None | MISSING | No visit analytics | Low | P3 | Privacy-friendly analytics | Dashboard shows data |
| AD-10 | Payment records | Order meta | `PaymentAdmin` read-only | UNVERIFIED (implemented) | — | — | — | — | Admin smoke test |
| AD-11 | Tiered discount management | — | `TieredDiscount` not in admin and never applied | PARTIAL | Dead feature | Confusion | P3 | Finish or remove | — |

### D.9 SEO & URLs (SEO)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| SEO-01 | Product URLs | `/product/<persian-slug>/` (+14 old slugs) | `/products/<pk>/`; no slug stored (`products/models.py:186`) | MISSING | Every product URL changes; `/product/...` 404 | Loss of search rankings and inbound links | P1 | Store WP slug; 301 old → new | All 623 old URLs → 301 → 200 |
| SEO-02 | Category URLs & pagination | `/product-category/...`, `/page/N/` | `/products/categories/<CODE>/`, `?page=N` | MISSING | 404 | Category rankings | P1 | 301 map per term | 14 terms + paging |
| SEO-03 | Page URLs | `/درباره-ما/`, `/ارتباط-با-ما/`, `/قوانین-و-مقررات/`, … | `/aboutus/`, `/contactus/`, `/orderus/`, `/workingus/`; archive slugs `wp-page-<id>` | MISSING | 404 | Lost links | P1 | 301 map | Each page URL |
| SEO-04 | Tag URLs | `/product-tag/<slug>/` | None | MISSING | 404 | Low | P2 | 301 to collection/search | 4 tags |
| SEO-05 | Post URLs | `/YYYY/MM/DD/<slug>/`, `/?p=ID` | `/p/wp-post-<id>/` | MISSING | 404 | Low | P2 | 301 map | 3 posts |
| SEO-06 | WooCommerce endpoints | `/shop/`, `/cart/`, `/checkout/`, `/my-account/` | `/cart/` matches; others 404 | PARTIAL | 3 of 4 endpoints break | Bookmarks, app links | P2 | 301 to Django equivalents | `resolve()` / HTTP |
| SEO-07 | Media URLs | 981 attachments under `/wp-content/uploads/` | Only covers imported; nginx has no `/wp-content/` location | MISSING | PDFs, images, embedded links 404 | Broken sample chapters, image search | P1 | Copy uploads and serve or redirect | Crawl all attachment URLs |
| SEO-08 | robots.txt | Present | 404 | MISSING | No crawl directives | Admin/API crawled | P2 | Add robots.txt | GET returns 200 |
| SEO-09 | XML sitemap | 404 on live | None | NOT APPLICABLE | Parity; recommended improvement | — | P3 | Add `django.contrib.sitemaps` | Submit to Search Console |
| SEO-10 | Canonical URL | Clean on products/pages | `{{ request.build_absolute_uri }}` incl. query strings (`templates/_base.html:13`) | PARTIAL | Sort/page/filter variants become canonical | Duplicate content | P2 | Strip query params / per-view canonical | View source |
| SEO-11 | Open Graph | `og:type product.item`, price | `og:type book`, no description/price | PARTIAL | Thinner share previews | Low | P3 | Add OG description/price | Sharing debugger |
| SEO-12 | Structured data | Product/Offer + BreadcrumbList | `Book` + Offer; no BreadcrumbList | PARTIAL | Breadcrumb rich result lost | Low | P3 | Add BreadcrumbList | Rich Results Test |
| SEO-13 | Unicode slugs (packages) | Persian slugs common | `packages/<slug:slug>/` is ASCII-only (`products/urls.py:14`) but model allows Unicode (`products/models.py:359`) | MISSING | Admin-created Persian bundle slugs 404 | Broken bundle pages | P2 | Use `<str:>` or a Unicode path converter | Create bundle with Persian slug |
| SEO-14 | Titles & meta descriptions | Site-wide generic description | Per-page titles and product descriptions | UNVERIFIED (implemented) | — | — | — | — | View source |

### D.10 Data & migration (DM)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| DM-01 | Order total currency | `IRR` (all years), `IRHT` (90 orders, 2026) | `_order_total` copied unconverted into Toman field (`import_wordpress_complete.py:311`) | MISSING | Totals 10× too high (IRR) or 1000× too low (IRHT) | Wrong history, wrong re-payment amount | P0 | Convert by `_order_currency` | Sample totals match WooCommerce |
| DM-02 | Order line items | Not in WXR | Orders imported with zero items | MISSING | Purchase history empty | Accounting, best sellers, returns | P0 | Import from DB dump, or label as archive | Items per order > 0 |
| DM-03 | Imported order status | completed / cancelled / on-hold / refunded | `status` not set → default `PENDING_PAYMENT` (`orders/models.py:54`); migration 0008 back-filled `PAID` only for paid orders; order history shows **Pay** for `PENDING_PAYMENT` (`order_history.html:62-63`); refunded orders imported as paid (`import_wordpress_complete.py:324`) | MISSING | 276 old unpaid orders can be paid again; refunded shown as paid | Customer charged for old orders (at wrong amount, see DM-01) | P0 | Explicit status mapping; block payment of imported orders | No imported order offers Pay |
| DM-04 | Coupon import fidelity | Restrictions + Smart Coupon semantics | Importer maps only amount/percent/limit/expiry (`import_wordpress_complete.py:242-270`); amounts not unit-converted | MISSING | Restricted coupons become unrestricted | Revenue loss | P0 | Do not import until CC-05, or import as inactive | Each coupon rule enforced |
| DM-05 | Product price units | Mixed thousand-Toman values | Heuristic: ×1000 if < 20,000 (`import_wordpress_wxr.py:38-49`) | UNVERIFIED (evidence) | 3 products ≥ 20,000 rely on the heuristic | Mis-priced books | P1 | Reconcile all 289 published prices | Diff live vs Django prices |
| DM-06 | Customer phone numbers | Billing phone on nearly all orders | `_ensure_user` ignores `phone` argument (`import_wordpress_complete.py:131-153`) | MISSING | No phone on migrated users | Cannot send SMS / birthday campaigns | P1 | Store normalized phone | Users with phone count |
| DM-07 | Registered customer accounts | Customers not in WXR (only 4 authors) | Users created only from order billing data | UNVERIFIED (evidence) | Customers without orders not migrated | Lost accounts | P1 | Export `wp_users`/`wp_usermeta` | Count vs WP users |
| DM-08 | Guest orders → accounts | 3,408 guest orders | Importer creates a user per guest email | PARTIAL | Accounts created without consent; "email already registered" on signup | Privacy and UX | P2 | Mark as guest-origin; decide policy | Signup with migrated email |
| DM-09 | Category mapping | 13 child terms; 110 uncategorized; 78 multi-category | Keyword heuristic (`CATEGORY_MAP` in `import_wordpress.py`) | PARTIAL | Misclassification possible | Wrong category pages | P1 | Map by term slug | Per-category counts match |
| DM-10 | Elementor page content | Home/app/bot built with Elementor | Importer reads `post_content` only | UNVERIFIED (evidence) | Pages may import empty/partial | Content loss | P2 | Check `_elementor_data` | Compare rendered text |
| DM-11 | Pending model migration | — | `products` 0013 (category choices) pending | PARTIAL | Model/DB drift | Deploy surprises | P2 | Generate and review migration | `makemigrations --check` clean |
| DM-12 | Current Django DB state | — | `books-db-1` container stopped; counts not read | UNVERIFIED (evidence) | Unknown what is already imported | Planning risk | P1 | Start DB and reconcile counts | Counts table vs export |

### D.11 Integrations (IN)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| IN-01 | SMS provider | Persian WooCommerce SMS | Kavenegar, synchronous (`services/sms.py`) | UNVERIFIED (implemented) | Synchronous send blocks requests | Slow checkout if provider is slow | — | Test in staging; consider queue | SMS received |
| IN-02 | Mobile app (woo2app) | `/app/` APK built on WooCommerce APIs | No WooCommerce-compatible API | UNVERIFIED (evidence) | App likely breaks | Mobile customers lose access | P1 (decision) | Confirm app usage; retire or rebuild | Test app against staging |
| IN-03 | Telegram bots | `/bot/` lists two bots | None | UNVERIFIED (evidence) | Unknown integration | Possible breakage | P1 (decision) | Confirm with owner | Bot works post-cutover |
| IN-04 | Transactional email (SMTP) | WooCommerce emails | SMTP configured only in `settings_production.py` | UNVERIFIED (implemented) | Untested | Password resets, receipts | P1 | Staging SMTP test | Email received |
| IN-05 | WordPress REST consumers | `/wp-json/wp/v2/product` public | Different API under `/api/v1/` | UNVERIFIED (evidence) | Unknown external consumers | Possible breakage | P2 | Check server logs | Log review |

### D.12 Security & operations (SE)

| ID | Feature | Live | Django | Status | Gap | Business impact | Priority | Recommended action | Verification |
|---|---|---|---|---|---|---|---|---|---|
| SE-01 | Production hardening | — | `DEBUG=False`, HSTS, secure cookies, SSL redirect in `settings_production.py` | UNVERIFIED (implemented) | — | — | — | `check --deploy` in staging | `manage.py check --deploy` |
| SE-02 | TLS & domain | HTTPS (certificate currently expired) | nginx listens on 80 only; `server_name yourdomain.com` (`nginx/nginx.conf:5-9`); empty `certbot/` | MISSING | No HTTPS; redirect loop with SSL redirect | Site unreachable / insecure | P0 | TLS server block + real domain + renewal | SSL Labs test |
| SE-03 | Backups | (host-managed, unknown) | No backup job in `docker-compose.prod.yml` | MISSING | No DB/media backups | Permanent data loss risk | P1 | Scheduled pg_dump + media backup + restore drill | Restore test |
| SE-04 | Frontend asset dependencies | Self-hosted theme | Tailwind **runtime** CDN, cdnjs, jsdelivr, unpkg, Google Fonts (`templates/_base.html:36-39, 299-301`); no SRI | PARTIAL | Site styling depends on foreign CDNs | Pages unstyled if CDNs are blocked/throttled in Iran; supply-chain risk | P1 | Build and self-host CSS/JS/fonts | Load site with external CDNs blocked |
| SE-05 | Rich-text editor | WP editor | CKEditor 4 (unsupported, `ckeditor.W001`) | PARTIAL | Known unpatched issues | Admin-side XSS risk | P2 | Upgrade to CKEditor 5 / alternative | `check` warning gone |
| SE-06 | HTML output escaping | WP filters | `{{ product.description\|safe }}` (`product_detail.html:96`), CMS pages `\|safe` | PARTIAL | Imported/admin HTML rendered unsanitized | Stored XSS if content is compromised | P2 | Sanitize (e.g. bleach) on save | Script tag stripped |
| SE-07 | State-changing GET | — | `remove_discount_code_view` lacks `@require_POST` (`cart/views.py:288`) | PARTIAL | CSRF-able (low impact) | Minor | P3 | Require POST | GET returns 405 |
| SE-08 | Error monitoring & logs | — | Console logging only; no `ADMINS`/Sentry | MISSING | Production errors invisible | Silent failures in payment flow | P2 | Error tracking + log retention | Trigger test error |
| SE-09 | Repository hygiene | — | `media/` (incl. PDF) and `__pycache__/*.pyc` tracked in git | PARTIAL | Repo bloat; `.pyc` churn | Low | P3 | Untrack via `.gitignore` | `git ls-files` |
| SE-10 | Test suite health | — | 166/168 pass; 2 locale failures; `pages` 0 tests; importers untested | PARTIAL | Gaps around highest-risk code (importers) | Regressions in migration | P2 | Tests for importers and pages | CI green |
| SE-11 | Rate limiting | — | allauth default rate limits; DRF throttling | UNVERIFIED (implemented) | — | — | — | Verify in staging | Repeated login attempts throttled |
| SE-12 | Public API docs | — | Swagger/ReDoc publicly accessible | PARTIAL | Exposes API surface | Low | P3 | Restrict to staff | Anonymous GET → 403 |

---

## E. Missing and Incomplete Features (confirmed gaps only)

Only items with status MISSING or PARTIAL are listed. Items still UNVERIFIED are in the separate list at the end of this section.

### Catalog
- **Missing:** private/hidden products are published (CAT-07); multiple categories (CAT-04); product tags (CAT-05); cross-sells/upsells (CAT-10); editor attribute (PD-02); paper type/period (PD-04); gallery (PD-07); product weights (PD-14).
- **Partial:**
  - Flat category enum instead of the WordPress hierarchy (CAT-03).
  - No popularity sort (CAT-02); single-select filter (CAT-06).
  - Discount dates are ignored (CAT-12).
  - Print year and publication date are merged into one value (PD-03).
  - Contributors are stored as comma strings, and the translator sits in the `edition` field (PD-05).
  - Description PDF links depend on the old WordPress uploads (PD-08).
  - Guest reviews are not allowed (PD-12).

### Search / navigation
- **Missing:** redirect for the legacy `/?s=` search URL (SR-06); redirect when there is a single result (SR-04).
- **Partial:** search covers products only (SR-07); the "user guide" menu pages are not linked (SR-09).

### Cart / checkout
- **Missing:** coupon restriction rules (CC-05); guest checkout (CC-06); shipping methods and costs (CC-08).
- **Partial:** structured address/email fields (CC-07); prefill (CC-09); phone validation (CC-10); persistent cart (CC-12); installment option is UI-only (CC-13).

### Payments / orders
- **Missing:** bank transfer (PO-05); customer emails (PO-08); tracking codes (PO-11); invoices/delivery notes (PO-17); order notes trail (PO-18).
- **Partial:**
  - No confirmation page (PO-07).
  - SMS coverage incomplete, and one SMS is sent before payment (PO-10).
  - Refunds (PO-15); store credit that cannot be spent (PO-16).
  - Offline-paid orders don't decrement stock (PO-19).
  - Returns policy doesn't match the published terms (PO-20).
  - Coupon usage limit has a race (PO-21).

### Accounts
- **Partial:** login is email-only (AC-02); the saved address is not used at checkout (AC-06); migrated users cannot log in without a reset (AC-07).

### Content
- **Missing:** RSS (CT-11); branded 404 (CT-12); Enamad seal (CT-13).
- **Partial:** home new-releases shelf (CT-01); special-offer grid (CT-02); contact data (CT-05); duplicated cooperation text (CT-07); guide pages (CT-09); blog posts (CT-10).

### Admin
- **Missing:** coupon admin (AD-02); bulk import/export (AD-06); statistics (AD-09).
- **Partial:** stock history (AD-05); roles (AD-07); tiered discounts (AD-11).

### SEO / URL
- **Missing:**
  - Product, category, page, tag and post URLs (SEO-01–05).
  - `/wp-content/uploads/` media (SEO-07).
  - robots.txt (SEO-08).
  - Unicode bundle slugs (SEO-13).
- **Partial:** WooCommerce endpoints (SEO-06); canonical (SEO-10); OG (SEO-11); structured data (SEO-12).

### Data / migration
- **Missing:** order currency conversion (DM-01); order line items (DM-02); order status mapping (DM-03); coupon fidelity (DM-04); customer phones (DM-06).
- **Partial:** guest-to-account conversion (DM-08); category mapping (DM-09); pending migration (DM-11).

### Integrations
- No confirmed gaps; all integration items remain unverified (see below).

### Security
- **Missing:** TLS/domain (SE-02); backups (SE-03); error monitoring (SE-08).
- **Partial:** CDN dependencies (SE-04); CKEditor 4 (SE-05); unsanitized HTML (SE-06); GET state change (SE-07); repo hygiene (SE-09); tests (SE-10); public API docs (SE-12).

### Items requiring verification (not classified as gaps)

| ID | Item | Why unverified |
|---|---|---|
| CC-11 | Terms checkbox at checkout | Live checkout form not opened |
| PO-06 | AsanPardakht still active? | Only historical orders seen |
| PO-09 | Shop notification on new order | WooCommerce email settings not visible |
| PO-14 | Auto-cancel of unpaid orders | WooCommerce hold-stock setting not visible |
| CT-03 | Home slider | Assets loaded but widget hidden by CSS |
| CT-16 | Flipbook | One dFlip item, location unknown |
| DM-05 | Product price units | Heuristic conversion; Django DB not readable |
| DM-07 | Customers without orders | WP users table not in export |
| DM-10 | Elementor page content | Not compared against Django DB |
| DM-12 | Current Django DB contents | Container stopped |
| IN-02 | Mobile app | App behaviour not tested |
| IN-03 | Telegram bots | Bot backends unknown |
| IN-05 | WordPress REST consumers | No server logs available |

---

## F. Purchase Workflow

| Step | Live (WooCommerce) | Django | Status | Notes |
|---|---|---|---|---|
| 1. Homepage | Tag-curated new releases + discount bundles | Best sellers, new releases (by date), subjects, contributor index | PARTIAL | Promotions not rendered (CT-01, CT-02) |
| 2. Browse | Hierarchical categories, tags, WOOF filters, 12/page, 5 sorts | Flat categories, discount filter, 12/page, 7 sorts | PARTIAL | CAT-03–06 |
| 3. Search | Title/description only | All fields, Persian normalization | VERIFIED (better) | SR-01–03 |
| 4. Product page | Attributes incl. editor; guest reviews; related | Attributes without editor; login reviews; related; bundles | PARTIAL | PD-02, PD-12 |
| 5. Add to cart | Form POST | POST + JSON, stock-capped | VERIFIED | CC-01, CC-03 |
| 6. Cart | Coupons with rules, shipping estimate (assumed) | Coupons without rules; no shipping | PARTIAL | CC-05, CC-08 |
| 7. Checkout | Guest or logged in; full address; shipping method; SEP / bank transfer | Login required; name/phone/free address; SEP only (installment UI charges full) | PARTIAL | CC-06–08, PO-05, CC-13 |
| 8. Payment | SEP / AsanPardakht / bank transfer | SEP with verification, reversal, idempotency | VERIFIED (SEP only) | PO-01–04 |
| 9. Confirmation | Order-received page + email | Flash message on home page; SMS | PARTIAL | PO-07, PO-08 |
| 10. Order management | Status emails/SMS, tracking code, invoices, notes | State machine, return requests, no tracking/invoice/notes | PARTIAL | PO-10, PO-11, PO-17, PO-18 |

### Edge cases

| Scenario | Django behaviour | Evidence | Assessment |
|---|---|---|---|
| Duplicate order submission | Each POST creates a new `PENDING_PAYMENT` order (cart is cleared after the first, so a second submit hits an empty cart) | `orders/views.py:114` | Acceptable; unpaid duplicates accumulate (PO-14) |
| Duplicate/replayed payment callback | Idempotent, matched by reference; duplicate transaction id rejected | `payment/services.py`, tests | VERIFIED |
| Callback after session loss | Matched by payment reference, not session | `payment/views.py` | VERIFIED |
| Invalid / expired / exhausted coupon | Rejected at apply and re-validated at checkout | `cart/cart.py`, tests | VERIFIED (basic rules only) |
| Coupon raced past `max_uses` | Counted after payment without a re-check | `payment/services.py:240` | PARTIAL (PO-21) |
| Stale price in cart | Prices re-read from DB on each iteration; order item snapshots price | `cart/cart.py`, tests | VERIFIED |
| Stale discount window | Discount dates ignored → sale price persists | `products/models.py:190-210` | PARTIAL (CAT-12) |
| Inventory conflict (last copy) | Row locks; second payer is not verified and gets reversed/refunded path | `test_last_copy_sold_once` | VERIFIED |
| Stock reservation during checkout | None (`reserve_stock` unused); stock taken only at payment | `products/models.py:270` | By design; customer may lose the item at payment |
| Gateway rejection / cancel / timeout | Payment marked failed/cancelled or kept pending; customer returned to cart | payment tests | VERIFIED |
| Amount tampering | Server computes amount; verify compares with gateway | `test_amount_mismatch_is_rejected_and_reversed` | VERIFIED |
| Paying someone else's order | Rejected | `test_cannot_pay_someone_elses_order` | VERIFIED |
| Re-paying a migrated historical order | **Allowed** for imported cancelled/on-hold orders, at unconverted amount | DM-01, DM-03 | **P0 defect** |
| SMS before payment | "Order registered" SMS sent even if never paid | `orders/views.py:124` | PARTIAL (PO-10) |
| Failed checkout leaves cart empty | Cart is cleared at order creation; retry is via order history "Pay" | `orders/views.py:114`, `order_history.html:63` | Acceptable, but the confirmation UX is weak |

---

## G. URL/SEO Migration Map

Django does not currently resolve any of the legacy patterns below, except `/cart/`, which this audit confirmed with `django.urls.resolve()`. All redirects should be **301** and generated from data (WordPress IDs are already stored in `Product.wordpress_id`, `Order.wordpress_id`, `CustomUser.wordpress_id`; pages/posts via `SitePage`).

| Legacy URL pattern | Volume | Current Django result | Proposed target | Mapping source |
|---|---|---|---|---|
| `/product/<slug>/` | 623 products (+14 `_wp_old_slug`) | 404 | `/products/<pk>/` (or a new slug URL) | Store `post_name` + old slugs per product |
| `/?post_type=product&p=<id>`, `/?p=<id>` | any | home page | product/post canonical URL | `wordpress_id` |
| `/shop/`, `/shop/page/<n>/` | 1 | 404 | `/products/?page=<n>` | static |
| `/product-category/<root>/` | 1 | 404 | `/products/` | static |
| `/product-category/<root>/<child>/` and `/product-category/<child>/` (+ `/page/<n>/`) | 13 | 404 | `/products/categories/<CODE>/` | term slug → category code table |
| `/product-tag/<tag>/` | 4 | 404 | tag/collection page or `/products/?discount=true` / `/products/new-releases/` | static table |
| `/?s=<q>&post_type=product` | n/a | home page | `/products/search/?q=<q>` | query rewrite |
| `/cart/` | 1 | 200 (match) | `/cart/` | — |
| `/checkout/` | 1 | 404 | `/order/create/` | static |
| `/my-account/` (+ `orders/`, `edit-account/`, `lost-password/`) | 1 | 404 | `/accounts/dashboard/`, order history, profile edit, allauth reset | static |
| `/درباره-ما/` | 1 | 404 | `/aboutus/` | static |
| `/ارتباط-با-ما/` | 1 | 404 | `/contactus/` | static |
| `/همکاری-با-ما/` | 1 | 404 | `/workingus/` | static |
| `/قوانین-و-مقررات/` | 1 | 404 | `/orderus/` | static |
| `/راهنمای-پرداخت-انلاین/`, `/app/`, `/bot/` | 3 | 404 | `/p/wp-page-<id>/` or retire to home | `SitePage` |
| `/demo2/`, `/دمو۲/`, `/خانه/` (page_id 1063/1138) | 3 | 404 | `/` | static |
| `/YYYY/MM/DD/<slug>/` | 3 posts | 404 | `/p/wp-post-<id>/` | `SitePage` |
| `/category/<slug>/`, `/author/<slug>/` | few | 404 | `/` or post archive | static |
| `/feed/`, `/comments/feed/` | 2 | 404 | new feed or 410 | — |
| `/wp-content/uploads/<yyyy>/<mm>/<file>` | 981 attachments (172 PDFs) | 404 | serve copied files at the same path, or 301 to `/media/...` | file copy + nginx `location` |
| `/wp-json/...`, `/wp-admin/`, `/wp-login.php`, `/xmlrpc.php` | — | 404 | 410 Gone (after confirming no app consumers, IN-02/IN-05) | static |
| `/sitemap.xml`, `/robots.txt` | — | 404 | new Django sitemap and robots.txt | — |

**Not preserved today:** product slugs (not stored), Persian page slugs (archive slugs are `wp-page-<id>`, and `slugify(allow_unicode=True)` would strip ZWNJ anyway), pagination format, media paths. Two unrelated routing risks also apply: Unicode bundle slugs fail the `<slug:>` converter (SEO-13), and author names containing "/" would fail `reverse('product:author_books')` (no current data affected).

---

## H. Data Preservation Risks

| # | Risk | Evidence | Severity | Mitigation |
|---|---|---|---|---|
| H-1 | Order totals stored in the wrong unit | `_order_currency` is `IRR` (and `IRHT` for 90 orders); importer copies raw value (`import_wordpress_complete.py:311`) | P0 | Convert per order: IRR ÷ 10, IRHT × 1000 |
| H-2 | Order line items absent | No `order_item` data in WXR | P0 | Export `wp_woocommerce_order_items` + `…_itemmeta` (or HPOS tables) from the WP database |
| H-3 | Order status lost; cancelled orders payable | Status never written; default `PENDING_PAYMENT`; refunded treated as paid | P0 | Explicit mapping (completed→DELIVERED, cancelled→CANCELLED, on-hold→awaiting transfer/CANCELLED, refunded→REFUNDED); mark imported orders non-payable |
| H-4 | Coupon rules discarded; units unconverted | Only amount/percent/limit/expiry imported | P0 | Model the rules or import restricted coupons as inactive |
| H-5 | Shipping data discarded | Shipping method/cost and postcode/province not imported into fields | P1 | Add fields; import shipping lines from DB dump |
| H-6 | Product weights discarded | `_weight` not mapped by either importer | P0 (blocks shipping) | Import `_weight` |
| H-7 | Editor and other attributes discarded | Editor (133), paper type (16), period (8) ignored | P1 | Add fields / attribute table |
| H-8 | Private products made public | `'active': status in ('publish','private')` | P1 | Import private as inactive |
| H-9 | Slugs not stored | No `slug` field on `Product` | P1 | Store slug + old slugs for redirects |
| H-10 | Media beyond covers not migrated | 981 attachments; only covers downloaded | P1 | Copy the full `uploads` directory |
| H-11 | Customer phone not stored; customers without orders not migrated | `_ensure_user` ignores phone; WXR has no customers | P1 | Export WP users; store phones |
| H-12 | Passwords not migrated | `set_unusable_password()` | P1 | Port WordPress phpass/bcrypt hashes via a custom hasher, or run a reset campaign |
| H-13 | Guest buyers turned into accounts | One user per guest email | P2 | Flag as imported guests; communicate |
| H-14 | Order notes truncated and merged | Joined into `order_notes`[:700] | P2 | Separate note model |
| H-15 | Category assignment heuristic | Keyword `CATEGORY_MAP`; 110 uncategorized; multi-category flattened | P1 | Map by term slug |
| H-16 | Re-running importers | `update_or_create` re-applies defaults (e.g. overwrites admin edits, `_import_pages` recreates singletons) | P2 | Make importers idempotent without clobbering edits; dry-run mode |
| H-17 | No backups | No backup job | P1 | Automated backups before and after cutover |
| H-18 | Elementor-only content | Home/app/bot content may live in `_elementor_data` | P2 | Compare imported text with live |

---

## I. Prioritized Backlog

### P0 — blocks safe launch

**T-01 · Correct imported order statuses and block re-payment**
- Feature: DM-03, PO-13
- Evidence: `orders/models.py:54` default; `orders/migrations/0008_…py:9` back-fills only paid orders; `order_history.html:62-63`; export has 212 cancelled + 64 on-hold orders
- Expected outcome: every imported order has a status matching WooCommerce, and no imported order can be paid
- Dependencies: none
- Acceptance criteria: imported cancelled/on-hold/refunded orders show the correct status; no **Pay** button and `/payment/process/?order=<id>` refuses them
- Django files: `products/management/commands/import_wordpress_complete.py`, `orders/models.py` (flag such as `imported`), `payment/views.py`, `accounts/templates/accounts/order_history.html`
- Verification: importer test with a fixture order of each status; manual attempt to pay an imported order

**T-02 · Convert imported order totals by currency**
- Feature: DM-01
- Evidence: `_order_currency` IRR (all years) / IRHT (90 orders); `import_wordpress_complete.py:311`
- Expected outcome: `total_price` in Toman for every imported order
- Dependencies: T-01
- Acceptance criteria: sample of orders per year/currency matches WooCommerce admin totals
- Django files: `import_wordpress_complete.py`
- Verification: unit test for IRR and IRHT; spot-check 20 orders against the WP admin

**T-03 · Obtain order line items or declare historical orders archival**
- Feature: DM-02
- Evidence: no line items in WXR
- Expected outcome: either items imported as `OrderItem` snapshots, or historical orders shown read-only with "archived order" labelling
- Dependencies: WordPress DB dump; T-01, T-02
- Acceptance criteria: decision recorded; items per order > 0 if imported
- Django files: importer, `orders/models.py` (optional archive flag), order history template
- Verification: totals of item lines + shipping − discount = order total

**T-04 · Coupon rules and coupon migration policy**
- Feature: CC-05, DM-04, AD-02
- Evidence: 2,025 coupons with restrictions; `DiscountCode` (`products/models.py:489`); importer `:242-270`; no admin registration
- Expected outcome: rules that matter (min spend, per-user limit, category, exclude sale items, individual use, max discount, expiry) are enforced, or restricted coupons are not active after migration
- Dependencies: tags/categories (T-22) for category restriction
- Acceptance criteria: each rule has a test; no migrated coupon grants more than in WooCommerce
- Django files: `products/models.py`, `cart/cart.py`, `orders/views.py`, `payment/services.py`, `products/admin.py`, importer
- Verification: rule-by-rule unit tests; sample of 50 migrated coupons compared with WooCommerce

**T-05 · Shipping methods, costs and product weights**
- Feature: CC-08, PD-14, H-5, H-6
- Evidence: 6 shipping methods; 1,978 orders with shipping; `_weight` on 539 products not imported
- Expected outcome: customer selects a shipping method; cost added to order and payment amount; weights imported
- Dependencies: T-12 (address fields for region rules); business confirmation of current rates
- Acceptance criteria: order total = items − discount + shipping; SEP amount equals that × 10; free-shipping threshold works
- Django files: new shipping model/config, `orders/models.py`, `orders/forms.py`, `orders/views.py`, `payment/services.py`, `import_wordpress_wxr.py`
- Verification: unit tests per method; sandbox payment

**T-06 · Production TLS, domain and nginx**
- Feature: SE-02
- Evidence: `nginx/nginx.conf:5-9`; `SECURE_SSL_REDIRECT=True`; empty `certbot/`
- Expected outcome: HTTPS on the real domain with auto-renewal, HTTP → HTTPS redirect
- Dependencies: DNS
- Acceptance criteria: SSL Labs grade A; no redirect loop; `check --deploy` clean
- Django files: `nginx/nginx.conf`, `docker-compose.prod.yml`, `config/settings_production.py` (proxy header)
- Verification: staging deployment test

### P1 — required for launch

| Task | Feature | Evidence | Expected outcome | Dependencies | Acceptance criteria | Django files | Verification |
|---|---|---|---|---|---|---|---|
| T-07 | Legacy URL preservation (SEO-01–06, SR-06) | Section G; `resolve()` 404s | Every legacy URL 301s to its Django page | Slugs stored (H-9), T-22 | 100% of old product/category/page URLs return 301 → 200 | `products/models.py` (slug), new redirect view/middleware, `config/urls.py` | Crawl legacy URL list from export |
| T-08 | `/wp-content/uploads/` media (SEO-07, PD-08) | 981 attachments; nginx has no location | Old media URLs keep working | Copy of uploads | All attachment URLs 200 | `nginx/nginx.conf`, media storage | Link crawl of descriptions |
| T-09 | Hide private products (CAT-07) | `import_wordpress_wxr.py:212` | 289 active products | — | Active count matches published | importer | Count query |
| T-10 | Editor & contributor fields (PD-02, PD-05) | 101 published products with editor | Editor shown; translator field correctly named | Migration | Editor visible on those products | `products/models.py`, importer, `product_detail.html`, admin | Spot-check |
| T-11 | Guest checkout (CC-06) | 58% guest orders | Purchase without registration | T-12 | Logged-out sandbox order completes | `orders/models.py`, `orders/views.py`, `payment/views.py` | Test + manual |
| T-12 | Structured address & email (CC-07, CC-10) | Billing meta fields | Province, city, postcode, email, validated mobile | — | Order stores structured fields | `orders/models.py`, `orders/forms.py` | Form tests |
| T-13 | Bank transfer + offline stock (PO-05, PO-19) | ≈1,790 bacs orders | Transfer option with instructions; stock decremented when confirmed | T-01 | Transfer order → awaiting → paid with stock change | `orders`, `payment`, admin actions | Tests |
| T-14 | Notifications (PO-08, PO-09, PO-10, PO-11) | Terms page promises email + tracking SMS | Emails/SMS for paid, shipped (with tracking), cancelled; shop alert | T-12, IN-04 | Each transition triggers the right message once | `orders/models.py` (tracking), `orders/admin.py`, `services/sms.py`, email templates | Staging message log |
| T-15 | Coupon admin (AD-02) | Not registered | Staff manage coupons | T-04 | CRUD in admin | `products/admin.py` | Admin test |
| T-16 | Enamad seal (CT-13) | Live footer seal | Seal valid for new site | Domain | Seal verifies | `templates/_base.html` | Click seal |
| T-17 | Self-host frontend assets (SE-04) | `_base.html:36-39, 299-301` | No runtime CDN dependency | Build step | Site renders with CDNs blocked | `templates/_base.html`, `static/`, Dockerfile | Offline render |
| T-18 | Backups (SE-03) | None configured | Nightly DB + media backup, tested restore | — | Restore drill succeeds | `docker-compose.prod.yml`, ops docs | Restore test |
| T-19 | Customer migration (DM-06, DM-07, AC-03, AC-07, IN-04) | `_ensure_user` ignores phone; unusable passwords | Customers can log in; phones stored | WP users export; SMTP | Migrated user resets password and logs in | importer, `accounts`, password hasher | Staging test |
| T-20 | Hide installment UI (CC-13) | `orders/views.py:42-68` | No unfulfilled promise | — | Checkout shows only real methods | `orders/views.py`, checkout template | Visual |
| T-21 | App & bot decision (IN-02, IN-03) | `/app/`, `/bot/` | Documented plan | Owner input | Plan agreed | — | Owner sign-off |
| T-22 | Category mapping (CAT-03, DM-09) | 14 terms; heuristic map | Categories match WordPress | Optional category model | Per-category counts match export | `products/models.py`, `products/taxonomy.py`, importer | Count comparison |
| T-23 | Price reconciliation (DM-05) | ×1000 heuristic | All prices verified | DB access | 0 differences vs live | importer | Diff script |
| T-24 | Restore Django DB & reconcile (DM-12) | Container stopped | Known import state | — | Count table vs export | — | Report |

### P2 — important, shortly after launch

| Task | Feature | Evidence | Expected outcome | Dependencies | Acceptance criteria | Django files | Verification |
|---|---|---|---|---|---|---|---|
| T-25 | Tags, multi-category, curated home shelves (CAT-04, CAT-05, CT-01, CT-02, SEO-04) | 4 tags, 78 multi-cat products | Collections drive home sections | T-22 | Home shows same titles as live | `products/models.py`, `pages/views.py`, `home.html` | Visual + count |
| T-26 | Discount date window (CAT-12) | `products/models.py:190-210` | Sales expire on schedule | — | Expired sale shows regular price | `products/models.py` | Unit test |
| T-27 | Guest reviews (PD-12) | Live allows guests | Moderated guest reviews | Anti-spam | Guest review reaches moderation queue | `products/models.py`, `products/views.py` | Test |
| T-28 | Order confirmation page (PO-07) | `payment/views.py:54-55` | Receipt page with number and items | — | Page shown after success | `payment/views.py`, `orders` | Test |
| T-29 | Invoices/delivery notes (PO-17) | Plugin active on live | Printable invoice | T-05, T-12 | Print from admin | `orders/admin.py`, template | Manual |
| T-30 | Order notes trail (PO-18) | 25,706 notes | Timestamped notes per order | T-01 | Imported + new notes visible in admin | `orders/models.py`, importer | Count |
| T-31 | Refunds, returns policy, wallet (PO-15, PO-16, PO-20) | Terms page vs `ReturnRequest` | Consistent policy; spendable or removed wallet | Business decision | Policy matches terms page | `orders`, `cart`, `payment` | Tests |
| T-32 | Coupon concurrency (PO-21) | `payment/services.py:240` | Usage limit never exceeded | T-04 | Concurrent test passes | `payment/services.py` | Test |
| T-33 | robots.txt, canonical, 404, Unicode slugs (SEO-08, SEO-10, CT-12, SEO-13) | 404s; `_base.html:13`; `products/urls.py:14` | Clean SEO basics | — | All four checks pass | `config/urls.py`, templates, `products/urls.py` | HTTP checks |
| T-34 | Contact & cooperation data (CT-05, CT-07) | `import_wordpress.py:504-521` | Correct contact data | — | Matches live | admin data | Visual |
| T-35 | Print year vs publication date (PD-03) | Separate attributes | Both stored | Migration | Values differ where live differs | model, importer | Spot-check |
| T-36 | Address book & prefill (AC-06, CC-09) | Unused profile address | Prefilled checkout | T-12 | Prefill works | `orders/views.py`, `orders/forms.py` | Test |
| T-37 | Username login (AC-02) | `config/settings.py:178` | Username or email login | T-19 | Both work | settings | Test |
| T-38 | Admin operations (AD-05, AD-06, AD-07) | No stock log, bulk tools, roles | Stock ledger, CSV import/export, shop-manager group | — | Staff can bulk-update prices | admin, new models | Manual |
| T-39 | Editor & HTML safety (SE-05, SE-06) | CKEditor 4, `\|safe` | Supported editor; sanitized HTML | — | `check` clean; script stripped | settings, models | Test |
| T-40 | Error monitoring (SE-08) | Console logging | Alerts on errors | — | Test error reported | settings | Manual |
| T-41 | Test & migration health (SE-10, DM-11) | 2 locale failures; pending 0013 | Green suite; no pending migrations | — | CI green | tests, migration | CI |
| T-42 | Elementor content & guest-account policy (DM-10, DM-08) | Elementor pages; guest users | Content verified; guest policy set | T-24 | Text matches live | importer | Comparison |
| T-43 | Legacy WP API consumers (IN-05) | `/wp-json` public | Consumers identified | Server logs | Decision recorded | — | Log review |

### P3 — optional

| Task | Feature | Evidence | Expected outcome | Dependencies | Acceptance criteria | Django files | Verification |
|---|---|---|---|---|---|---|---|
| T-44 | Search & browse polish (CAT-02, CAT-06, SR-04, SR-07, SR-09) | Live sorts/filters | Popularity sort, multi-filter, single-hit redirect | T-25 | Behaviour matches live | `products/views.py` | Manual |
| T-45 | Product extras (CAT-10, PD-04, PD-07) | 105 cross-sells, 3 galleries | Data preserved | — | Counts match | models, importer | Count |
| T-46 | Content extras (CT-03, CT-09, CT-10, CT-11, CT-16, SEO-09, SEO-11, SEO-12) | Feed, posts, guides | Feed, sitemap, richer OG/JSON-LD | T-07 | Validators pass | `pages`, templates | Validators |
| T-47 | Analytics (AD-09) | wp-statistics | Visit statistics | — | Data visible | templates | Manual |
| T-48 | Minor hardening (SE-07, SE-09, SE-12) | GET removal; tracked media; public Swagger | Hygiene fixes | — | Checks pass | `cart/views.py`, `.gitignore`, `api/urls.py` | Tests |
| T-49 | Leftovers (PO-06, PO-14, CC-12, AD-11) | AsanPardakht, unpaid orders, tiers | Decide/implement or remove | Owner input | Decision recorded | various | — |

---

## J. Manual Verification Items

| # | Item | Why it could not be verified automatically | Suggested method |
|---|---|---|---|
| J-1 | Live checkout form fields, shipping options and prices, terms checkbox | Adding to cart on the live site was deliberately not performed | Owner walks through checkout up to (not including) payment, with screenshots |
| J-2 | Current shipping rates and free-shipping threshold | Only per-order amounts in export | WooCommerce → Settings → Shipping |
| J-3 | Active payment gateways (AsanPardakht?) and bank-transfer instructions | WP admin not accessed | WooCommerce → Settings → Payments |
| J-4 | WooCommerce email and SMS settings (shop alerts, customer emails) | WP admin not accessed | WooCommerce → Settings → Emails; SMS plugin settings |
| J-5 | Hold-stock / unpaid order timeout | WP admin not accessed | WooCommerce → Settings → Products → Inventory |
| J-6 | Authenticated "My account" pages (orders, addresses, invoice links) | No test account used | Log in with a staff test account |
| J-7 | Order line items and customer table | Not in WXR | Database export of order items and users |
| J-8 | Django database contents (what has already been imported) | `books-db-1` container stopped | Start DB, run read-only counts |
| J-9 | Real SEP terminal behaviour (sandbox) | Tests use a mocked gateway | Staging transaction with SEP test terminal |
| J-10 | Kavenegar SMS and SMTP delivery | Disabled in tests | Staging send to a staff number/address |
| J-11 | Mobile app (woo2app) dependency on WooCommerce APIs | Not testable read-only | Install app, test against staging |
| J-12 | Telegram bots' data source | Unknown backends | Ask bot owner |
| J-13 | Price unit correctness for the 3 products ≥ 20,000 and all published products | DB not readable | Diff live price vs Django |
| J-14 | Elementor page text vs imported text | DB not readable | Visual comparison |
| J-15 | Enamad / Shaparak requirements for the new domain/server | External registration | Contact Enamad / bank |
| J-16 | Tests on PostgreSQL (row locking behaves differently from SQLite) | DB container stopped | Run suite against Postgres in CI |
| J-17 | Live TLS certificate renewal | Hosting not accessible | Renew immediately on current host |

---

## K. Final Launch Checklist

**Data**
- [ ] Imported order statuses mapped; no imported order payable (T-01)
- [ ] Order totals converted from IRR/IRHT (T-02)
- [ ] Line-item decision implemented (T-03)
- [ ] Coupons enforce live rules, or restricted coupons are inactive (T-04)
- [ ] Product weights, editors, categories, visibility and prices reconciled with WordPress (T-05, T-09, T-10, T-22, T-23)
- [ ] Customer accounts, phones and password plan in place (T-19)
- [ ] Full `/wp-content/uploads/` copied (T-08)
- [ ] Final record counts (products, categories, users, orders, coupons, comments, pages) match the export (T-24)

**Commerce**
- [ ] Shipping methods and costs charged correctly (T-05)
- [ ] Guest checkout works (T-11)
- [ ] Structured address, email and validated mobile captured (T-12)
- [ ] Bank transfer available, or explicitly retired with notice (T-13)
- [ ] Installment UI hidden (T-20)
- [ ] SEP sandbox purchase, cancel, failure and replay tested on staging (J-9)
- [ ] Customer emails and SMS (paid, shipped with tracking code) working (T-14)

**SEO / URLs**
- [ ] 301 redirects for products, categories, pages, tags, posts, shop endpoints (T-07)
- [ ] robots.txt, canonical fix, branded 404 (T-33)
- [ ] Search Console: submit sitemap (optional) and monitor 404s after cutover

**Security / operations**
- [ ] TLS on real domain, HSTS, `manage.py check --deploy` clean (T-06)
- [ ] Frontend assets self-hosted (T-17)
- [ ] Automated backups with tested restore (T-18)
- [ ] Error monitoring enabled (T-40)
- [ ] Secrets only in environment; `DEBUG=False`
- [ ] Pending migration generated and reviewed; test suite green on PostgreSQL (T-41, J-16)
- [ ] Enamad seal re-issued for new site (T-16)

**Business decisions**
- [ ] Mobile app and Telegram bots plan (T-21)
- [ ] Returns/refund policy aligned with published terms (T-31)
- [ ] Cutover plan: freeze WordPress orders, final export, DNS switch, rollback plan

---

*End of report. No application code, settings, templates, models, migrations, dependencies or database records were modified during this audit.*
