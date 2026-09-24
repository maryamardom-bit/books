from html.parser import HTMLParser
from html import unescape
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from pages.models import AboutUs, ContactInfo, CooperationInfo, OrderCondition
from products.models import Package, Product


WP_BASE = 'https://kasrapublishing.ir'
CTX = ssl._create_unverified_context()
UA = {'User-Agent': 'KasraImporter/1.0 (catalog migration; +https://kasrapublishing.ir)'}

CATEGORY_MAP = (
    ('داخلی', Product.Category.INTERIOR),
    ('منظر', Product.Category.LANDSCAPE),
    ('لنداسکیپ', Product.Category.LANDSCAPE),
    ('شهر', Product.Category.URBAN),
    ('کسب', Product.Category.BUSINESS),
    ('دیجیتال', Product.Category.DIGITAL),
    ('پایدار', Product.Category.SUSTAIN),
    ('تاریخ', Product.Category.HISTORY),
    ('نقد', Product.Category.HISTORY),
    ('نظریه', Product.Category.HISTORY),
    ('مقدمات', Product.Category.DESIGN_BASICS),
    ('بیان', Product.Category.DESIGN_BASICS),
    ('راهنما', Product.Category.DESIGN_GUIDE),
    ('نمونه', Product.Category.SAMPLES),
    ('بسته', Product.Category.PACKAGES),
    ('مجموعه', Product.Category.PACKAGES),
    ('طراحی معماری', Product.Category.ARCH_DESIGN),
    ('معماری', Product.Category.ARCH_DESIGN),
)

SIZE_MAP = {
    'رقعی': Product.BookSize.RAGHIEI,
    'وزیری': Product.BookSize.VAZEHI,
    'جیبی': Product.BookSize.JEYBI,
    'رحلی': Product.BookSize.RAHLEI,
}

COVER_MAP = {
    'شومیز': Product.CoverType.SHOMIZ,
    'جلد سخت': Product.CoverType.GARD,
    'گالینگور': Product.CoverType.GARD,
}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)


def html_text(fragment):
    parser = _TextExtractor()
    try:
        parser.feed(fragment)
    except Exception:
        return unescape(re.sub(r'<[^>]+>', ' ', fragment))
    return unescape(' '.join(parser.parts))


def encode_url(url):
    url = (url or '').replace('http://', 'https://')
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe='/%')
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def fetch(url, timeout=40):
    req = urllib.request.Request(encode_url(url), headers=UA)
    with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
        headers = dict(resp.headers.items())
        return resp.read(), headers


def fetch_json(url):
    body, headers = fetch(url)
    return json.loads(body.decode('utf-8')), headers


def map_category(label, title=''):
    hay = f'{label} {title}'
    for needle, code in CATEGORY_MAP:
        if needle in hay:
            return code
    return Product.Category.OTHER


def parse_price_toman(price_html):
    if not price_html:
        return 0, 0
    dels = re.findall(
        r'<del[^>]*>.*?woocommerce-Price-amount[^>]*>(.*?)</span>',
        price_html,
        re.S | re.I,
    )
    ins = re.findall(
        r'<ins[^>]*>.*?woocommerce-Price-amount[^>]*>(.*?)</span>',
        price_html,
        re.S | re.I,
    )
    amounts = re.findall(
        r'woocommerce-Price-amount[^>]*>(.*?)</span>',
        price_html,
        re.S | re.I,
    )
    def to_int(chunk):
        text = html_text(chunk)
        digits = re.sub(r'[^\d]', '', text)
        if not digits:
            return 0
        value = int(digits)
        if 'هزار' in text:
            value *= 1000
        elif 'ریال' in text:
            value = value // 10
        return value

    sale = to_int(ins[0]) if ins else 0
    original = to_int(dels[0]) if dels else 0
    current = to_int(amounts[0]) if amounts else 0
    if sale and original:
        return original, sale
    return current, 0


def parse_options(block):
    result = {}
    for heading, items in re.findall(
        r'<h4>(.*?)</h4>\s*<ul>(.*?)</ul>',
        block,
        re.S | re.I,
    ):
        key = html_text(heading).replace('محصول', '').replace(':', '').strip()
        values = [html_text(m) for m in re.findall(r'<a[^>]*>(.*?)</a>', items, re.S | re.I)]
        values = [v for v in values if v and v != '-']
        if values:
            result[key] = values
    return result


def parse_product_html(html, wp_id):
    marker = f'id="product-{wp_id}"'
    start = html.find(marker)
    chunk = html[start:] if start >= 0 else html
    for stop in ('related products', 'upsells', 'id="tab-reviews"'):
        idx = chunk.lower().find(stop)
        if idx > 500:
            chunk = chunk[:idx]
            break
    summary_m = re.search(r'class="summary entry-summary"(.*?)</div><!-- \.summary -->', chunk, re.S)
    summary = summary_m.group(1) if summary_m else chunk[:8000]
    cat_m = re.search(r'class="product_category">(.*?)</div>', summary, re.S)
    price_m = re.search(r'<p class="price">(.*?)</p>', summary, re.S)
    stock_in = 'in-stock' in summary or 'موجود در انبار' in summary
    qty_m = re.search(r'name="quantity"[^>]*max="(\d+)"', summary)
    options_m = re.search(r'class="product_options">(.*?)</div>', summary, re.S)
    options = parse_options(options_m.group(1)) if options_m else {}
    regular, special = parse_price_toman(price_m.group(1) if price_m else '')
    stock = 0
    if stock_in:
        stock = int(qty_m.group(1)) if qty_m else 10
    return {
        'wp_category': html_text(cat_m.group(1)) if cat_m else '',
        'price': regular,
        'special_price': special,
        'stock': stock,
        'options': options,
    }


def option_join(options, *keys):
    for key in keys:
        if key in options:
            return '، '.join(options[key])
    for want in keys:
        for key, values in options.items():
            if want in key:
                return '، '.join(values)
    return ''


def parse_shop_card(block):
    cat_m = re.search(r'class="product_category">(.*?)</div>', block, re.S)
    price_m = re.search(r'class="price">(.*?)<div class="product_options">', block, re.S)
    if not price_m:
        price_m = re.search(r'<p class="price">(.*?)</p>', block, re.S)
    if not price_m:
        price_m = re.search(r'class="price">(.*?)</span></span>', block, re.S)
    options_m = re.search(r'class="product_options">(.*?)</div>', block, re.S)
    sku_m = re.search(r'data-product_sku="([^"]*)"', block)
    head = block[:500]
    if 'outofstock' in head:
        stock = 0
    elif 'instock' in head:
        stock = 10
    else:
        stock = 10
    regular, special = parse_price_toman(price_m.group(1) if price_m else '')
    isbn = (sku_m.group(1) if sku_m else '') or ''
    options = parse_options(options_m.group(1)) if options_m else {}
    if isbn and 'شابک' not in options:
        options['شابک'] = [isbn]
    return {
        'wp_category': html_text(cat_m.group(1)) if cat_m else '',
        'price': regular,
        'special_price': special,
        'stock': stock,
        'options': options,
    }


def shop_catalog(sleep=0.08):
    index = {}
    page = 1
    while True:
        url = f'{WP_BASE}/shop/' if page == 1 else f'{WP_BASE}/shop/page/{page}/'
        try:
            raw, _ = fetch(url)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                break
            raise
        html = raw.decode('utf-8', errors='ignore')
        parts = html.split('<li class="post-')
        found = 0
        for part in parts[1:]:
            match = re.match(r'(\d+) product\b', part)
            if not match:
                continue
            found += 1
            wp_id = int(match.group(1))
            details = parse_shop_card(part[:12000])
            prev = index.get(wp_id)
            if not prev or (details['options'] and not prev.get('options')):
                index[wp_id] = details
        if not found:
            break
        page += 1
        time.sleep(sleep)
    return index


def first_int(options, *keys):
    raw = option_join(options, *keys)
    digits = re.sub(r'[^\d]', '', raw)
    return int(digits) if digits else None


class Command(BaseCommand):
    help = 'Import public WooCommerce catalog from kasrapublishing.ir into this Django project.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--skip-images', action='store_true')
        parser.add_argument('--force-images', action='store_true')
        parser.add_argument('--skip-pages', action='store_true')
        parser.add_argument('--sleep', type=float, default=0.12)

    def handle(self, *args, **options):
        limit = options['limit']
        sleep = options['sleep']
        self.stdout.write('Indexing WooCommerce shop cards…')
        shop = shop_catalog(sleep=min(sleep, 0.1))
        self.stdout.write(f'Shop cards with bibliographic data: {len(shop)}')
        self.stdout.write('Fetching product list from WordPress REST API…')
        products = self._all_products(limit)
        self.stdout.write(f'Found {len(products)} published products.')
        created = updated = failed = 0
        for index, item in enumerate(products, start=1):
            try:
                was_new = self._import_product(
                    item,
                    shop_details=shop.get(item['id']),
                    skip_images=options['skip_images'],
                    force_images=options['force_images'],
                    sleep=sleep,
                )
                created += int(was_new)
                updated += int(not was_new)
            except Exception as exc:
                failed += 1
                self.stderr.write(f'  ! {item.get("id")} {exc}')
            if index % 20 == 0 or index == len(products):
                self.stdout.write(f'  {index}/{len(products)} imported (new={created} updated={updated} failed={failed})')
            time.sleep(sleep)
        if not options['skip_pages']:
            self._import_pages()
        self.stdout.write(self.style.SUCCESS(
            f'Done. new={created} updated={updated} failed={failed}'
        ))

    def _all_products(self, limit):
        items = []
        page = 1
        while True:
            url = f'{WP_BASE}/wp-json/wp/v2/product?per_page=50&page={page}'
            try:
                batch, headers = fetch_json(url)
            except urllib.error.HTTPError as exc:
                if exc.code == 400:
                    break
                raise
            if not batch:
                break
            items.extend(batch)
            total = int(headers.get('X-WP-Total', len(items)))
            if limit and len(items) >= limit:
                return items[:limit]
            if len(items) >= total:
                break
            page += 1
            time.sleep(0.1)
        return items

    def _import_product(self, item, shop_details=None, skip_images=False, force_images=False, sleep=0.12):
        wp_id = item['id']
        title = unescape(item['title']['rendered'])[:200]
        description = item.get('content', {}).get('rendered') or ''
        details = shop_details
        if not details or not details.get('options'):
            link = item.get('link') or ''
            html = ''
            if link:
                try:
                    raw, _ = fetch(link)
                    html = raw.decode('utf-8', errors='ignore')
                except Exception:
                    html = ''
            parsed = parse_product_html(html, wp_id) if html else {
                'wp_category': '', 'price': 0, 'special_price': 0, 'stock': 10, 'options': {},
            }
            if details:
                if not details.get('options'):
                    details['options'] = parsed['options']
                if not details.get('wp_category'):
                    details['wp_category'] = parsed['wp_category']
                if not details.get('price'):
                    details['price'] = parsed['price']
                    details['special_price'] = parsed['special_price']
            else:
                details = parsed
        options = details['options']
        category = map_category(details['wp_category'], title)
        if any(token in title for token in ('بسته', 'مجموعه کتب', 'مجموعه کتاب')):
            category = Product.Category.PACKAGES
        author = option_join(options, 'نویسنده')[:200]
        translator = option_join(options, 'مترجم')[:100]
        publisher = option_join(options, 'ناشر') or 'کتابکده کسری'
        isbn = option_join(options, 'شابک')[:30]
        size_label = option_join(options, 'قطع').split('،')[0].strip()
        cover_label = option_join(options, 'نوع صحافی/جلد', 'نوع جلد').split('،')[0].strip()
        book_size = SIZE_MAP.get(size_label, Product.BookSize.OTHER if size_label else None)
        cover_type = COVER_MAP.get(cover_label, Product.CoverType.OTHER if cover_label else None)
        year = first_int(options, 'سال چاپ', 'تاریخ نشر')
        pages = first_int(options, 'تعداد صفحه', 'تعداد صفحه:')
        printing = option_join(options, 'نوبت چاپ')
        created_at = item.get('date')
        try:
            dt = datetime.fromisoformat(created_at)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
        except Exception:
            dt = timezone.now()

        price = details['price'] or 0
        special = details['special_price'] or 0
        defaults = {
            'title': title,
            'category': category,
            'description': description or title,
            'price': price if not special else max(price, special),
            'special_price': special if special and special < (price or special) else 0,
            'active': item.get('status') == 'publish',
            'author': author,
            'publisher': publisher[:200],
            'isbn': isbn,
            'year_of_publication': year,
            'edition': translator,
            'number_of_pages': pages,
            'book_size': book_size,
            'cover_type': cover_type,
            'publication_date': year,
            'printing_series': printing[:100] if printing else '',
            'stock': details['stock'],
            'datetime_created': dt,
        }
        if defaults['special_price'] and defaults['price'] and defaults['special_price'] < defaults['price']:
            pass
        elif special and not price:
            defaults['price'] = special
            defaults['special_price'] = 0

        obj, created = Product.objects.update_or_create(wordpress_id=wp_id, defaults=defaults)
        if not skip_images and (force_images or not obj.image):
            image_url = self._featured_url(item)
            if not image_url and item.get('link'):
                image_url = self._og_image(item.get('link'))
            if image_url:
                self._attach_image(obj, image_url, wp_id)
                time.sleep(sleep)
        if category == Product.Category.PACKAGES:
            self._upsert_package(obj, wp_id, title, description, defaults)
        return created

    def _featured_url(self, item):
        media_id = item.get('featured_media')
        if media_id:
            try:
                media, _ = fetch_json(f'{WP_BASE}/wp-json/wp/v2/media/{media_id}')
            except Exception:
                media = None
            if media:
                details = media.get('media_details') or {}
                sizes = details.get('sizes') or {}
                for key in ('medium', 'shop_single', 'large', 'full'):
                    if key in sizes and sizes[key].get('source_url'):
                        return sizes[key]['source_url']
                if media.get('source_url'):
                    return media['source_url']
        embedded = (item.get('_embedded') or {}).get('wp:featuredmedia') or []
        if not embedded:
            return ''
        media = embedded[0]
        details = media.get('media_details') or {}
        sizes = details.get('sizes') or {}
        for key in ('medium', 'shop_single', 'large', 'full'):
            if key in sizes and sizes[key].get('source_url'):
                return sizes[key]['source_url']
        return media.get('source_url') or ''

    def _og_image(self, link):
        try:
            raw, _ = fetch(link)
        except Exception:
            return ''
        html = raw.decode('utf-8', errors='ignore')
        match = re.search(r'property="og:image" content="([^"]+)"', html)
        return match.group(1) if match else ''

    def _attach_image(self, obj, url, wp_id):
        try:
            body, headers = fetch(url)
        except Exception:
            return
        ctype = headers.get('Content-Type', 'image/jpeg').split(';')[0]
        if not ctype.startswith('image/'):
            return
        ext = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp'}.get(ctype, 'jpg')
        name = f'wp-{wp_id}.{ext}'
        obj.image.save(name, ContentFile(body), save=True)

    def _upsert_package(self, product, wp_id, title, description, defaults):
        slug = f'wp-{wp_id}'
        pkg, _ = Package.objects.update_or_create(
            wordpress_id=wp_id,
            defaults={
                'title': title[:200],
                'slug': slug,
                'description': html_text(description)[:5000],
                'manual_price': defaults['special_price'] or defaults['price'],
                'price': defaults['special_price'] or defaults['price'],
                'original_price': defaults['price'],
                'stock': defaults['stock'],
                'active': defaults['active'],
            },
        )
        if product.image and not pkg.image:
            pkg.image = product.image
            pkg.save(update_fields=['image'])

    def _import_pages(self):
        self.stdout.write('Importing publisher pages…')
        pages, _ = fetch_json(f'{WP_BASE}/wp-json/wp/v2/pages?per_page=100')
        by_id = {p['id']: p for p in pages}
        about = by_id.get(1996)
        if about:
            AboutUs.objects.all().delete()
            AboutUs.objects.create(text=about['content']['rendered'], is_active=True)
        coop = by_id.get(2000)
        if coop:
            CooperationInfo.objects.all().delete()
            CooperationInfo.objects.create(
                intro_text=coop['content']['rendered'],
                invitation_text=coop['content']['rendered'],
                is_active=True,
            )
        order = by_id.get(1083)
        if order:
            OrderCondition.objects.all().delete()
            OrderCondition.objects.create(text=order['content']['rendered'], is_active=True)
        contact_page = by_id.get(2)
        contact_html = contact_page['content']['rendered'] if contact_page else ''
        email_m = re.search(r'[\w.\-]+@gmail\.com', contact_html) or re.search(r'kasrapublishing@gmail\.com', contact_html)
        phone_m = re.search(r'0\d{2,3}[\-–]?\d{7,8}', html_text(contact_html))
        ContactInfo.objects.all().delete()
        ContactInfo.objects.create(
            address=html_text(contact_html)[:2000] or 'مشهد - فلسطین ۱۴ - پلاک ۱۰',
            postal_code='',
            phone=phone_m.group(0) if phone_m else '051-37670019',
            whatsapp='9891537670019',
            email=email_m.group(0) if email_m else 'kasrapublishing@gmail.com',
        )
        self.stdout.write('Publisher pages saved.')
