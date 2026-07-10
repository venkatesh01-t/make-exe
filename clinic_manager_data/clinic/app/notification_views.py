from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from .models import appoinments, InventoryItem

def get_notification_data():
    today = timezone.now().date()
    thirty_days_from_now = today + timedelta(days=30)
    
    # Today's Appointments
    today_appointments = appoinments.objects.filter(date=today).order_by('time')
    
    # Low Stock Items
    low_stock_items = InventoryItem.objects.filter(qty__lt=10).order_by('qty')
    
    # Expiring Items
    expiring_items = InventoryItem.objects.filter(expiry__lte=thirty_days_from_now).exclude(expiry__isnull=True).order_by('expiry')
    
    # Calculate total notification count
    total_count = today_appointments.count() + low_stock_items.count() + expiring_items.count()
    
    return {
        'today_appointments': today_appointments,
        'low_stock_items': low_stock_items,
        'expiring_items': expiring_items,
        'total_count': total_count
    }

def notifications_dropdown(request):
    data = get_notification_data()
    # Limit for dropdown: show max 5 combined
    return render(request, 'partials/notifications_dropdown.html', data)

def all_notifications_modal(request):
    data = get_notification_data()
    return render(request, 'ext/notifications/all_notifications_modal.html', data)
