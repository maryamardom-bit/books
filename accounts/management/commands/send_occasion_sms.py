from django.core.management.base import BaseCommand
import jdatetime
import random
import string

from accounts.models import CustomUser
from products.models import DiscountCode
from services.sms import SMSService


class Command(BaseCommand):
    help = 'Send occasion SMS to all users'

    def handle(self, *args, **kwargs):
        today = jdatetime.date.today()
        
        # مناسبت‌ها
        occasions = {
            (1, 3): 'روز معماری',
            (7, 24): 'روز کتاب',
        }
        
        occasion = occasions.get((today.month, today.day))
        
        if not occasion:
            self.stdout.write(self.style.WARNING('No occasion today.'))
            return
        
        # ساخت کد تخفیف
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        DiscountCode.objects.create(
            code=code,
            percent=15,
            max_uses=100,
            active=True,
        )
        
        users = CustomUser.objects.filter(phone_number__isnull=False)
        
        sent_count = 0
        for user in users:
            success, message = SMSService.send_occasion_sms(user, occasion, code)
            if success:
                sent_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Total SMS sent: {sent_count}'))