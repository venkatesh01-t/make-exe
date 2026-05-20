import csv
import io
import json
import os
from django.urls import reverse
from django.conf import settings
import cv2
import numpy as np
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.generic import TemplateView

from .models import BillingInvoice, ClinicInformation, DailyPatient, Doctor, InventoryItem, Patient, Treatment, appoinments

User = get_user_model()




class SettingsPartialView(LoginRequiredMixin, TemplateView):
    template_name = 'partials/settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        clinic = ClinicInformation.objects.first()
        
        if not clinic:
            # create a temporary unsaved instance so template access won't blow up
            clinic = ClinicInformation(reg_no="")
        context['clinic'] = clinic
        context['users'] = User.objects.all()
        context['doctors'] = Doctor.objects.all()
        return context

class UserCreateView(LoginRequiredMixin, TemplateView):
    def get(self, request):
        return TemplateView.as_view(template_name="ext/user_form.html")(request)

    def post(self, request):
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        is_staff = request.POST.get("is_staff") == "on"
        is_active = request.POST.get("is_active") == "on"
        phonenumber = request.POST.get("phonenumber")
        role = request.POST.get("role")
        doctor_id = request.POST.get("doctor_id")

        user = User.objects.create(
            username=username,
            email=email,
            is_staff=is_staff,
            is_active=is_active,
            phone_number=phonenumber,
            custom_permissions=role
        )
        
        # Assign doctor if role is doctor and doctor_id is provided
        if role == "doctor" and doctor_id:
            try:
                doctor = Doctor.objects.get(id=doctor_id)
                user.doctor = doctor
            except Doctor.DoesNotExist:
                pass
        
        if password:
            user.set_password(password)
            user.save()
        else:
            user.save()


        response =get_users_table_body(request)
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"User created successfully for {user.username}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "userModal"

            }
        })

        return response


class UserEditView(LoginRequiredMixin, TemplateView):
    def get(self, request, pk):
        print(pk)
        user = get_object_or_404(User, pk=pk)
        response = render(request, "ext/user_form.html", {
            "user": user,
            "doctors": Doctor.objects.all()
        })
        return response
    def post(self, request, pk):
        print("edit",pk)
        user = get_object_or_404(User, pk=pk)
        user.username = request.POST.get("username")
        user.email = request.POST.get("email")
        user.is_staff = request.POST.get("is_staff") == "on"
        user.is_active = request.POST.get("is_active") == "on"
        password = request.POST.get("password")
        phonenumber = request.POST.get("phonenumber")
        role = request.POST.get("role")
        doctor_id = request.POST.get("doctor_id")
        user.phone_number = phonenumber
        user.custom_permissions = role
        
        # Handle doctor assignment
        if role == "doctor" and doctor_id:
            try:
                doctor = Doctor.objects.get(id=doctor_id)
                user.doctor = doctor
            except Doctor.DoesNotExist:
                user.doctor = None
        else:
            user.doctor = None
        
        if password:
            user.set_password(password)

        user.save()
        response = get_users_table_body(request)
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"User updated successfully for {user.username}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "userModaledit"
            }
        })
        response["HX-Target"] = request.POST.get("hx_target", "#users-table-body")
        response["HX-Swap"] = "innerHTML"
        response["HX-Redirect"] = reverse("clinic:htmx_login")
        return response

def get_users_table_body(request):
    content={"users": User.objects.all(),
             "doctor": Doctor.objects.all()}
    return render(request, "ext/user_data.html", content)


class UserDeleteView(LoginRequiredMixin, TemplateView):
    def post(self, request):
        user_id = request.POST.get("user_id")
        user = get_object_or_404(User, pk=user_id)
        username = user.username
        user.delete()

        response = get_users_table_body(request)
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"User deleted successfully for {username}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "deleteUserModal"
            }
        })
        response["HX-Target"] = "#users-table-body"
        response["HX-Swap"] = "innerHTML"
        return response


def get_doctors_json(request):
    """Fetch all doctors as JSON for the user form doctor selection."""
    doctors = Doctor.objects.all().values('id', 'name', 'specialization', 'experience')
    return JsonResponse(list(doctors), safe=False)


class ClinicInfoView(LoginRequiredMixin, TemplateView):
    """HTMX endpoint for creating/updating clinic details and logo processing."""
    def post(self, request):
        # grab form data
        reg_no = request.POST.get('reg_no', '').strip()
        clinic_name = request.POST.get('clinic_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        address = request.POST.get('address', '').strip()
        open_time = request.POST.get('open_time')
        close_time = request.POST.get('close_time')
        doctor_name = request.POST.get('doctor_name', '').strip()
        doctor_specialist = request.POST.get('doctor_specialist', '').strip()

        # Get existing clinic or create new one
        # Try to get the first clinic (should only be one)
        clinic = ClinicInformation.objects.first()

        if not clinic:
            # First time: create new clinic record
            clinic = ClinicInformation(reg_no=reg_no)
        else:
            # Subsequent times: update existing clinic
            if reg_no:
                clinic.reg_no = reg_no

        # Update all fields
        if clinic_name:
            clinic.clinic_name = clinic_name
        if phone:
            clinic.phone = phone
        if email:
            clinic.email = email
        if address:
            clinic.address = address
        if open_time:
            clinic.open_time = open_time
        if close_time:
            clinic.close_time = close_time
        if doctor_name:
            clinic.doctor_name = doctor_name
        if doctor_specialist:
            clinic.doctor_specialist = doctor_specialist

        # Handle logo upload (save directly to clinic without backup)
        image_file = request.FILES.get('logo')
        if image_file:
            # --- 1. Read uploaded image into OpenCV ---
            # Convert Django InMemoryUploadedFile to NumPy array
            file_bytes = np.frombuffer(image_file.read(), np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)  # BGR format

            # --- 2. Convert to grayscale ---
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # --- 3. Create mask (detect white background) ---
            _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

            # --- 4. Add alpha channel ---
            b, g, r = cv2.split(img)
            alpha = mask
            rgba = cv2.merge([b, g, r, alpha])  # BGRA

            # --- 5. Encode as PNG in memory ---
            success, png_data = cv2.imencode('.png', rgba)
            if success:
                # --- 6. Save to model field ---
                clinic.logo.save(
                    f"clinic_logo_{clinic.id}.png",
                    ContentFile(png_data.tobytes()),
                    save=False
                )

            # --- 7. Save the clinic object ---
        clinic.save()

        response = HttpResponse()
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": "Clinic information saved successfully!",
                "type": "success",
                "duration": 3000
            }
        })
        return response


class SettingsExportCSVView(LoginRequiredMixin, TemplateView):
    csv_headers = [
        'model',
        'record_id',
        'name',
        'secondary',
        'tertiary',
        'date',
        'status',
        'amount',
        'notes',
        'details_json',
    ]

    def _csv_response(self, request):
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Redirect'] = request.get_full_path()
            return response

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(self.csv_headers)

        self._write_patient_rows(writer)
        self._write_daily_patient_rows(writer)
        self._write_appointment_rows(writer)
        self._write_billing_rows(writer)
        self._write_doctor_rows(writer)
        self._write_treatment_rows(writer)
        self._write_inventory_rows(writer)
        self._write_clinic_rows(writer)

        response = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="clinic_records_{timezone.now().date()}.csv"'
        return response

    def _write_row(self, writer, model_name, record_id, name='', secondary='', tertiary='', record_date='', status='', amount='', notes='', details=None):
        writer.writerow([
            model_name,
            record_id,
            name,
            secondary,
            tertiary,
            record_date,
            status,
            amount,
            notes,
            json.dumps(details or {}, default=str, ensure_ascii=False),
        ])

    def _write_patient_rows(self, writer):
        for patient in Patient.objects.all().order_by('id'):
            self._write_row(
                writer,
                'Patient',
                patient.id,
                name=f'{patient.first_name} {patient.last_name or ""}'.strip(),
                secondary=patient.phone,
                tertiary=patient.email,
                record_date=patient.last_visit.isoformat() if patient.last_visit else '',
                status=patient.status or '',
                notes=patient.medical_history or '',
                details={
                    'age': patient.age,
                    'gender': patient.gender,
                    'previous_visits': patient.previous_visits,
                    'created_at': patient.created_at,
                },
            )

    def _write_daily_patient_rows(self, writer):
        for daily_patient in DailyPatient.objects.select_related('patient').all().order_by('id'):
            self._write_row(
                writer,
                'DailyPatient',
                daily_patient.id,
                name=daily_patient.name or str(daily_patient.patient),
                secondary=daily_patient.doctor or '',
                tertiary=daily_patient.complaint or '',
                record_date=daily_patient.date.isoformat() if daily_patient.date else '',
                status=daily_patient.status or '',
                notes=daily_patient.treatments or '',
                details={
                    'patient_id': daily_patient.patient_id,
                    'created_at': daily_patient.created_at,
                },
            )

    def _write_appointment_rows(self, writer):
        for appointment in appoinments.objects.all().order_by('id'):
            self._write_row(
                writer,
                'Appointment',
                appointment.id,
                name=appointment.name or '',
                secondary=appointment.doctor or '',
                tertiary=appointment.treatment or '',
                record_date=appointment.date.isoformat() if appointment.date else '',
                status=appointment.status or '',
                notes=appointment.notes or '',
                details={
                    'time': appointment.time,
                    'created_at': appointment.created_at,
                    'updated_at': appointment.updated_at,
                },
            )

    def _write_billing_rows(self, writer):
        for invoice in BillingInvoice.objects.select_related('patient', 'daily_patient').all().order_by('id'):
            self._write_row(
                writer,
                'BillingInvoice',
                invoice.id,
                name=str(invoice.patient),
                secondary=invoice.doctor or '',
                tertiary=invoice.treatment or '',
                record_date=invoice.bill_date.isoformat() if invoice.bill_date else '',
                status=invoice.status or '',
                amount=str(invoice.amount),
                notes=invoice.note or '',
                details={
                    'invoice_number': invoice.invoice_number,
                    'daily_patient_id': invoice.daily_patient_id,
                    'paid_at': invoice.paid_at,
                    'created_at': invoice.created_at,
                    'updated_at': invoice.updated_at,
                },
            )

    def _write_doctor_rows(self, writer):
        for doctor in Doctor.objects.all().order_by('id'):
            self._write_row(
                writer,
                'Doctor',
                doctor.id,
                name=doctor.name,
                secondary=doctor.specialization,
                tertiary=doctor.education or '',
                status=doctor.working_days or '',
                notes=f'Experience: {doctor.experience} years; Rating: {doctor.rating or ""}',
                details={
                    'initials': doctor.initials,
                    'experience': doctor.experience,
                    'patients': doctor.Patients,
                    'start_time': doctor.start_time,
                    'end_time': doctor.end_time,
                },
            )

    def _write_treatment_rows(self, writer):
        for treatment in Treatment.objects.all().order_by('id'):
            self._write_row(
                writer,
                'Treatment',
                treatment.id,
                name=treatment.Treatment_name,
                secondary=treatment.Price,
                tertiary=treatment.Duration,
                notes=treatment.Description,
            )

    def _write_inventory_rows(self, writer):
        for item in InventoryItem.objects.all().order_by('id'):
            self._write_row(
                writer,
                'InventoryItem',
                item.id,
                name=item.name,
                secondary=item.category,
                tertiary=str(item.qty),
                record_date=item.expiry.isoformat() if item.expiry else '',
                notes=item.notes or '',
                details={
                    'created_at': item.created_at,
                    'updated_at': item.updated_at,
                },
            )

    def _write_clinic_rows(self, writer):
        clinic = ClinicInformation.objects.first()
        if not clinic:
            return
        self._write_row(
            writer,
            'ClinicInformation',
            clinic.id,
            name=clinic.clinic_name or '',
            secondary=clinic.reg_no,
            tertiary=clinic.doctor_name or '',
            notes=clinic.address or '',
            details={
                'phone': clinic.phone,
                'email': clinic.email,
                'doctor_specialist': clinic.doctor_specialist,
                'open_time': clinic.open_time,
                'close_time': clinic.close_time,
            },
        )

    def get(self, request):
        return self._csv_response(request)


class SettingsBackupDatabaseView(LoginRequiredMixin, TemplateView):
    def get(self, request):
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=204)
            response['HX-Redirect'] = request.get_full_path()
            return response

        database_path = settings.DATABASES['default']['NAME']
        if not os.path.exists(database_path):
            return HttpResponse('Database file not found.', status=404)

        backup_name = f'clinic_backup_{timezone.now().date()}.sqlite3'
        return FileResponse(open(database_path, 'rb'), as_attachment=True, filename=backup_name)


class SettingsClearTemporaryDataView(LoginRequiredMixin, TemplateView):
    def get(self, request):
        response = HttpResponse(status=204)
        response['HX-Trigger'] = json.dumps({
            'showNotification': {
                'message': 'Temporary data reset successfully.',
                'type': 'success',
                'duration': 3000,
                'closemodel': ''
            }
        })
        return response
        
