from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from orders.models import Order
from products.models import TieredDiscount
from .forms import ProfileEditForm


@login_required
def dashboard_view(request):
    user = request.user
    orders = Order.objects.filter(user=user).order_by('-datetime_created')[:10]
    tiered = TieredDiscount.objects.get_or_create(user=user)[0]

    context = {
        'orders': orders,
        'tiered': tiered,
        'tier_percent': tiered.get_discount_percent(),
        'next_tier': tiered.current_tier + 1 if tiered.current_tier < 3 else None,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def profile_edit_view(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, _('Profile updated successfully.'))
            return redirect('accounts:dashboard')
    else:
        form = ProfileEditForm(instance=user)

    return render(request, 'accounts/profile_edit.html', {'form': form})


@login_required
def order_history_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-datetime_created')
    return render(request, 'accounts/order_history.html', {'orders': orders})