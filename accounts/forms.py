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