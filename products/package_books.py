"""Link the books named inside a package description."""
import html
import re
from urllib.parse import parse_qs, unquote, urlsplit

from products.models import Package, Product

_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_ANCHOR_RE = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.I | re.S)
_HREF_RE = re.compile(r"""href=["']([^"']+)["']""", re.I)
_TAG_RE = re.compile(r"<[^>]+>")


def _normalize(value):
    text = html.unescape(unquote(value or "")).translate(_DIGIT_TRANSLATION)
    text = text.replace("\u200c", "").replace("\u200d", "")
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه")
    return re.sub(r"[^\w]+", "", text, flags=re.UNICODE).lower()


def _slug(href):
    parts = urlsplit(html.unescape(href or ""))
    query = parse_qs(parts.query)
    if query.get("product"):
        return unquote(query["product"][0])
    path = unquote(parts.path)
    marker = "/product/"
    if marker in path:
        return path.split(marker, 1)[1].strip("/")
    return ""


def _anchor_label(inner_html):
    text = _TAG_RE.sub("", inner_html or "")
    return html.unescape(text).replace("\xa0", " ").strip(" »«\n\t")


def _pick(candidates):
    if not candidates:
        return None
    titles = {_normalize(product.title) for product in candidates}
    if len(titles) > 1:
        return None
    active = [product for product in candidates if product.active]
    pool = active or candidates
    return min(pool, key=lambda product: product.pk)


def _match_key(catalog, key):
    if len(key) < 2:
        return None
    exact = [product for product in catalog if _normalize(product.title) == key]
    if exact:
        return _pick(exact)
    if len(key) < 6:
        return None
    prefix = []
    for product in catalog:
        other = _normalize(product.title)
        shorter, longer = (key, other) if len(key) <= len(other) else (other, key)
        if len(shorter) >= 6 and longer.startswith(shorter):
            prefix.append(product)
    return _pick(prefix)


def books_in_html(source, catalog):
    """Return catalog books referenced by product links, in link order."""
    found = []
    seen = set()
    for attrs, inner in _ANCHOR_RE.findall(source or ""):
        href_match = _HREF_RE.search(attrs)
        if not href_match or "product" not in href_match.group(1):
            continue
        href = href_match.group(1)
        product = _match_key(catalog, _normalize(_anchor_label(inner)))
        if product is None:
            product = _match_key(catalog, _normalize(_slug(href)))
        if product is None or product.pk in seen:
            continue
        seen.add(product.pk)
        found.append(product)
    return found


def assign_package_books(package, html_source=None, catalog=None):
    """Attach books named in the description without recalculating the package price."""
    if catalog is None:
        catalog = list(Product.objects.exclude(category=Product.Category.PACKAGES))
    found = []
    seen = set()
    for source in (package.description, html_source):
        for product in books_in_html(source, catalog):
            if product.pk not in seen:
                seen.add(product.pk)
                found.append(product)
    if not found or not package.pk:
        return found
    through = Package.products.through
    existing = set(
        through.objects.filter(package_id=package.pk).values_list("product_id", flat=True)
    )
    through.objects.bulk_create(
        [
            through(package_id=package.pk, product_id=product.pk)
            for product in found
            if product.pk not in existing
        ]
    )
    return found


def assign_all_packages():
    catalog = list(Product.objects.exclude(category=Product.Category.PACKAGES))
    linked = 0
    for package in Package.objects.all():
        before = package.products.count()
        assign_package_books(package, catalog=catalog)
        linked += max(package.products.count() - before, 0)
    return linked
