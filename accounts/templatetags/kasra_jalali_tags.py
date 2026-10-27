from django import template
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
import jdatetime
from django.utils import timezone

register = template.Library()


def jalali_month_names():
    return [
        _('Farvardin'), _('Ordibehesht'), _('Khordad'),
        _('Tir'), _('Mordad'), _('Shahrivar'),
        _('Mehr'), _('Aban'), _('Azar'),
        _('Dey'), _('Bahman'), _('Esfand'),
    ]


@register.filter(name='jalali_date')
def jalali_date(value):
    """Convert datetime to Jalali date string"""
    if not value:
        return ''
    
    if hasattr(value, 'year'):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        
        j_date = jdatetime.datetime.fromgregorian(datetime=value)
        return j_date.strftime('%Y/%m/%d')
    
    return value


@register.filter(name='jalali_datetime')
def jalali_datetime(value):
    """Convert datetime to Jalali datetime string"""
    if not value:
        return ''
    
    if hasattr(value, 'year'):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        
        j_date = jdatetime.datetime.fromgregorian(datetime=value)
        return j_date.strftime('%Y/%m/%d - %H:%M')
    
    return value


@register.filter(name='jalali_date_humanize')
def jalali_date_humanize(value):
    """Convert datetime to humanized Jalali date"""
    if not value:
        return ''
    
    if hasattr(value, 'year'):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        
        now = timezone.localtime(timezone.now())
        j_now = jdatetime.datetime.fromgregorian(datetime=now)
        j_value = jdatetime.datetime.fromgregorian(datetime=value)
        
        diff = j_now - j_value
        
        if diff.days == 0:
            return _('Today')
        elif diff.days == 1:
            return _('Yesterday')
        elif diff.days < 7:
            return ngettext('%(count)s day ago', '%(count)s days ago', diff.days) % {'count': diff.days}
        elif diff.days < 30:
            weeks = diff.days // 7
            return ngettext('%(count)s week ago', '%(count)s weeks ago', weeks) % {'count': weeks}
        else:
            return j_value.strftime('%Y/%m/%d')
    
    return value


@register.filter(name='jalali_text')
def jalali_text(value):
    """Convert datetime to Jalali text format"""
    if not value:
        return ''
    
    if hasattr(value, 'year'):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        
        j_date = jdatetime.datetime.fromgregorian(datetime=value)
        
        month_name = jalali_month_names()[j_date.month - 1]
        return f'{j_date.day} {month_name} {j_date.year}'
    
    return value


@register.filter(name='jalali_text_datetime')
def jalali_text_datetime(value):
    """Convert datetime to Jalali text with time"""
    if not value:
        return ''
    
    if hasattr(value, 'year'):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        
        j_date = jdatetime.datetime.fromgregorian(datetime=value)
        
        month_name = jalali_month_names()[j_date.month - 1]
        return f'{j_date.day} {month_name} {j_date.year} - {j_date.hour:02d}:{j_date.minute:02d}'
    
    return value


@register.filter(name='to_jalali')
def to_jalali(value, format_str=None):
    """
    Convert datetime to Jalali date string.
    If format_str is provided, use it. Otherwise use default format.
    """
    if not value:
        return ''
    
    if hasattr(value, 'year'):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        
        j_date = jdatetime.datetime.fromgregorian(datetime=value)
        
        if format_str:
            return j_date.strftime(format_str)
        else:
            return j_date.strftime('%Y/%m/%d')
    
    return value


@register.filter(name='to_jalali_datetime')
def to_jalali_datetime(value, format_str=None):
    """Convert datetime to Jalali datetime string"""
    if not value:
        return ''
    
    if hasattr(value, 'year'):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        
        j_date = jdatetime.datetime.fromgregorian(datetime=value)
        
        if format_str:
            return j_date.strftime(format_str)
        else:
            return j_date.strftime('%Y/%m/%d - %H:%M')
    
    return value


@register.filter(name='to_jalali_text')
def to_jalali_text(value):
    """Convert datetime to Jalali text format"""
    if not value:
        return ''
    
    if hasattr(value, 'year'):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        
        j_date = jdatetime.datetime.fromgregorian(datetime=value)
        
        month_name = jalali_month_names()[j_date.month - 1]
        return f'{j_date.day} {month_name} {j_date.year}'
    
    return value