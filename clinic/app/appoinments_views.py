from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from .models import appoinments,Doctor,Treatment
from django.core.paginator import Paginator
import json




@login_required
def get_appointment_data(request):
    # Filters and pagination for appointments list (used by AJAX/HTMX)
    qs = appoinments.objects.all().order_by('-date', '-time')

    # Query params
    q_date = request.GET.get('date', '').strip()
    doctor = request.GET.get('doctor', '').strip()
    status = request.GET.get('status', '').strip()
    treatment = request.GET.get('treatment', '').strip()
    page_number = request.GET.get('page', 1)

    if q_date:
        qs = qs.filter(date=q_date)

    if doctor and doctor.lower() != 'all':
        qs = qs.filter(doctor__icontains=doctor)

    if status and status.lower() != 'all':
        qs = qs.filter(status__iexact=status)

    if treatment and treatment.lower() != 'all':
        qs = qs.filter(treatment__icontains=treatment)

    paginator = Paginator(qs, 10)  # 10 per page
    page_obj = paginator.get_page(page_number)

    context = {
        "appoinment": page_obj.object_list,
        "page_obj": page_obj,
        "has_previous": page_obj.has_previous(),
        "has_next": page_obj.has_next(),
        "previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
        "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
        "total_count": paginator.count,
        "current_page": page_obj.number,
        "per_page": paginator.per_page,
    }

    return render(request, "ext/appointment_data.html", context)


def _appointment_calendar_data_json():
    """Generate appointment calendar data grouped by date with status counts"""
    calendar_data = {}
    appointments = appoinments.objects.all().order_by('date')
    
    for appointment in appointments:
        date_str = appointment.date.isoformat()
        if date_str not in calendar_data:
            calendar_data[date_str] = {
                'total': 0,
                'confirmed': 0,
                'pending': 0,
                'cancelled': 0
            }
        
        calendar_data[date_str]['total'] += 1
        
        status = appointment.status.lower() if appointment.status else 'pending'
        if status == 'confirmed':
            calendar_data[date_str]['confirmed'] += 1
        elif status == 'pending':
            calendar_data[date_str]['pending'] += 1
        elif status == 'cancelled':
            calendar_data[date_str]['cancelled'] += 1
    
    return json.dumps(calendar_data)


class AppointmentsPartialView(LoginRequiredMixin, TemplateView):
    
    template_name = 'partials/appointments.html'
    def get_context_data(self, **kwargs):
        doctor= Doctor.objects.all()
        self.context={"doctors": doctor,"treatment":Treatment.objects.all(), "appointment_calendar_data_json": _appointment_calendar_data_json()}
        context = super().get_context_data(**kwargs)
        context.update(self.context)
        return context

class AppointmentCreateView(LoginRequiredMixin, TemplateView):  
    def get(self, request):
        
        return TemplateView.as_view(template_name="ext/appoinmentform.html")(request)
    def post(self, request):
        patient_name = self.request.POST
        print(patient_name)
        appoinments.objects.create(
            name=patient_name.get("name"),
            doctor=patient_name.get("doctor"),
            treatment=patient_name.get("treatment"),
            date=patient_name.get("date"),
            time=patient_name.get("time"),
            notes=patient_name.get("notes"),
            status=patient_name.get("status") or "confirmed"
        ).save()
        
        
        response = get_appointment_data(self.request)
        # 🔹 Trigger Toast Notification via HX-Trigger
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"Appointment booked successfully for {patient_name['name']}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "appointmentModal"
            }
        })

        return response


class AppointmentEditView(LoginRequiredMixin, TemplateView):
    def post(self, request):
        appt_id = request.POST.get('appointment_id')
        appointment = get_object_or_404(appoinments, id=appt_id)
        # update allowed fields
        appointment.name = request.POST.get('name') or appointment.name
        appointment.treatment = request.POST.get('treatment') or appointment.treatment
        # optionally update other fields if form expands in future
        appointment.save()

        response = get_appointment_data(request)
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"Appointment updated successfully for {appointment.name}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "editModal"
            }
        })
        return response


class AppointmentDeleteView(LoginRequiredMixin, TemplateView):
    def post(self, request):
        appt_id = request.POST.get('appointment_id')
        appointment = get_object_or_404(appoinments, id=appt_id)
        name = appointment.name
        appointment.delete()

        response = get_appointment_data(request)
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"Appointment deleted successfully for {name}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "deleteModal"
            }
        })
        return response
