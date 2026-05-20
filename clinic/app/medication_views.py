from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.template.loader import render_to_string
from .models import MedicationTemplate
import json


def build_hx_trigger(message, notif_type='success', duration=3500, closemodel=''):
    return json.dumps({
        'showNotification': {
            'message': message,
            'type': notif_type,
            'duration': duration,
            'closemodel': closemodel,
        }
    })


class MedicationListView(LoginRequiredMixin, View):
    """Fetch all medications and display in modal"""
    def get(self, request):
        medications = MedicationTemplate.objects.all().values('id', 'category', 'name', 'dosage', 'frequency', 'duration')
        categories = MedicationTemplate.objects.values_list('category', flat=True).distinct()
        
        context = {
            'medications': medications,
            'categories': sorted(set(categories))
        }
        return HttpResponse(render_to_string('ext/medication_list.html', context))


class MedicationCreateView(LoginRequiredMixin, View):
    """Create new medication template"""
    def post(self, request):
        try:
            data = json.loads(request.body)
            medication = MedicationTemplate.objects.create(
                category=data.get('category'),
                name=data.get('name'),
                dosage=data.get('dosage'),
                frequency=data.get('frequency'),
                duration=data.get('duration')
            )
            
            context = {'medication': medication}
            html = render_to_string('ext/medication_row.html', context)
            response = HttpResponse(html)
            response['HX-Trigger'] = build_hx_trigger('Medication added successfully', 'success', 3500, '')
            return response
        except Exception as e:
            return HttpResponse(f"<p class='text-red-500'>Error: {str(e)}</p>", status=400)


class MedicationUpdateView(LoginRequiredMixin, View):
    """Update medication template"""
    def post(self, request, pk):
        try:
            medication = get_object_or_404(MedicationTemplate, pk=pk)
            data = json.loads(request.body)
            
            medication.category = data.get('category', medication.category)
            medication.name = data.get('name', medication.name)
            medication.dosage = data.get('dosage', medication.dosage)
            medication.frequency = data.get('frequency', medication.frequency)
            medication.duration = data.get('duration', medication.duration)
            medication.save()
            
            context = {'medication': medication}
            html = render_to_string('ext/medication_row.html', context)
            response = HttpResponse(html)
            response['HX-Trigger'] = build_hx_trigger('Medication updated successfully', 'success', 3500, '')
            return response
        except Exception as e:
            return HttpResponse(f"<p class='text-red-500'>Error: {str(e)}</p>", status=400)


class MedicationDeleteView(LoginRequiredMixin, View):
    """Delete medication template"""
    def delete(self, request, pk):
        try:
            medication = get_object_or_404(MedicationTemplate, pk=pk)
            medication.delete()
            response = HttpResponse("", status=200)
            response['HX-Trigger'] = build_hx_trigger('Medication deleted successfully', 'success', 3500, '')
            return response
        except Exception as e:
            return HttpResponse(f"<p class='text-red-500'>Error: {str(e)}</p>", status=400)


class MedicationEditFormView(LoginRequiredMixin, View):
    """Load edit form for medication"""
    def get(self, request, pk):
        medication = get_object_or_404(MedicationTemplate, pk=pk)
        categories = MedicationTemplate.objects.values_list('category', flat=True).distinct()
        
        context = {
            'medication': medication,
            'categories': sorted(set(categories))
        }
        html = render_to_string('ext/medication_edit_form.html', context)
        return HttpResponse(html)


class MedicationByCategoryView(LoginRequiredMixin, View):
    """Get medications by category (for template buttons)"""
    def get(self, request):
        categories = MedicationTemplate.objects.values_list('category', flat=True).distinct()
        medications_by_category = {}
        
        for category in categories:
            medications = MedicationTemplate.objects.filter(category=category).values('id', 'name', 'dosage', 'frequency', 'duration')
            medications_by_category[category] = list(medications)
        
        return JsonResponse(medications_by_category)
