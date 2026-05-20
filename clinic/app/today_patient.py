import json
import os
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.views import View
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Count, Q
from .models import (
    DailyPatient,
    PatientUpload,
    MedicationTemplate,
    Treatment,
    Doctor,
    ClinicInformation,
    Prescription,
    PrescriptionMedication,
    PrescriptionTreatment,
    BillingInvoice,
    labtest,
    labwork,
    labdetails,
)
from django.contrib.auth.decorators import login_required
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.utils.text import slugify
from datetime import datetime


UPLOAD_MAX_BYTES = 50 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {
    '.jpg': 'image',
    '.jpeg': 'image',
    '.png': 'image',
    '.gif': 'image',
    '.webp': 'image',
    '.pdf': 'pdf',
    '.mp4': 'video',
    '.webm': 'video',
    '.mov': 'video',
    '.avi': 'video',
    '.mkv': 'video',
    '.docx': 'docx',
}


def _file_type_from_name(file_name):
    lower_name = (file_name or '').lower()
    dot_index = lower_name.rfind('.')
    ext = lower_name[dot_index:] if dot_index != -1 else ''
    return ALLOWED_UPLOAD_EXTENSIONS.get(ext), ext


def _format_mb(size_bytes):
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def _parse_treatment_names(payload):
    if not payload:
        return []

    names = []
    seen = set()
    for part in payload.split(";;"):
        name = (part or "").strip()
        if not name:
            continue
        # Extract treatment name (before first |)
        treatment_name = name.split("|")[0].strip()
        key = treatment_name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(treatment_name)
    return names


def _parse_treatment_details(payload):
    """Parse treatment payload in format: treatment_name|tooth_number|is_paid"""
    if not payload:
        return []
    
    treatments = []
    for part in payload.split(";;"):
        part = part.strip()
        if not part:
            continue
        
        parts = part.split("|")
        treatment_name = parts[0].strip() if parts else ""
        tooth_number = parts[1].strip() if len(parts) > 1 else ""
        is_paid = parts[2].strip() == "1" if len(parts) > 2 else True
        
        if treatment_name:
            treatments.append({
                'name': treatment_name,
                'tooth_number': tooth_number,
                'is_paid': is_paid
            })
    
    return treatments


def _price_to_decimal(raw_price):
    cleaned = (str(raw_price or "")
               .replace(",", "")
               .replace("₹", "")
               .replace("$", "")
               .strip())
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _treatment_meta_map(treatment_names):
    if not treatment_names:
        return {}

    rows = Treatment.objects.filter(Treatment_name__in=treatment_names)
    meta = {}
    for row in rows:
        key = (row.Treatment_name or "").strip().lower()
        if not key:
            continue
        meta[key] = {
            "name": row.Treatment_name,
            "description": row.Description or "",
            "price": row.Price or "",
            "duration": row.Duration or "",
        }
    return meta


def _treatment_details_from_names(treatment_names):
    meta = _treatment_meta_map(treatment_names)
    details = []
    for name in treatment_names:
        info = meta.get((name or "").strip().lower(), {})
        details.append({
            "name": name,
            "description": info.get("description", ""),
            "price": info.get("price", ""),
            "duration": info.get("duration", ""),
        })
    return details


def _patient_calendar_data_json():
    """Generate calendar data with patient counts by status per date"""
    calendar_data = {}
    
    # Get all daily patient dates with counts by status
    dates_data = list(
        DailyPatient.objects
        .annotate(d=TruncDate('date'))
        .values('d')
        .annotate(
            total=Count('id'),
            completed_count=Count('id', filter=Q(status='COMPLETED')),
            pending_count=Count('id', filter=Q(status='PENDING')),
            cancelled_count=Count('id', filter=Q(status='cancelled'))
        )
        .order_by('d')
    )
    
    for entry in dates_data:
        if entry['d']:
            date_str = entry['d'].isoformat()
            calendar_data[date_str] = {
                'total': entry['total'],
                'confirmed': entry['completed_count'],
                'pending': entry['pending_count'],
                'cancelled': entry['cancelled_count']
            }
    
    return json.dumps(calendar_data)


class today_patient(LoginRequiredMixin,TemplateView):
    template_name="partials/today_patients.html"
    def get(self,request):
        context={
            "treatment":Treatment.objects.all(),
            "doctors":Doctor.objects.all(),
            "clinic": ClinicInformation.objects.first(),
            "labdetails": labdetails.objects.all(),
            "labtest":labtest.objects.all(),
            "patient_calendar_data_json": _patient_calendar_data_json()
        }
        
        return render(request,self.template_name,context)


class DailyPatientDeleteView(LoginRequiredMixin, TemplateView):
    def post(self, request):
        daily_patient_id = request.POST.get('daily_patient_id', '').strip()
        if not daily_patient_id:
            response = get_today_patient_data(request)
            response["HX-Trigger"] = json.dumps({
                "showNotification": {
                    "message": "Daily patient id is required",
                    "type": "error",
                    "duration": 4000,
                    "closemodel": ""
                }
            })
            return response

        daily_patient = get_object_or_404(DailyPatient, id=int(daily_patient_id))
        patient_name = daily_patient.name or str(daily_patient.patient)
        daily_patient.delete()

        response = get_today_patient_data(request)
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"Daily patient deleted successfully for {patient_name}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "deletePatientModal"
            }
        })
        return response
    
        

class PrescriptionSubmitView(LoginRequiredMixin, View):
    def _notification_response(self, message, message_type="success", close_modal=""):
        response = get_today_patient_data(self.request)  # Reuse the existing view to get updated data
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": message,
                "type": message_type,
                "duration": 3500,
                "closemodel": close_modal,
            }
        })
        return response

    def post(self, request, *args, **kwargs):
        daily_patient_id = request.POST.get("dailyPatientId", "").strip()
        if not daily_patient_id:
            return self._notification_response(
                "Daily patient id is required",
                message_type="error",
            )

        try:
            daily_patient = DailyPatient.objects.select_related("patient").get(pk=int(daily_patient_id))
        except (ValueError, DailyPatient.DoesNotExist):
            return self._notification_response(
                "Selected today-patient row not found",
                message_type="error",
            )

        # Optional cross-check from hidden field to prevent accidental mismatches.
        patient_id = request.POST.get("patientId", "").strip()
        if patient_id:
            try:
                if int(patient_id) != daily_patient.patient_id:
                    return self._notification_response(
                        "Daily patient and patient do not match",
                        message_type="error",
                    )
            except ValueError:
                return self._notification_response(
                    "Invalid patient id",
                    message_type="error",
                )

        visit_date_raw = request.POST.get("visitDate", "").strip()
        visit_date = timezone.localdate()
        if visit_date_raw:
            try:
                visit_date = datetime.strptime(visit_date_raw, "%Y-%m-%d").date()
            except ValueError:
                return self._notification_response(
                    "Invalid visit date format",
                    message_type="error",
                )

        prescription, created = Prescription.objects.get_or_create(
            daily_patient=daily_patient,
            defaults={
                "visit_date": visit_date,
                "created_by": request.user if request.user.is_authenticated else None,
            },
        )
        prescription.visit_date = visit_date

        prescription.age_gender = request.POST.get("patientAgeGender", "").strip()
        prescription.allergies = request.POST.get("patientAllergies", "").strip()
        prescription.chief_complaint = request.POST.get("chiefComplaint", "").strip()
        prescription.diagnosis = request.POST.get("diagnosis", "").strip()
        prescription.advice = request.POST.get("advice", "").strip()
        if request.user.is_authenticated and not prescription.created_by_id:
            prescription.created_by = request.user
        prescription.save()

        if not created:
            prescription.medicines.all().delete()
            prescription.treatments.all().delete()

        meds_payload = request.POST.get("meds", "").strip()
        if meds_payload:
            for medicine_row in meds_payload.split(";;"):
                if not medicine_row.strip():
                    continue
                parts = medicine_row.split("|")
                while len(parts) < 4:
                    parts.append("")
                name, dosage, frequency, duration = [p.strip() for p in parts[:4]]
                if not name:
                    continue
                PrescriptionMedication.objects.create(
                    prescription=prescription,
                    drug_name=name,
                    dosage=dosage,
                    frequency=frequency,
                    duration=duration,
                )

        treatments_payload = request.POST.get("treatments", "").strip()
        treatment_details = _parse_treatment_details(treatments_payload)
        selected_treatment_names = [t['name'] for t in treatment_details]
        treatment_meta = _treatment_meta_map(selected_treatment_names)

        doctor_name = ""
        if getattr(request.user, "doctor", None) and request.user.doctor.name:
            doctor_name = request.user.doctor.name
        elif daily_patient.doctor:
            doctor_name = daily_patient.doctor
        elif request.user.is_authenticated:
            doctor_name = request.user.get_full_name() or request.user.username

        daily_patient.treatments = ", ".join(selected_treatment_names) if selected_treatment_names else ""
        daily_patient.doctor = doctor_name
        daily_patient.status="COMPLETED"
        daily_patient.save()

        if treatment_details:
            for treatment_detail in treatment_details:
                PrescriptionTreatment.objects.create(
                    prescription=prescription,
                    treatment_name=treatment_detail['name'],
                    tooth_number=treatment_detail.get('tooth_number', ''),
                    is_paid=treatment_detail.get('is_paid', True),
                )

            total_amount = Decimal("0.00")
            note_parts = []
            for treatment_detail in treatment_details:
                treatment_name = treatment_detail['name']
                is_paid = treatment_detail.get('is_paid', True)
                tooth_number = treatment_detail.get('tooth_number', '')
                
                info = treatment_meta.get((treatment_name or "").strip().lower(), {})
                parsed_price = _price_to_decimal(info.get("price"))
                
                # Only add amount for paid treatments
                if is_paid and parsed_price is not None:
                    total_amount += parsed_price

                duration = (info.get("duration") or "").strip()
                status_label = "PAID" if is_paid else "UNPAID"
                tooth_label = f" Tooth {tooth_number}" if tooth_number else ""
                
                note_parts.append(
                    f"{treatment_name}{tooth_label} ({status_label}) ({duration or '-'})".strip()
                )

            billing_note = "; ".join(note_parts).strip()[:500] if note_parts else None
            treatment_summary = ", ".join(selected_treatment_names)

            pending_invoice = (
                BillingInvoice.objects
                .filter(daily_patient=daily_patient, status=BillingInvoice.STATUS_PENDING)
                .order_by('-id')
                .first()
            )

            if pending_invoice:
                pending_invoice.patient = daily_patient.patient
                pending_invoice.treatment = treatment_summary
                pending_invoice.doctor = doctor_name or pending_invoice.doctor
                pending_invoice.amount = total_amount
                pending_invoice.note = billing_note
                pending_invoice.created_by = pending_invoice.created_by or (request.user if request.user.is_authenticated else None)
                pending_invoice.save(update_fields=[
                    'patient', 'treatment', 'doctor', 'amount', 'note', 'created_by', 'updated_at'
                ])
            else:
                BillingInvoice.objects.create(
                    patient=daily_patient.patient,
                    daily_patient=daily_patient,
                    treatment=treatment_summary,
                    doctor=doctor_name or None,
                    amount=total_amount,
                    note=billing_note,
                    status=BillingInvoice.STATUS_PENDING,
                    created_by=request.user if request.user.is_authenticated else None,
                )

        return self._notification_response(
            "Prescription updated successfully" if not created else "Prescription data submitted successfully",
            message_type="success",
            close_modal="prescriptionFormModal",
        )
        


@login_required
def get_latest_prescription(request, patient_id):
    daily_patient_id = request.GET.get("daily_patient_id", "").strip()
    print(f"Fetching latest prescription for patient_id={patient_id} with daily_patient_id={daily_patient_id}")

    base_qs = Prescription.objects.prefetch_related("medicines", "treatments")
    if daily_patient_id:
        try:
            prescription = base_qs.filter(
                daily_patient__patient_id=patient_id,
                daily_patient_id=int(daily_patient_id),
            ).order_by("-updated_at").first()
        except ValueError:
            prescription = None
    else:
        prescription = base_qs.filter(daily_patient__patient_id=patient_id).order_by("-updated_at").first()

    if not prescription:
        return JsonResponse({"exists": False})

    treatment_names = [t.treatment_name for t in prescription.treatments.all() if t.treatment_name]
    treatment_details = _treatment_details_from_names(treatment_names)

    return JsonResponse({
        "exists": True,
        "id": prescription.id,
        "patientId": prescription.daily_patient.patient_id,
        "dailyPatientId": prescription.daily_patient_id,
        "visitDate": prescription.visit_date.isoformat() if prescription.visit_date else "",
        "ageGender": prescription.age_gender or "",
        "allergies": prescription.allergies or "",
        "chiefComplaint": prescription.chief_complaint or "",
        "diagnosis": prescription.diagnosis or "",
        "advice": prescription.advice or "",
        "medicines": [
            {
                "name": m.drug_name or "",
                "dosage": m.dosage or "",
                "freq": m.frequency or "",
                "duration": m.duration or "",
            }
            for m in prescription.medicines.all()
        ],
        "treatments": treatment_names,
        "treatmentDetails": treatment_details,
    })


@login_required
def get_daily_patient_prescription(request, daily_patient_id):
    prescription = (
        Prescription.objects
        .filter(daily_patient_id=daily_patient_id)
        .prefetch_related("medicines", "treatments")
        .order_by("-updated_at")
        .first()
    )

    if not prescription:
        return JsonResponse({"exists": False})

    # Get treatments with tooth numbers and paid status
    treatments = list(prescription.treatments.all())
    treatment_names = [t.treatment_name for t in treatments if t.treatment_name]
    
    # Build treatment details with tooth number and paid status
    treatment_details = []
    for treatment in treatments:
        if not treatment.treatment_name:
            continue
        meta = _treatment_meta_map([treatment.treatment_name])
        info = meta.get((treatment.treatment_name or "").strip().lower(), {})
        treatment_details.append({
            "name": treatment.treatment_name,
            "tooth_number": treatment.tooth_number or "",
            "is_paid": treatment.is_paid if hasattr(treatment, 'is_paid') else True,
            "description": info.get("description", ""),
            "price": info.get("price", ""),
            "duration": info.get("duration", ""),
        })

    return JsonResponse({
        "exists": True,
        "id": prescription.id,
        "patientId": prescription.daily_patient.patient_id,
        "dailyPatientId": prescription.daily_patient_id,
        "visitDate": prescription.visit_date.isoformat() if prescription.visit_date else "",
        "ageGender": prescription.age_gender or "",
        "allergies": prescription.allergies or "",
        "chiefComplaint": prescription.chief_complaint or "",
        "diagnosis": prescription.diagnosis or "",
        "advice": prescription.advice or "",
        "medicines": [
            {
                "name": m.drug_name or "",
                "dosage": m.dosage or "",
                "freq": m.frequency or "",
                "duration": m.duration or "",
            }
            for m in prescription.medicines.all()
        ],
        "treatments": treatment_names,
        "treatmentDetails": treatment_details,
    })


@login_required
def get_today_patient_data(request):
    qs = DailyPatient.objects.all().order_by('-date')
    
    # Get filters from request
    doctor = request.GET.get('doctor', '').strip()
    status = request.GET.get('status', '').strip()
    treatment = request.GET.get('treatment', '').strip()
    q_date = request.GET.get('date', '').strip()

    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1

    # Step 1: Get unique dates (for pagination)
    unique_dates = list(
        qs.annotate(date_only=TruncDate('date'))
        .values_list('date_only', flat=True)
        .distinct()
        .order_by('-date_only')
    )

    total_pages = len(unique_dates)

    # Step 2: Handle date search
    if q_date:
        try:
            q_date_obj = datetime.strptime(q_date, "%Y-%m-%d").date()

            if q_date_obj in unique_dates:
                page_number = unique_dates.index(q_date_obj) + 1
            else:
                # ❌ Date not found → return empty result
                context = {
                    "appoinment": DailyPatient.objects.none(),
                    "has_previous": False,
                    "has_next": False,
                    "previous_page_number": None,
                    "next_page_number": None,
                    "total_count": 0,
                    "current_page": 1,
                    "per_page": 0,
                    "filters": {
                        "doctor": doctor,
                        "status": status,
                        "treatment": treatment,
                        "date": q_date
                    },
                    "message": "Data not found for selected date"
                }
                
                response = render(request, "ext/today_patient_data.html", context)
                response["HX-Trigger"] = json.dumps({
                    "showNotification": {
                        "message": f"Data Not Found The Date {q_date}",
                        "type": "info",
                        "duration": 4000,
                        "closemodel":""
                    }
                })
                return response

        except ValueError:
            # Invalid date format
            context = {
                "appoinment": DailyPatient.objects.none(),
                "has_previous": False,
                "has_next": False,
                "previous_page_number": None,
                "next_page_number": None,
                "total_count": 0,
                "current_page": 1,
                "per_page": 0,
                "filters": {
                    "doctor": doctor,
                    "status": status,
                    "treatment": treatment,
                    "date": q_date
                },
                "message": "Invalid date format"
            }
            return render(request, "ext/today_patient_data.html", context)

    # Step 3: Get data for current page
    if 1 <= page_number <= total_pages:
        target_date = unique_dates[page_number - 1]
        page_qs = qs.filter(date__date=target_date)
    else:
        page_qs = DailyPatient.objects.none()

    # Step 4: Apply filters
    if doctor and doctor.lower() != 'all':
        page_qs = page_qs.filter(doctor__icontains=doctor)

    if status and status.lower() != 'all':
        page_qs = page_qs.filter(status__iexact=status)

    if treatment and treatment.lower() != 'all':
        page_qs = page_qs.filter(treatments__icontains=treatment)

    current_page_qs = page_qs

    # Step 5: Final context
    context = {
        "appoinment": current_page_qs,
        "has_previous": page_number > 1,
        "has_next": page_number < total_pages,
        "previous_page_number": page_number - 1 if page_number > 1 else None,
        "next_page_number": page_number + 1 if page_number < total_pages else None,
        "total_count": current_page_qs.count(),
        "current_page": page_number,
        "per_page": current_page_qs.count(),
        "filters": {
            "doctor": doctor,
            "status": status,
            "treatment": treatment,
            "date": q_date
        }
    }

    response = render(request, "ext/today_patient_data.html", context)
    response["HX-Trigger"] = json.dumps({
                    "showNotification": {
                        "message": f"Data is available for the date {target_date}",
                        "type": "success",
                        "duration": 4000,
                        "closemodel":""
                    }
                })
    return response


class PatientUploadListView(LoginRequiredMixin, TemplateView):
    template_name = "ext/patient_upload_data.html"

    def get(self, request, daily_patient_id, *args, **kwargs):
        daily_patient = get_object_or_404(
            DailyPatient.objects.select_related('patient'),
            id=daily_patient_id,
        )
        uploads = list(PatientUpload.objects.filter(daily_patient=daily_patient))
        
        # Custom sort: Images → PDFs → Others
        file_type_order = {'image': 0, 'pdf': 1}
        uploads.sort(key=lambda x: (
            file_type_order.get(x.file_type, 2),  # Others get priority 2
            -x.created_at.timestamp() if x.created_at else 0  # Within same type, sort by newest first
        ))
        
        context = {
            "uploads": uploads,
            "daily_patient": daily_patient,
        }
        return render(request, self.template_name, context)


class PatientUploadCreateView(LoginRequiredMixin, TemplateView):
    template_name = "ext/patient_upload_data.html"

    def post(self, request, *args, **kwargs):
        daily_patient_id = request.POST.get("daily_patient_id", "").strip()
        if not daily_patient_id:
            return HttpResponse("Daily patient id is required", status=400)

        daily_patient = get_object_or_404(
            DailyPatient.objects.select_related('patient'),
            id=daily_patient_id,
        )

        files = request.FILES.getlist("files")
        uploads_qs = PatientUpload.objects.filter(daily_patient=daily_patient)
        if not files:
            response = render(request, self.template_name, {
                "uploads": uploads_qs,
                "daily_patient": daily_patient,
            })
            response["HX-Trigger"] = json.dumps({
                "showNotification": {
                    "message": "Please select at least one file",
                    "type": "error",
                    "duration": 4500,
                    "closemodel": ""
                }
            })
            return response

        validation_errors = []
        for incoming_file in files:
            file_type, ext = _file_type_from_name(incoming_file.name)
            if not file_type:
                validation_errors.append(f"{incoming_file.name}: unsupported type ({ext or 'no extension'})")
                continue
            if incoming_file.size > UPLOAD_MAX_BYTES:
                validation_errors.append(
                    f"{incoming_file.name}: file too large ({_format_mb(incoming_file.size)}). Maximum is 50 MB"
                )

        if validation_errors:
            response = render(request, self.template_name, {
                "uploads": uploads_qs,
                "daily_patient": daily_patient,
            })
            response["HX-Trigger"] = json.dumps({
                "showNotification": {
                    "message": validation_errors[0],
                    "type": "error",
                    "duration": 5500,
                    "closemodel": ""
                }
            })
            return response

        username = request.user.username if request.user.is_authenticated else "anonymous"

        for incoming_file in files:
            file_type, _ = _file_type_from_name(incoming_file.name)
            upload = PatientUpload.objects.create(
                patient=daily_patient.patient,
                daily_patient=daily_patient,
                file=incoming_file,
                original_name=incoming_file.name,
                file_type=file_type,
                mime_type=getattr(incoming_file, 'content_type', '') or '',
                size_bytes=incoming_file.size,
                uploader=request.user if request.user.is_authenticated else None,
                uploader_username=username,
            )

            # Rename stored file to deterministic, readable format after id is available.
            ext = os.path.splitext(incoming_file.name)[1].lower() or '.bin'
            safe_patient_name = slugify(str(daily_patient.patient)) or 'patient'
            readable_name = (
                f"{safe_patient_name}_pid{daily_patient.patient_id}"
                f"_dp{daily_patient.id}_u{upload.id}{ext}"
            )

            current_file_name = upload.file.name
            current_folder = os.path.dirname(current_file_name)
            target_path = os.path.join(current_folder, readable_name).replace('\\', '/')

            if current_file_name and current_file_name != target_path:
                storage = upload.file.storage
                with storage.open(current_file_name, 'rb') as source_file:
                    saved_name = storage.save(target_path, source_file)
                storage.delete(current_file_name)
                upload.file.name = saved_name

            upload.original_name = readable_name
            upload.save(update_fields=['file', 'original_name'])

        uploads_qs = PatientUpload.objects.filter(daily_patient=daily_patient)
        response = render(request, self.template_name, {
            "uploads": uploads_qs,
            "daily_patient": daily_patient,
        })
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"Uploaded {len(files)} file(s) successfully",
                "type": "success",
                "duration": 3500,
                "closemodel": ""
            }
        })
        return response


class PatientUploadDeleteView(LoginRequiredMixin, TemplateView):
    template_name = "ext/patient_upload_data.html"

    def post(self, request, upload_id, *args, **kwargs):
        upload = get_object_or_404(PatientUpload.objects.select_related('daily_patient__patient'), id=upload_id)
        daily_patient = upload.daily_patient

        if upload.file:
            upload.file.delete(save=False)
        upload.delete()

        uploads_qs = PatientUpload.objects.filter(daily_patient=daily_patient)
        response = render(request, self.template_name, {
            "uploads": uploads_qs,
            "daily_patient": daily_patient,
        })
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": "File deleted successfully",
                "type": "success",
                "duration": 3000,
                "closemodel": ""
            }
        })
        return response