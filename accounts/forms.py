from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
import jdatetime


# =============================================
# فرم‌های ادمین (باید وجود داشته باشند)
# =============================================
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'phone_number')
        labels = {
            'username': _('username'),
            'email': _('email'),
            'phone_number': _('phone number'),
        }


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
        labels = {
            'username': _('username'),
            'email': _('email'),
            'phone_number': _('phone number'),
            'first_name': _('first name'),
            'last_name': _('last name'),
        }


# =============================================
# فرم ویرایش پروفایل کاربر
# =============================================
class ProfileEditForm(forms.ModelForm):
    birth_date = forms.CharField(
        label=_('birth date'),
        required=False,
        widget=forms.TextInput(attrs={
            'id': 'birth-date-input',
            'placeholder': _('Select a date'),
            'autocomplete': 'off',
            'readonly': 'readonly',
            'class': 'cursor-pointer',
        }),
    )

    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'birth_date', 'address', 'postal_code']
        widgets = {
            'first_name': forms.TextInput(),
            'last_name': forms.TextInput(),
            'email': forms.EmailInput(),
            'phone_number': forms.TextInput(attrs={'dir': 'ltr'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'postal_code': forms.TextInput(attrs={'dir': 'ltr'}),
        }
        labels = {
            'first_name': _('first name'),
            'last_name': _('last name'),
            'email': _('email'),
            'phone_number': _('phone number'),
            'address': _('address'),
            'postal_code': _('postal code'),
        }

    def clean_birth_date(self):
        value = self.cleaned_data.get('birth_date', '')
        if not value:
            return value
        try:
            parts = value.split('/')
            if len(parts) != 3:
                raise forms.ValidationError(_('Invalid date format'))
            year, month, day = map(int, parts)
            date = jdatetime.date(year, month, day)
            today = jdatetime.date.today()
            if date > today:
                raise forms.ValidationError(_('Future date is not allowed.'))
            if today.year - year > 120:
                raise forms.ValidationError(_('Age cannot be more than 120 years.'))
            return date.strftime('%Y/%m/%d')
        except forms.ValidationError:
            raise
        except Exception:
            raise forms.ValidationError(_('Invalid date'))