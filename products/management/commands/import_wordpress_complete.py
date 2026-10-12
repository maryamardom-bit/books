import csv
import re
import xml.etree.ElementTree as ET
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from html import unescape
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from core.money import MoneyConversionError, parse_amount, woo_amount_to_toman
from orders.models import Order
from pages.models import SitePage
from products.management.commands.correct_imported_order_amounts import ADVISORY_LOCK_KEY
from products.management.commands.import_wordpress import fetch
from products.models import Comment, DiscountCode, Product

User = get_user_model()
NS = {
    'wp': 'http://wordpress.org/export/1.2/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
    'excerpt': 'http://wordpress.org/export/1.2/excerpt/',
    'dc': 'http://purl.org/dc/elements/1.1/',
}


def _text(el):
    return (el.text or '') if el is not None else ''


def parse_dt(value):
    try:
        dt = datetime.fromisoformat(value)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    except Exception:
        return timezone.now()


def parse_source_dt(value):
    """Like parse_dt, but None for a missing or invalid date instead of the current time."""
    try:
        dt = datetime.fromisoformat((value or '').strip())
    except ValueError:
        return None
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


PAID_STATUSES = ('wc-completed', 'wc-refunded', 'wc-processing')

CONFLICT_COLUMNS = [
    'wordpress_id', 'order_id', 'reason', 'field', 'stored_value', 'source_value',
    'source_currency', 'action', 'recommended_action',
]
RECOMMENDED_ACTIONS = {
    'INVALID_SOURCE_ID': 'Fix the post id in the export; the record was not imported.',
    'DUPLICATE_SOURCE_ID': 'Remove the duplicate from the export; no occurrence was imported or updated.',
    'SOURCE_TOTAL_INVALID': 'Check _order_total in WooCommerce (missing, malformed or negative).',
    'SOURCE_TOTAL_NOT_INTEGER': 'Fractional _order_total; decide the rounding before importing this order.',
    'SOURCE_DATE_INVALID': 'Missing or invalid post_date; a new order is not created and a stored date is kept.',
    'STORED_EQUALS_PROVISIONAL_CONVERSION': (
        'Stored total equals the source converted with the provisional, unapproved factors. '
        'Numerical equality is not evidence of approval; review manually.'
    ),
    'TOTAL_CONFLICT': 'Stored total matches neither the source value nor its provisional conversion; review manually.',
    'IS_PAID_CONFLICT': 'Stored paid flag differs from the source status; review manually.',
    'OWNERSHIP_CONFLICT': 'The source customer differs from the stored order owner; the owner was kept. Review manually.',
    'CONTACT_CONFLICT': 'The source contact field differs from the stored value; the stored value was kept.',
    'MISSING_IN_SOURCE': 'Imported order is not in this export; confirm the export is complete. Nothing was changed.',
    'WRITE_ERROR': 'The order could not be written and was rolled back; see the importer error output.',
    'RUN_INCOMPLETE': 'The import stopped early; orders after this point were not processed.',
}
CONTACT_FIELDS = (('first', 'first_name'), ('last', 'last_name'), ('phone', 'phone_number'), ('address', 'address'))


def _order_items(path):
    for _, elem in ET.iterparse(path, events=('end',)):
        if elem.tag != 'item':
            continue
        post_type = _text(elem.find('wp:post_type', NS))
        if not post_type or post_type == 'shop_order':
            yield elem
        elem.clear()


def _order_wp_id(elem):
    raw = _text(elem.find('wp:post_id', NS)).strip()
    return raw, (int(raw) if raw.isascii() and raw.isdigit() and int(raw) > 0 else None)


def _source_total(raw):
    """Return (whole_amount, None) or (None, reason). The source unit is kept as-is."""
    try:
        amount = parse_amount(raw)
    except MoneyConversionError:
        return None, 'SOURCE_TOTAL_INVALID'
    if amount != amount.to_integral_value():
        return None, 'SOURCE_TOTAL_NOT_INTEGER'
    return int(amount), None


def _provisional_toman(raw, currency):
    try:
        return woo_amount_to_toman(raw, currency)
    except MoneyConversionError:
        return None


def _csv_safe(value):
    text = '' if value is None else str(value)
    return f"'{text}" if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text


class ConflictReport:
    """
    Collects order conflicts. With a path, the file is created exclusively before anything is
    imported and every row is flushed as soon as its order is committed, so an interrupted run
    still leaves a report of everything processed so far.
    """

    def __init__(self, path=None):
        self.path = path
        self.rows = []
        self._handle = self._writer = None

    def open(self):
        if self.path is None:
            return
        if self.path.exists():
            raise CommandError(f'{self.path} already exists; choose a new conflict report path.')
        if not self.path.parent.is_dir():
            raise CommandError(f'Conflict report directory does not exist: {self.path.parent}')
        try:
            self._handle = self.path.open('x', encoding='utf-8', newline='')
        except OSError as exc:
            raise CommandError(f'Cannot create the conflict report: {exc.strerror or exc}') from None
        self._writer = csv.writer(self._handle)
        self._writer.writerow(CONFLICT_COLUMNS)
        self._handle.flush()

    def add(self, *rows):
        self.rows.extend(rows)
        if self._writer:
            for row in rows:
                self._writer.writerow([_csv_safe(row[column]) for column in CONFLICT_COLUMNS])
            self._handle.flush()

    def close(self):
        if self._handle:
            self._handle.close()
            self._handle = self._writer = None


@contextmanager
def correction_exclusion():
    """
    Holds the order-amount correction advisory lock (session level) for the whole order import, so
    an import and a correction or rollback can never run at the same time on PostgreSQL.
    """
    if connection.vendor != 'postgresql':
        yield
        return
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [ADVISORY_LOCK_KEY])
        acquired = cursor.fetchone()[0]
    if not acquired:
        raise CommandError('An order amount correction or rollback holds the maintenance lock; order import refused.')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [ADVISORY_LOCK_KEY])


def unique_username(base):
    base = re.sub(r'[^A-Za-z0-9@.+_-]', '', base)[:140] or 'wpuser'
    candidate = base
    n = 1
    while User.objects.filter(username=candidate).exists():
        n += 1
        candidate = f'{base[:140 - len(str(n)) - 1]}-{n}'
    return candidate


class Command(BaseCommand):
    help = 'Import remaining WordPress WXR data: private products, pages, posts, coupons, orders, comments, covers.'

    def add_arguments(self, parser):
        parser.add_argument('--dir', required=True)
        parser.add_argument('--skip-images', action='store_true')
        parser.add_argument('--skip-orders', action='store_true')
        parser.add_argument(
            '--only-orders', action='store_true',
            help='Import orders only: no products, prices, stock, images, comments, pages or coupons.',
        )
        parser.add_argument(
            '--conflict-report',
            help='Write order conflicts (no personal data) to this CSV file; it must not exist yet.',
        )

    def handle(self, *args, **options):
        if options['only_orders'] and options['skip_orders']:
            raise CommandError('--only-orders and --skip-orders cannot be combined.')
        report = ConflictReport(Path(options['conflict_report']) if options.get('conflict_report') else None)
        report.open()
        try:
            self._run(options, report)
        finally:
            report.close()

    def _run(self, options, report):
        folder = Path(options['dir'])
        orders_xml = folder / 'shop_order.xml'
        if options['only_orders']:
            if not orders_xml.exists():
                raise CommandError(f'{orders_xml} not found.')
            self._import_orders(orders_xml, report)
            self.stdout.write(self.style.SUCCESS('Order transfer finished (orders only).'))
            return
        product_xml = folder / 'product.xml'
        if product_xml.exists():
            self.stdout.write('Importing all products including private…')
            call_command('import_wordpress_wxr', file=str(product_xml), include_private=True)
            if not options['skip_images']:
                self._import_images(folder)
            self._import_comments(product_xml)
        pages_xml = folder / 'pages.xml'
        posts_xml = folder / 'posts.xml'
        if pages_xml.exists():
            self._import_site_pages(pages_xml, 'page')
        if posts_xml.exists():
            self._import_site_pages(posts_xml, 'post')
        coupons_xml = folder / 'shop_coupon.xml'
        if coupons_xml.exists():
            self._import_coupons(coupons_xml)
        if orders_xml.exists() and not options['skip_orders']:
            self._import_orders(orders_xml, report)
        self.stdout.write(self.style.SUCCESS('Full WordPress transfer finished.'))

    def _attachment_urls(self, folder):
        path = folder / 'attachment.xml'
        urls = {}
        if not path.exists():
            return urls
        for _, elem in ET.iterparse(path, events=('end',)):
            if elem.tag != 'item':
                continue
            pid = _text(elem.find('wp:post_id', NS))
            url = _text(elem.find('wp:attachment_url', NS))
            if pid and url:
                urls[pid] = url
            elem.clear()
        return urls

    def _import_images(self, folder):
        urls = self._attachment_urls(folder)
        self.stdout.write(f'Attachment map: {len(urls)} files')
        attached = 0
        for _, elem in ET.iterparse(folder / 'product.xml', events=('end',)):
            if elem.tag != 'item':
                continue
            if _text(elem.find('wp:post_type', NS)) not in ('', 'product'):
                elem.clear()
                continue
            wp_id = _text(elem.find('wp:post_id', NS))
            product = Product.objects.filter(wordpress_id=int(wp_id or 0)).first()
            if not product or product.image:
                elem.clear()
                continue
            thumb = ''
            for meta in elem.findall('wp:postmeta', NS):
                if _text(meta.find('wp:meta_key', NS)) == '_thumbnail_id':
                    thumb = _text(meta.find('wp:meta_value', NS))
                    break
            image_url = urls.get(thumb)
            if image_url:
                try:
                    body, headers = fetch(image_url)
                    ctype = headers.get('Content-Type', 'image/jpeg').split(';')[0]
                    if ctype.startswith('image/'):
                        ext = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}.get(ctype, 'jpg')
                        product.image.save(f'wp-{wp_id}.{ext}', ContentFile(body), save=True)
                        attached += 1
                except Exception:
                    pass
            elem.clear()
        self.stdout.write(f'Covers attached: {attached}')

    def _ensure_user(self, *, email='', login='', wp_id=0, first='', last='', phone='', address=''):
        email = (email or '').strip().lower()
        wp_id = int(wp_id or 0)
        if wp_id:
            user = User.objects.filter(wordpress_id=wp_id).first()
            if user:
                return user
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user:
                if wp_id and not user.wordpress_id:
                    user.wordpress_id = wp_id
                    user.save(update_fields=['wordpress_id'])
                return user
        username = unique_username(login or (email.split('@')[0] if email else f'wp-{wp_id or "guest"}'))
        user = User(username=username, email=email, first_name=(first or '')[:150], last_name=(last or '')[:150])
        if wp_id:
            user.wordpress_id = wp_id
        if address:
            user.address = address[:5000]
        user.set_unusable_password()
        user.save()
        return user

    def _import_comments(self, path):
        created = 0
        for _, elem in ET.iterparse(path, events=('end',)):
            if elem.tag != 'item':
                continue
            if _text(elem.find('wp:post_type', NS)) not in ('', 'product'):
                elem.clear()
                continue
            wp_id = int(_text(elem.find('wp:post_id', NS)) or 0)
            product = Product.objects.filter(wordpress_id=wp_id).first()
            if not product:
                elem.clear()
                continue
            for comment in elem.findall('wp:comment', NS):
                ctype = _text(comment.find('wp:comment_type', NS))
                if ctype and ctype not in ('review', 'comment', ''):
                    continue
                cid = int(_text(comment.find('wp:comment_id', NS)) or 0)
                body = unescape(_text(comment.find('wp:comment_content', NS))).strip()
                if not cid or not body:
                    continue
                if Comment.objects.filter(wordpress_id=cid).exists():
                    continue
                rating = 5
                for meta in comment.findall('wp:commentmeta', NS):
                    if _text(meta.find('wp:meta_key', NS)) == 'rating':
                        try:
                            rating = min(5, max(1, int(_text(meta.find('wp:meta_value', NS)) or 5)))
                        except ValueError:
                            rating = 5
                author = self._ensure_user(
                    email=_text(comment.find('wp:comment_author_email', NS)),
                    login=_text(comment.find('wp:comment_author', NS)) or f'comment-{cid}',
                )
                approved = _text(comment.find('wp:comment_approved', NS))
                Comment.objects.create(
                    wordpress_id=cid,
                    product=product,
                    author=author,
                    body=body[:20000],
                    stars=rating,
                    active=approved in ('1', 'yes', 'true'),
                )
                created += 1
            elem.clear()
        self.stdout.write(f'Comments imported: {created}')

    def _import_site_pages(self, path, source):
        created = 0
        for _, elem in ET.iterparse(path, events=('end',)):
            if elem.tag != 'item':
                continue
            wp_id = int(_text(elem.find('wp:post_id', NS)) or 0)
            status = _text(elem.find('wp:status', NS))
            title = unescape(_text(elem.find('title')))[:250] or f'{source}-{wp_id}'
            slug = f'wp-{source}-{wp_id}'
            SitePage.objects.update_or_create(
                wordpress_id=wp_id,
                defaults={
                    'title': title,
                    'slug': slug,
                    'content': _text(elem.find('content:encoded', NS)),
                    'excerpt': _text(elem.find('excerpt:encoded', NS)),
                    'source': source,
                    'status': status,
                    'is_active': status == 'publish',
                    'datetime_created': parse_dt(_text(elem.find('wp:post_date', NS))),
                },
            )
            created += 1
            elem.clear()
        self.stdout.write(f'{source} records: {created}')

    def _import_coupons(self, path):
        """
        Creates codes that do not exist yet. Existing codes are never updated: used_count counts
        redemptions made in Django, amount may be a corrected value, and active may be an admin
        decision. Differences are counted per field (codes are not printed).
        """
        created = preserved = 0
        differing = Counter()
        for _, elem in ET.iterparse(path, events=('end',)):
            if elem.tag != 'item':
                continue
            status = _text(elem.find('wp:status', NS))
            code = (_text(elem.find('title')) or _text(elem.find('wp:post_name', NS))).strip()[:50]
            if not code:
                elem.clear()
                continue
            metas = {
                _text(m.find('wp:meta_key', NS)): _text(m.find('wp:meta_value', NS))
                for m in elem.findall('wp:postmeta', NS)
            }
            dtype = metas.get('discount_type') or ''
            amount_raw = metas.get('coupon_amount') or '0'
            try:
                amount_val = float(amount_raw)
            except ValueError:
                amount_val = 0
            percent = int(amount_val) if 'percent' in dtype else 0
            amount = 0 if percent else int(amount_val)
            try:
                max_uses = int(float(metas.get('usage_limit') or 0)) or 999999
            except ValueError:
                max_uses = 999999
            try:
                used = int(float(metas.get('usage_count') or 0))
            except ValueError:
                used = 0
            expiry = metas.get('expiry_date') or metas.get('date_expires') or ''
            valid_until = parse_dt(expiry) if expiry else None
            values = {
                'percent': min(percent, 100),
                'amount': max(amount, 0),
                'max_uses': max_uses,
                'used_count': used,
                'active': status == 'publish',
                'valid_until': valid_until,
            }
            existing = DiscountCode.objects.filter(code=code).first()
            if existing is None:
                DiscountCode.objects.create(code=code, **values)
                created += 1
            else:
                preserved += 1
                differing.update(field for field, value in values.items() if getattr(existing, field) != value)
            elem.clear()
        self.stdout.write(f'Coupons imported: new={created} existing_preserved={preserved}')
        if differing:
            fields = ' '.join(f'{field}={count}' for field, count in sorted(differing.items()))
            self.stdout.write(self.style.WARNING(f'Existing coupons differing from the export (kept as stored): {fields}'))

    def _import_orders(self, path, report):
        """
        New orders are created with the source total as-is (no unit conversion). For existing
        orders only order_notes and payment_method are refreshed: total_price, is_paid, the owner,
        the contact fields and a stored date are kept, and any difference is reported.
        """
        with correction_exclusion():
            self._import_order_items(path, report)

    def _import_order_items(self, path, report):
        id_counts = Counter(_order_wp_id(elem)[1] for elem in _order_items(path))
        created = updated = skipped = 0
        seen = set()
        finished = False
        try:
            for elem in _order_items(path):
                raw_id, wp_id = _order_wp_id(elem)
                if wp_id is None:
                    report.add(self._conflict(raw_id, None, 'INVALID_SOURCE_ID', 'wordpress_id', action='NOT_IMPORTED'))
                    skipped += 1
                    continue
                seen.add(wp_id)
                if id_counts[wp_id] > 1:
                    existing_pk = Order.objects.filter(wordpress_id=wp_id).values_list('pk', flat=True).first()
                    report.add(self._conflict(wp_id, existing_pk, 'DUPLICATE_SOURCE_ID', 'wordpress_id', action='NOT_IMPORTED'))
                    skipped += 1
                    continue
                source = self._order_source(elem)
                pending = []
                try:
                    with transaction.atomic():
                        outcome = self._apply_order(wp_id, source, pending)
                except Exception as exc:
                    # The message may contain personal data from the source; only the type is shown.
                    self.stderr.write(f'  ! order {wp_id}: {type(exc).__name__}')
                    existing_pk = Order.objects.filter(wordpress_id=wp_id).values_list('pk', flat=True).first()
                    report.add(self._conflict(
                        wp_id, existing_pk, 'WRITE_ERROR', '', source_value=type(exc).__name__, action='NOT_APPLIED',
                    ))
                    skipped += 1
                    continue
                report.add(*pending)
                created += outcome == 'created'
                updated += outcome == 'updated'
                skipped += outcome == 'skipped'
                if (created + updated) and (created + updated) % 500 == 0:
                    self.stdout.write(f'  orders {created + updated}')
            for pk, wp_id in Order.objects.filter(wordpress_id__isnull=False).order_by('wordpress_id').values_list('pk', 'wordpress_id'):
                if wp_id not in seen:
                    report.add(self._conflict(wp_id, pk, 'MISSING_IN_SOURCE', 'wordpress_id', action='NONE'))
            finished = True
        finally:
            if not finished:
                report.add(self._conflict('', None, 'RUN_INCOMPLETE', '', action='STOPPED'))
        self.stdout.write(f'Orders imported: new={created} updated={updated} skipped={skipped} conflicts={len(report.rows)}')
        self._report_conflicts(report)

    def _order_source(self, elem):
        metas = {
            _text(m.find('wp:meta_key', NS)): _text(m.find('wp:meta_value', NS))
            for m in elem.findall('wp:postmeta', NS)
        }
        email = metas.get('_billing_email') or ''
        address_parts = [
            metas.get('_billing_address_1') or '',
            metas.get('_billing_address_2') or '',
            metas.get('_billing_city') or '',
            metas.get('_billing_state') or '',
            metas.get('_billing_postcode') or '',
        ]
        notes = []
        for comment in elem.findall('wp:comment', NS):
            content = unescape(_text(comment.find('wp:comment_content', NS))).strip()
            if content:
                notes.append(re.sub(r'<[^>]+>', ' ', content))
        method = metas.get('_payment_method') or 'online'
        status = _text(elem.find('wp:status', NS))
        return {
            'status': status,
            'paid': status in PAID_STATUSES,
            'email': email,
            'customer_wp_id': metas.get('_customer_user') or 0,
            'first': (metas.get('_billing_first_name') or '')[:100],
            'last': (metas.get('_billing_last_name') or '')[:100],
            'phone': re.sub(r'\D', '', metas.get('_billing_phone') or '')[:15],
            'address': '، '.join(p for p in address_parts if p)[:700],
            'notes': '\n'.join(notes)[:700],
            'total': metas.get('_order_total', ''),
            'currency': metas.get('_order_currency', ''),
            'payment_method': 'online' if 'install' not in method else 'installment',
            'created_at': parse_source_dt(_text(elem.find('wp:post_date', NS))),
        }

    def _apply_order(self, wp_id, source, conflicts):
        existing = Order.objects.select_for_update(of=('self',)).select_related('user').filter(wordpress_id=wp_id).first()
        total, total_problem = _source_total(source['total'])
        if existing is not None:
            return self._update_existing_order(existing, source, total, total_problem, conflicts)
        if total_problem:
            conflicts.append(self._conflict(
                wp_id, None, total_problem, 'total_price', source_value=source['total'],
                source_currency=source['currency'], action='NOT_CREATED',
            ))
            return 'skipped'
        if source['created_at'] is None:
            conflicts.append(self._conflict(wp_id, None, 'SOURCE_DATE_INVALID', 'datetime_created', action='NOT_CREATED'))
            return 'skipped'

        user = self._ensure_user(
            email=source['email'],
            login=source['email'].split('@')[0] if source['email'] else f'order-{wp_id}',
            wp_id=int(source['customer_wp_id'] or 0),
            first=source['first'],
            last=source['last'],
            phone=source['phone'],
            address=source['address'],
        )
        order = Order.objects.create(
            wordpress_id=wp_id,
            total_price=total,
            is_paid=source['paid'],
            user=user,
            first_name=source['first'] or user.first_name or '—',
            last_name=source['last'] or user.last_name or '—',
            phone_number=source['phone'] or '00000000000',
            address=source['address'] or '—',
            order_notes=source['notes'],
            payment_method=source['payment_method'],
        )
        Order.objects.filter(pk=order.pk).update(datetime_created=source['created_at'])
        return 'created'

    def _update_existing_order(self, order, source, total, total_problem, conflicts):
        fields = {'order_notes': source['notes'], 'payment_method': source['payment_method']}
        if source['created_at'] is None:
            conflicts.append(self._conflict(
                order.wordpress_id, order.pk, 'SOURCE_DATE_INVALID', 'datetime_created', action='STORED_PRESERVED',
            ))
        else:
            fields['datetime_created'] = source['created_at']
        Order.objects.filter(pk=order.pk).update(datetime_modified=timezone.now(), **fields)
        self._compare_owner_and_contact(order, source, conflicts)
        self._compare_financials(order, total, total_problem, source, conflicts)
        return 'updated'

    def _compare_owner_and_contact(self, order, source, conflicts):
        """Values are personal data, so only the field name is reported."""
        email = (source['email'] or '').strip().lower()
        customer_wp_id = int(source['customer_wp_id'] or 0)
        owner = order.user
        if (customer_wp_id and owner.wordpress_id != customer_wp_id) or (email and (owner.email or '').lower() != email):
            conflicts.append(self._conflict(order.wordpress_id, order.pk, 'OWNERSHIP_CONFLICT', 'user', action='STORED_PRESERVED'))
        for source_key, field in CONTACT_FIELDS:
            if source[source_key] and source[source_key] != getattr(order, field):
                conflicts.append(self._conflict(order.wordpress_id, order.pk, 'CONTACT_CONFLICT', field, action='STORED_PRESERVED'))

    def _compare_financials(self, order, total, total_problem, source, conflicts):
        common = {'source_currency': source['currency'], 'action': 'STORED_PRESERVED'}
        if total_problem:
            conflicts.append(self._conflict(
                order.wordpress_id, order.pk, total_problem, 'total_price',
                stored_value=order.total_price, source_value=source['total'], **common,
            ))
        elif order.total_price != total:
            converted = _provisional_toman(source['total'], source['currency'])
            reason = 'STORED_EQUALS_PROVISIONAL_CONVERSION' if converted == order.total_price else 'TOTAL_CONFLICT'
            conflicts.append(self._conflict(
                order.wordpress_id, order.pk, reason, 'total_price',
                stored_value=order.total_price, source_value=source['total'], **common,
            ))
        if order.is_paid != source['paid']:
            conflicts.append(self._conflict(
                order.wordpress_id, order.pk, 'IS_PAID_CONFLICT', 'is_paid',
                stored_value=order.is_paid, source_value=source['status'], **common,
            ))

    @staticmethod
    def _conflict(wp_id, order_id, reason, field, stored_value='', source_value='', source_currency='', action=''):
        return {
            'wordpress_id': wp_id,
            'order_id': '' if order_id is None else order_id,
            'reason': reason,
            'field': field,
            'stored_value': stored_value,
            'source_value': source_value,
            'source_currency': source_currency,
            'action': action,
            'recommended_action': RECOMMENDED_ACTIONS[reason],
        }

    def _report_conflicts(self, report):
        conflicts = report.rows
        if not conflicts:
            return
        by_reason = Counter(c['reason'] for c in conflicts)
        self.stdout.write(self.style.WARNING('Order conflicts (financial fields were not changed):'))
        for reason, count in sorted(by_reason.items()):
            self.stdout.write(f'  {reason}: {count}')
        if report.path:
            self.stdout.write(f'Conflict report written to {report.path}')
            return
        shown = conflicts[:20]
        for c in shown:
            self.stdout.write(
                f"  wordpress_id={c['wordpress_id']} reason={c['reason']} field={c['field']} "
                f"stored={c['stored_value']} source={c['source_value']} action={c['action']}"
            )
        if len(conflicts) > len(shown):
            self.stdout.write(f'  ... {len(conflicts) - len(shown)} more; pass --conflict-report to export all of them.')
