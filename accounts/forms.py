from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from django import forms
from django.utils.translation import gettext_lazy as _


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


class ProfileEditForm(forms.ModelForm):
    """Profile edit form"""
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'birth_date', 'address', 'postal_code']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'first_name': _('first name'),
            'last_name': _('last name'),
            'email': _('email'),
            'phone_number': _('phone number'),
            'birth_date': _('birth date'),
            'address': _('address'),
            'postal_code': _('postal code'),
        }