import re
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Order
from pages.models import SitePage
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

    def handle(self, *args, **options):
        folder = Path(options['dir'])
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
        orders_xml = folder / 'shop_order.xml'
        if orders_xml.exists() and not options['skip_orders']:
            self._import_orders(orders_xml)
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
        created = 0
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
            DiscountCode.objects.update_or_create(
                code=code,
                defaults={
                    'percent': min(percent, 100),
                    'amount': max(amount, 0),
                    'max_uses': max_uses,
                    'used_count': used,
                    'active': status == 'publish',
                    'valid_until': valid_until,
                },
            )
            created += 1
            elem.clear()
        self.stdout.write(f'Coupons imported: {created}')

    def _import_orders(self, path):
        created = updated = 0
        for _, elem in ET.iterparse(path, events=('end',)):
            if elem.tag != 'item':
                continue
            post_type = _text(elem.find('wp:post_type', NS))
            if post_type and post_type != 'shop_order':
                elem.clear()
                continue
            wp_id = int(_text(elem.find('wp:post_id', NS)) or 0)
            if not wp_id:
                elem.clear()
                continue
            metas = {
                _text(m.find('wp:meta_key', NS)): _text(m.find('wp:meta_value', NS))
                for m in elem.findall('wp:postmeta', NS)
            }
            status = _text(elem.find('wp:status', NS))
            email = metas.get('_billing_email') or ''
            first = (metas.get('_billing_first_name') or '')[:100]
            last = (metas.get('_billing_last_name') or '')[:100]
            phone = re.sub(r'\D', '', metas.get('_billing_phone') or '')[:15]
            address_parts = [
                metas.get('_billing_address_1') or '',
                metas.get('_billing_address_2') or '',
                metas.get('_billing_city') or '',
                metas.get('_billing_state') or '',
                metas.get('_billing_postcode') or '',
            ]
            address = '، '.join(p for p in address_parts if p)[:700]
            notes = []
            for comment in elem.findall('wp:comment', NS):
                content = unescape(_text(comment.find('wp:comment_content', NS))).strip()
                if content:
                    notes.append(re.sub(r'<[^>]+>', ' ', content))
            try:
                total = int(float(metas.get('_order_total') or 0))
            except ValueError:
                total = 0
            total = max(total, 0)
            user = self._ensure_user(
                email=email,
                login=email.split('@')[0] if email else f'order-{wp_id}',
                wp_id=int(metas.get('_customer_user') or 0),
                first=first,
                last=last,
                phone=phone,
                address=address,
            )
            paid = status in ('wc-completed', 'wc-refunded', 'wc-processing')
            method = metas.get('_payment_method') or 'online'
            payment_method = 'online' if 'install' not in method else 'installment'
            defaults = {
                'user': user,
                'is_paid': paid,
                'first_name': first or user.first_name or '—',
                'last_name': last or user.last_name or '—',
                'phone_number': phone or '00000000000',
                'address': address or '—',
                'order_notes': '\n'.join(notes)[:700],
                'total_price': max(total, 0),
                'payment_method': payment_method,
            }
            try:
                obj, was_new = Order.objects.update_or_create(wordpress_id=wp_id, defaults=defaults)
            except Exception as exc:
                self.stderr.write(f'  ! order {wp_id}: {exc}')
                elem.clear()
                continue
            created_at = parse_dt(_text(elem.find('wp:post_date', NS)))
            Order.objects.filter(pk=obj.pk).update(datetime_created=created_at)
            created += int(was_new)
            updated += int(not was_new)
            if (created + updated) % 500 == 0:
                self.stdout.write(f'  orders {created + updated}')
            elem.clear()
        self.stdout.write(f'Orders imported: new={created} updated={updated}')
