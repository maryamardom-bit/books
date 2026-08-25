import requests
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class SMSService:
    """Service for sending SMS via Kavenegar"""
    
    API_URL = 'https://api.kavenegar.com/v1/{}/sms/send.json'
    
    @classmethod
    def send_sms(cls, receptor, message):
        """Send SMS to a single receptor"""
        api_key = settings.KAVENEGAR_API_KEY
        sender = settings.KAVENEGAR_SENDER
        
        url = cls.API_URL.format(api_key)
        
        payload = {
            'receptor': receptor,
            'sender': sender,
            'message': message,
        }
        
        try:
            response = requests.post(url, data=payload, timeout=10)
            result = response.json()
            
            if result.get('return', {}).get('status') == 200:
                return True, _('SMS sent successfully.')
            else:
                return False, result.get('return', {}).get('message', _('Error sending SMS.'))
        except requests.exceptions.RequestException as e:
            return False, str(e)
    
    @classmethod
    def send_bulk_sms(cls, receptors, message):
        """Send SMS to multiple receptors"""
        api_key = settings.KAVENEGAR_API_KEY
        sender = settings.KAVENEGAR_SENDER
        
        url = cls.API_URL.format(api_key)
        
        receptor_str = ','.join(receptors) if isinstance(receptors, list) else receptors
        
        payload = {
            'receptor': receptor_str,
            'sender': sender,
            'message': message,
        }
        
        try:
            response = requests.post(url, data=payload, timeout=15)
            result = response.json()
            
            if result.get('return', {}).get('status') == 200:
                return True, _('SMS sent successfully.')
            else:
                return False, result.get('return', {}).get('message', _('Error sending SMS.'))
        except requests.exceptions.RequestException as e:
            return False, str(e)
    
    @classmethod
    def send_birthday_sms(cls, user, discount_code=None):
        """Send birthday SMS with discount code"""
        message = f"{_('Happy Birthday')} {user.get_full_name() or user.username}!"
        if discount_code:
            message += f"\n{_('Your discount code')}: {discount_code}"
        else:
            message += f"\n{_('Get 20% discount on your next purchase')}!"
        
        return cls.send_sms(str(user.phone_number), message)
    
    @classmethod
    def send_occasion_sms(cls, user, occasion_name, discount_code):
        """Send occasion SMS with discount code"""
        message = f"{_('Dear')} {user.get_full_name() or user.username}\n"
        message += f"{_('Happy')} {occasion_name}!\n"
        message += f"{_('Your discount code')}: {discount_code}"
        
        return cls.send_sms(str(user.phone_number), message)
    
    @classmethod
    def send_discount_code_sms(cls, user, discount_code):
        """Send discount code notification"""
        message = f"{_('Dear')} {user.get_full_name() or user.username}\n"
        message += f"{_('New discount code for you')}: {discount_code}\n"
        message += f"{_('Kasra Publishing')}"
        
        return cls.send_sms(str(user.phone_number), message)
    
    @classmethod
    def send_order_confirmation_sms(cls, user, order):
        """Send order confirmation SMS"""
        message = f"{_('Dear')} {user.get_full_name() or user.username}\n"
        message += f"{_('Your order has been registered.')}\n"
        message += f"{_('Order')}: #{order.id}\n"
        message += f"{_('Total')}: {order.total_price:,} {_('Toman')}\n"
        message += f"{_('Kasra Publishing')}"
        
        return cls.send_sms(str(user.phone_number), message)
    
    @classmethod
    def send_payment_confirmation_sms(cls, user, order):
        """Send payment confirmation SMS"""
        message = f"{_('Dear')} {user.get_full_name() or user.username}\n"
        message += f"{_('Your payment was successful.')}\n"
        message += f"{_('Order')}: #{order.id}\n"
        message += f"{_('Total')}: {order.total_price:,} {_('Toman')}\n"
        message += f"{_('Kasra Publishing')}"
        
        return cls.send_sms(str(user.phone_number), message)
    
    @classmethod
    def send_return_confirmation_sms(cls, user, order, return_request):
        """Send return confirmation SMS"""
        message = f"{_('Dear')} {user.get_full_name() or user.username}\n"
        message += f"{_('Your return request has been approved.')}\n"
        message += f"{_('Order')}: #{order.id}\n"
        message += f"{_('Amount')}: {order.total_price:,} {_('Toman')}\n"
        message += f"{_('Kasra Publishing')}"
        
        return cls.send_sms(str(user.phone_number), message)