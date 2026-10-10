from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    OrderItem = apps.get_model('orders', 'OrderItem')
    Order.objects.filter(is_paid=True).update(status='PAID')
    for item in OrderItem.objects.filter(title='').select_related('product', 'package').iterator():
        source = item.product or item.package
        if source is not None:
            item.title = source.title[:255]
            item.save(update_fields=['title'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('products', '0012_wordpress_full_import'),
        ('orders', '0007_order_total_bigint'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('DRAFT', 'Draft'),
                    ('PENDING_PAYMENT', 'Pending payment'),
                    ('PAYMENT_FAILED', 'Payment failed'),
                    ('PAID', 'Paid'),
                    ('PROCESSING', 'Processing'),
                    ('PACKED', 'Packed'),
                    ('SHIPPED', 'Shipped'),
                    ('DELIVERED', 'Delivered'),
                    ('CANCELLED', 'Cancelled'),
                    ('RETURN_REQUESTED', 'Return requested'),
                    ('RETURNED', 'Returned'),
                    ('REFUNDED', 'Refunded'),
                ],
                db_index=True,
                default='PENDING_PAYMENT',
                max_length=20,
                verbose_name='status',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='discount_code',
            field=models.CharField(blank=True, max_length=50, verbose_name='discount code'),
        ),
        migrations.AlterField(
            model_name='order',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to=settings.AUTH_USER_MODEL,
                verbose_name='user',
            ),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='title',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='title'),
        ),
        migrations.AlterField(
            model_name='orderitem',
            name='product',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='order_items',
                to='products.product',
            ),
        ),
        migrations.AlterField(
            model_name='orderitem',
            name='package',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='order_items',
                to='products.package',
            ),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
