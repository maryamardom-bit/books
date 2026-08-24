from django import forms
from django.utils.html import format_html


class CustomJalaliDateTimeWidget(forms.TextInput):
    """
    ویجت سفارشی برای تاریخ/زمان شمسی با تقویم پاپ‌آپ
    بدون نیاز به فایل template
    """
    
    class Media:
        css = {
            'all': ('admin/css/custom_jalali_datepicker.css',)
        }
        js = ('admin/js/custom_jalali_datepicker.js',)
    
    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'form-control custom-jalali-datetime-input',
            'dir': 'ltr',
            'autocomplete': 'off',
            'readonly': 'readonly',
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)
    
    def render(self, name, value, attrs=None, renderer=None):
        """رندر مستقیم HTML بدون نیاز به template"""
        if value is None:
            value = ''
        
        # ساخت id یکتا
        if attrs and 'id' in attrs:
            input_id = attrs['id']
        else:
            input_id = f'id_{name}'
        
        return format_html(
            '''
            <div class="custom-datetime-wrapper" style="position: relative; width: 100%;">
                <input type="text" 
                       name="{name}" 
                       value="{value}" 
                       id="{input_id}" 
                       class="form-control custom-jalali-datetime-input" 
                       dir="ltr" 
                       readonly
                       style="cursor: pointer; background: #fff; padding-left: 35px;">
                <span onclick="toggleCustomCalendar(event, '{input_id}')" 
                      style="position:absolute; left:10px; top:50%; transform:translateY(-50%); cursor:pointer; font-size:16px;">
                    📅
                </span>
                <div class="custom-jalali-calendar" 
                     id="calendar-{input_id}" 
                     style="display:none; position:absolute; top:45px; right:0; background:#fff; 
                            border:1px solid #ddd; border-radius:10px; box-shadow:0 5px 25px rgba(0,0,0,0.15); 
                            z-index:9999; padding:15px; width:300px;">
                </div>
            </div>
            ''',
            name=name,
            value=value,
            input_id=input_id,
        )