import csv
import json
from datetime import timedelta
from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.views.generic import TemplateView
from django.shortcuts import render
from django.core.paginator import Paginator

from .models import InventoryItem, InventoryEvent


class InventoryPartialView(LoginRequiredMixin,TemplateView):
    template_name = 'partials/inventory.html'
    def get_dashboard_stats(self):
        """
        Helper method to calculate real-time statistics for the dashboard cards.
        """
        today = timezone.now().date()
        next_30_days = today + timedelta(days=30)

        return {
            "total_items": InventoryItem.objects.count(),
            "low_stock_count": InventoryItem.objects.filter(qty__lt=10).count(),
            "expiring_count": InventoryItem.objects.filter(expiry__lte=next_30_days).count(),
        }

    def get(self, request):
        """
        Handles the initial page load and refreshes.
        It fetches the inventory list and the dashboard statistics.
        """
        items = InventoryItem.objects.all().order_by('-id')

        # Get the calculated stats (Total, Low Stock, Expiring)
        context = self.get_dashboard_stats()

        # Add the inventory list to the context
        context["inventory_items"] = items

        return render(request, self.template_name, context)


class InventoryeditView(LoginRequiredMixin, TemplateView):
    template_name = 'ext/inventory_data.html'  # Fragment containing only the <tr> tags/inventory_table.html'  # Fragment containing only the <tr> tags

    def get(self, request):
        items = InventoryItem.objects.all().order_by('-id')
        return render(request, self.template_name, {"inventory_items": items})

    def post(self, request):

        action = request.POST.get("action")
        item_id = request.POST.get("treatment_id")
        message = ""
        close = ""

        if action == "add":
            name = request.POST.get("name")
            category = request.POST.get("category")
            qty = request.POST.get("qty")
            expiry = request.POST.get("expiry")
            notes = request.POST.get("description")

            item = InventoryItem.objects.create(
                name=name,
                category=category,
                qty=qty,
                expiry=expiry if expiry else None,
                notes=notes
            )
            
            # Log the creation event
            InventoryEvent.objects.create(
                inventory_item=item,
                event_type='CREATE',
                quantity_changed=int(qty) if qty else 0,
                previous_qty=0,
                new_qty=int(qty) if qty else 0,
                user=request.user,
                notes=f"Item created with initial quantity: {qty}"
            )
            
            message = f"Item '{name}' added successfully!"
            close = "itemModal"

        elif action == "edit" and item_id:
            item = InventoryItem.objects.get(id=item_id)
            old_qty = item.qty
            old_name = item.name
            
            item.name = request.POST.get("name")
            item.category = request.POST.get("category")
            new_qty = request.POST.get("qty")
            item.qty = new_qty
            item.expiry = request.POST.get("expiry") if request.POST.get("expiry") else None
            item.notes = request.POST.get("description")
            item.save()
            
            # Log the update event
            InventoryEvent.objects.create(
                inventory_item=item,
                event_type='UPDATE',
                quantity_changed=int(new_qty) - old_qty if new_qty else 0,
                previous_qty=old_qty,
                new_qty=int(new_qty) if new_qty else 0,
                user=request.user,
                notes=f"Item updated: quantity changed from {old_qty} to {new_qty}"
            )
            
            message = f"Item '{item.name}' updated successfully!"
            close = "itemModal"

        elif action == "delete" and item_id:
            item = InventoryItem.objects.get(id=item_id)
            name = item.name
            
            # Log the deletion event before deleting
            InventoryEvent.objects.create(
                inventory_item=item,
                event_type='DELETE',
                quantity_changed=-item.qty,
                previous_qty=item.qty,
                new_qty=0,
                user=request.user,
                notes=f"Item deleted (was {item.qty} units)"
            )
            
            item.delete()
            message = f"Item '{name}' deleted successfully!"
            close = "deleteModal"

        # Return paginated data - page 1
        all_items = InventoryItem.objects.all().order_by('-id')
        paginator = Paginator(all_items, 10)
        page_obj = paginator.get_page(1)
        
        context = {
            'page_obj': page_obj,
            'inventory_items': page_obj.object_list,
            'total_pages': paginator.num_pages,
            'is_paginated': paginator.num_pages > 1,
            'today': timezone.now().date()
        }
        
        response = render(request, 'ext/inventory_data_paginated.html', context)

        # Trigger notification and modal close in frontend
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": message,
                "type": "success",
                "duration": 4000,
                "closemodel": close
            }
        })
        return response


class InventoryPaginatedView(LoginRequiredMixin, TemplateView):
    """Handle paginated inventory data with HTMX"""
    template_name = 'ext/inventory_data_paginated.html'
    
    def get(self, request):
        
        
        page_num = request.GET.get('page', 1)
        all_items = InventoryItem.objects.all().order_by("-id")
        
        paginator = Paginator(all_items, 10)  # 10 items per page
        page_obj = paginator.get_page(page_num)
        
        context = {
            'page_obj': page_obj,
            'inventory_items': page_obj.object_list,
            'total_pages': paginator.num_pages,
            'is_paginated': paginator.num_pages > 1,
            'today': timezone.now().date()
        }
        
        return render(request, self.template_name, context)


class InventoryView(LoginRequiredMixin,TemplateView):

    def post(self, request, id, key):
        inv=InventoryItem.objects.get(id=id)
        previous_qty = inv.qty

        if key == "add":
            # add logic
            inv.qty = inv.qty + 1
            inv.save()
            
            # Log the event
            InventoryEvent.objects.create(
                inventory_item=inv,
                event_type='INCREASE',
                quantity_changed=1,
                previous_qty=previous_qty,
                new_qty=inv.qty,
                user=request.user,
                notes=f"Quantity increased from {previous_qty} to {inv.qty}"
            )

        elif key == "less":
            # delete logic
            inv.qty = inv.qty - 1
            inv.save()
            
            # Log the event
            InventoryEvent.objects.create(
                inventory_item=inv,
                event_type='DECREASE',
                quantity_changed=-1,
                previous_qty=previous_qty,
                new_qty=inv.qty,
                user=request.user,
                notes=f"Quantity decreased from {previous_qty} to {inv.qty}"
            )

        return HttpResponse()


class InventoryEventsView(LoginRequiredMixin, TemplateView):
    """
    View to fetch and display events for an inventory item.
    Returns HTML fragment showing the event history.
    """
    template_name = 'ext/inventory_events.html'

    def get(self, request, id):
        try:
            item = InventoryItem.objects.get(id=id)
            events = InventoryEvent.objects.filter(inventory_item=item)
            return render(request, self.template_name, {
                'item': item,
                'events': events
            })
        except InventoryItem.DoesNotExist:
            return HttpResponse("<p>Item not found</p>", status=404)


class InventoryExportCSVView(LoginRequiredMixin, TemplateView):
    """
    View to export the current inventory state to a CSV file.
    """
    def get(self, request):
        # Check if the request is from HTMX
        if request.headers.get('HX-Request'):
            # HTMX cannot download files directly via AJAX.
            # We send back an HX-Redirect header to the same URL.
            # The browser will then follow this as a standard request, triggering the download.
            response = HttpResponse(status=204) # No Content
            response['HX-Redirect'] = request.get_full_path()
            return response

        # Create the HttpResponse object with the appropriate CSV header for standard requests.
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="inventory_report_{timezone.now().date()}.csv"'

        writer = csv.writer(response)
        writer.writerow(['ID', 'Item Name', 'Category', 'Quantity', 'Expiry Date', 'Notes'])

        items = InventoryItem.objects.all().order_by('name')

        for item in items:
            writer.writerow([
                item.id,
                item.name,
                item.category,
                item.qty,
                item.expiry.strftime('%Y-%m-%d') if item.expiry else 'N/A',
                item.notes or ''
            ])

        return response
       
