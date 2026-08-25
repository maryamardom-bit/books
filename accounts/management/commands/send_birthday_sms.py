from django.core.management.base import BaseCommand
from django.utils import timezone
import jdatetime

from accounts.models import CustomUser
from products.models import DiscountCode
from services.sms import SMSService


class Command(BaseCommand):
    help = 'Send birthday SMS to users whose birthday is today'

    def handle(self, *args, **kwargs):
        today = jdatetime.date.today()
        
        users = CustomUser.objects.filter(birth_date__isnull=False)
        
        sent_count = 0
        for user in users:
            try:
                parts = str(user.birth_date).split('/')
                if len(parts) == 3:
                    birth_month = int(parts[1])
                    birth_day = int(parts[2])
                    
                    if birth_month == today.month and birth_day == today.day:
                        # ساخت کد تخفیف ۲۰٪
                        import random
                        import string
                        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                        
                        DiscountCode.objects.create(
                            code=code,
                            percent=20,
                            max_uses=1,
                            active=True,
                        )
                        
                        success, message = SMSService.send_birthday_sms(user, code)
                        
                        if success:
                            sent_count += 1
                            self.stdout.write(self.style.SUCCESS(f'Sent to {user.username}'))
                        else:
                            self.stdout.write(self.style.ERROR(f'Failed for {user.username}: {message}'))
            except:
                continue
        
        self.stdout.write(self.style.SUCCESS(f'Total SMS sent: {sent_count}'))