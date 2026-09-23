"""Editorial subject copy for architecture catalog — no extra models."""

from django.db.models import Count

from .models import Product

EXCLUDED_CATEGORIES = ('PACKAGES',)

CATEGORY_BLURBS = {
    Product.Category.BUSINESS: 'دفتر، مدیریت پروژه و اقتصاد ساخت',
    Product.Category.ARCH_DESIGN: 'نظریه، طراحی و فرهنگ معماری',
    Product.Category.INTERIOR: 'فضای داخلی، مبلمان و جزئیات',
    Product.Category.URBAN: 'شهر، سیاست فضا و طراحی شهری',
    Product.Category.LANDSCAPE: 'منظر، باغ و فضای باز',
    Product.Category.DESIGN_GUIDE: 'راهنماهای اجرایی و استاندارد طراحی',
    Product.Category.HISTORY: 'تاریخ، نقد و میراث معماری',
    Product.Category.DESIGN_BASICS: 'مبانی فرم، اسکیس و بیان معماری',
    Product.Category.DIGITAL: 'نرم‌افزار، بازنمایی و طراحی دیجیتال',
    Product.Category.SUSTAIN: 'پایداری، اقلیم و ساخت مسئولانه',
    Product.Category.SAMPLES: 'پروژه‌ها، نمونه‌ها و مطالعات موردی',
    Product.Category.OTHER: 'عناوین منتخب خارج از رده‌بندی اصلی',
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
            'blurb': CATEGORY_BLURBS.get(code, ''),
            'count': counts.get(code, 0),
        })
    return subjects
