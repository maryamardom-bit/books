import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('orders', '0008_order_status_orderitem_title_protect'),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gateway', models.CharField(max_length=30, verbose_name='gateway')),
                ('reference', models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='reference')),
                ('amount', models.BigIntegerField(verbose_name='amount')),
                ('status', models.CharField(
                    choices=[
                        ('INITIATED', 'Initiated'),
                        ('PENDING', 'Pending at gateway'),
                        ('PAID', 'Paid'),
                        ('FAILED', 'Failed'),
                        ('CANCELLED', 'Cancelled'),
                    ],
                    db_index=True,
                    default='INITIATED',
                    max_length=20,
                    verbose_name='status',
                )),
                ('token', models.CharField(blank=True, max_length=255, verbose_name='token')),
                ('transaction_id', models.CharField(blank=True, max_length=100, null=True, verbose_name='transaction id')),
                ('rrn', models.CharField(blank=True, max_length=50, verbose_name='RRN')),
                ('trace_no', models.CharField(blank=True, max_length=50, verbose_name='trace number')),
                ('card_mask', models.CharField(blank=True, max_length=32, verbose_name='card')),
                ('failure_reason', models.CharField(blank=True, max_length=255, verbose_name='failure reason')),
                ('callback_payload', models.JSONField(blank=True, default=dict, verbose_name='callback payload')),
                ('verify_payload', models.JSONField(blank=True, default=dict, verbose_name='verify payload')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='created')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated')),
                ('paid_at', models.DateTimeField(blank=True, null=True, verbose_name='paid at')),
                ('order', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='payments',
                    to='orders.order',
                    verbose_name='order',
                )),
            ],
            options={
                'verbose_name': 'payment',
                'verbose_name_plural': 'payments',
                'ordering': ['-created_at'],
                'constraints': [
                    models.UniqueConstraint(
                        condition=models.Q(transaction_id__isnull=False),
                        fields=('gateway', 'transaction_id'),
                        name='payment_unique_gateway_transaction',
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(status='PAID'),
                        fields=('order',),
                        name='payment_one_paid_per_order',
                    ),
                ],
            },
        ),
    ]
