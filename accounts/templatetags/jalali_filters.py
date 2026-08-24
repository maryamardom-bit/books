from django import template
import jdatetime

register = template.Library()

@register.filter
def jalali_text(value):
    """تبدیل تاریخ شمسی 1370/05/24 به ۲۴ اردیبهشت ۱۳۷۰"""
    if not value:
        return ''
    
    try:
        parts = str(value).replace('-', '/').split('/')
        if len(parts) == 3:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            
            month_names = {
                1: 'فروردین',
                2: 'اردیبهشت',
                3: 'خرداد',
                4: 'تیر',
                5: 'مرداد',
                6: 'شهریور',
                7: 'مهر',
                8: 'آبان',
                9: 'آذر',
                10: 'دی',
                11: 'بهمن',
                12: 'اسفند',
            }
            
            # تبدیل اعداد به فارسی
            persian_digits = '۰۱۲۳۴۵۶۷۸۹'
            english_digits = '0123456789'
            translation = str.maketrans(english_digits, persian_digits)
            
            day_fa = str(day).translate(translation)
            year_fa = str(year).translate(translation)
            
            return f'{day_fa} {month_names[month]} {year_fa}'
    except:
        pass
    
    return value