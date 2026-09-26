"""Editorial subject copy for architecture catalog — no extra models."""

from django.db.models import Count
from django.utils.translation import gettext_lazy as _

from .models import Product

EXCLUDED_CATEGORIES = ('PACKAGES',)

CATEGORY_BLURBS = {
    Product.Category.BUSINESS: _('Practice, project management, and the economics of building'),
    Product.Category.ARCH_DESIGN: _('Theory, design, and architectural culture'),
    Product.Category.INTERIOR: _('Interiors, furniture, and detail'),
    Product.Category.URBAN: _('The city, spatial policy, and urban design'),
    Product.Category.LANDSCAPE: _('Landscape, gardens, and open space'),
    Product.Category.DESIGN_GUIDE: _('Practice guides and design standards'),
    Product.Category.HISTORY: _('History, criticism, and architectural heritage'),
    Product.Category.DESIGN_BASICS: _('Form, sketching, and architectural representation'),
    Product.Category.DIGITAL: _('Software, representation, and digital design'),
    Product.Category.SUSTAIN: _('Sustainability, climate, and responsible construction'),
    Product.Category.SAMPLES: _('Projects, precedents, and case studies'),
    Product.Category.OTHER: _('Selected titles outside the main classification'),
}

# Source strings for Rosetta. Empty Persian msgstr keeps the English title
# until it is translated.
CATEGORY_ENGLISH = {
    Product.Category.BUSINESS: _('Architecture Business'),
    Product.Category.ARCH_DESIGN: _('Architecture & Design'),
    Product.Category.INTERIOR: _('Interior Architecture'),
    Product.Category.URBAN: _('Urban Design'),
    Product.Category.LANDSCAPE: _('Landscape'),
    Product.Category.DESIGN_GUIDE: _('Design Guides'),
    Product.Category.HISTORY: _('Architectural History'),
    Product.Category.DESIGN_BASICS: _('Design Fundamentals'),
    Product.Category.DIGITAL: _('Digital Design'),
    Product.Category.SUSTAIN: _('Sustainability'),
    Product.Category.SAMPLES: _('Case Studies'),
    Product.Category.OTHER: _('Other'),
}


def catalog_subjects():
    counts = dict(
        Product.objects.filter(active=True)
        .exclude(category__in=EXCLUDED_CATEGORIES)
        .values_list('category')
        .annotate(n=Count('id'))
    )
    subjects = []
    for code, name in Product.Category.choices:
        if code in EXCLUDED_CATEGORIES:
            continue
        subjects.append({
            'code': code,
            'name': str(name),
            'english': CATEGORY_ENGLISH.get(code, ''),
            'blurb': CATEGORY_BLURBS.get(code, ''),
            'count': counts.get(code, 0),
        })
    return subjects
