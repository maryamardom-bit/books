import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from products.management.commands.import_wordpress import (
    COVER_MAP,
    SIZE_MAP,
    map_category,
)
from products.models import Product

NS = {
    'wp': 'http://wordpress.org/export/1.2/',
    'content': 'http://purl.org/rss/1.0/modules/content/',
}

ATTR_MAP = {
    'pa_نویسنده': 'author',
    'pa_مترجم': 'edition',
    'pa_ناشر': 'publisher',
    'pa_شابک': 'isbn',
    'pa_قطع': 'book_size_label',
    'pa_نوع-صحافیجلد': 'cover_label',
    'pa_سال-چاپ': 'year',
    'pa_تاریخ-نشر': 'year_alt',
    'pa_تعداد-صفحه': 'pages',
    'pa_نوبت-چاپ': 'printing',
}


def _text(el):
    return (el.text or '') if el is not None else ''


def woo_price_to_toman(raw):
    raw = (raw or '').strip()
    if not raw:
        return 0
    try:
        value = int(float(raw.replace(',', '')))
    except ValueError:
        return 0
    if value <= 0:
        return 0
    # Storefront displays these units as «هزار تومان».
    if value < 20000:
        return value * 1000
    return value


class Command(BaseCommand):
    help = 'Update catalog fields from a WooCommerce WXR product export.'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True)
        parser.add_argument('--include-private', action='store_true')

    def handle(self, *args, **options):
        path = options['file']
        include_private = options['include_private']
        updated = skipped = created = missing = 0
        try:
            context = ET.iterparse(path, events=('end',))
        except OSError as exc:
            raise CommandError(str(exc)) from exc

        for _, elem in context:
            if elem.tag != 'item':
                continue
            post_type = _text(elem.find('wp:post_type', NS))
            if post_type and post_type != 'product':
                elem.clear()
                continue
            status = _text(elem.find('wp:status', NS))
            if status not in ('publish', 'private', 'draft', 'pending'):
                skipped += 1
                elem.clear()
                continue
            wp_id = int(_text(elem.find('wp:post_id', NS)) or 0)
            if not wp_id:
                skipped += 1
                elem.clear()
                continue
            fields = self._fields_from_item(elem, status)
            obj = Product.objects.filter(wordpress_id=wp_id).first()
            if obj is None:
                obj, was_new = Product.objects.update_or_create(
                    wordpress_id=wp_id,
                    defaults=fields,
                )
                created += int(was_new)
                updated += int(not was_new)
            else:
                for key, value in fields.items():
                    if key in ('description', 'title') and value:
                        setattr(obj, key, value)
                    elif key in ('author', 'edition', 'publisher', 'isbn', 'printing_series') and value:
                        setattr(obj, key, value)
                    elif key in ('year_of_publication', 'publication_date', 'number_of_pages', 'book_size', 'cover_type') and value:
                        setattr(obj, key, value)
                    elif key in ('price', 'special_price', 'stock') and value:
                        setattr(obj, key, value)
                    elif key == 'category' and value:
                        setattr(obj, key, value)
                    elif key == 'active':
                        setattr(obj, key, value)
                obj.save()
                updated += 1
            if obj.category == Product.Category.PACKAGES:
                from products.models import Package
                Package.objects.update_or_create(
                    wordpress_id=wp_id,
                    defaults={
                        'title': obj.title[:200],
                        'slug': f'wp-{wp_id}',
                        'description': unescape(_text(elem.find('content:encoded', NS)))[:5000],
                        'manual_price': obj.special_price or obj.price,
                        'price': obj.special_price or obj.price,
                        'original_price': obj.price,
                        'stock': obj.stock,
                        'active': obj.active,
                    },
                )
            elem.clear()

        self.stdout.write(self.style.SUCCESS(
            f'WXR applied. updated={updated} created={created} skipped={skipped} missing={missing}'
        ))

    def _fields_from_item(self, elem, status):
        title = unescape(_text(elem.find('title')))[:200]
        description = _text(elem.find('content:encoded', NS)) or title
        metas = {}
        for meta in elem.findall('wp:postmeta', NS):
            metas[_text(meta.find('wp:meta_key', NS))] = _text(meta.find('wp:meta_value', NS))
        attrs = {}
        cats = []
        for cat in elem.findall('category'):
            domain = cat.get('domain') or ''
            value = (cat.text or '').strip()
            if not value or value == '-':
                continue
            if domain.startswith('pa_'):
                attrs.setdefault(domain, []).append(value)
            if domain == 'product_cat':
                cats.append(value)

        def joined(key):
            return '، '.join(attrs.get(key, []))

        author = joined('pa_نویسنده')[:200]
        translator = joined('pa_مترجم')[:100]
        publisher = joined('pa_ناشر')[:200] or 'کتابکده کسری'
        isbn = (joined('pa_شابک') or metas.get('_sku') or '')[:30]
        size_label = joined('pa_قطع').split('،')[0].strip()
        cover_label = joined('pa_نوع-صحافیجلد').split('،')[0].strip()
        year_raw = joined('pa_سال-چاپ') or joined('pa_تاریخ-نشر')
        pages_raw = joined('pa_تعداد-صفحه')
        printing = joined('pa_نوبت-چاپ')[:100]
        year = None
        digits = ''.join(ch for ch in year_raw if ch.isdigit())
        if digits:
            year = int(digits[:4]) if len(digits) >= 4 else int(digits)
        pages = None
        pdigits = ''.join(ch for ch in pages_raw if ch.isdigit())
        if pdigits:
            pages = int(pdigits)
        regular = woo_price_to_toman(metas.get('_regular_price') or metas.get('_price'))
        sale = woo_price_to_toman(metas.get('_sale_price'))
        special = sale if sale and regular and sale < regular else 0
        try:
            stock = int(float(metas.get('_stock') or 0))
        except ValueError:
            stock = 0
        if metas.get('_stock_status') == 'outofstock':
            stock = 0
        elif stock < 0:
            stock = 0
        category = map_category(' '.join(cats), title)
        if any(token in title for token in ('بسته', 'مجموعه کتب', 'مجموعه کتاب')):
            category = Product.Category.PACKAGES
        created_at = _text(elem.find('wp:post_date', NS))
        try:
            dt = datetime.fromisoformat(created_at)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
        except Exception:
            dt = timezone.now()
        return {
            'title': title,
            'description': description or title,
            'category': category,
            'author': author,
            'edition': translator,
            'publisher': publisher,
            'isbn': isbn,
            'book_size': SIZE_MAP.get(size_label, Product.BookSize.OTHER if size_label else None),
            'cover_type': COVER_MAP.get(cover_label, Product.CoverType.OTHER if cover_label else None),
            'year_of_publication': year,
            'publication_date': year,
            'number_of_pages': pages,
            'printing_series': printing,
            'price': regular or sale,
            'special_price': special,
            'stock': stock,
            'active': status in ('publish', 'private'),
            'datetime_created': dt,
        }
