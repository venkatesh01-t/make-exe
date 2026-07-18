from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.views import View
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
import json
from django.db.models import Q, Value
from django.db.models.functions import Concat
from datetime import date, datetime
from django.http import HttpResponse, JsonResponse
from .models import Patient, labdetails, labtest, DailyPatient, Prescription, labwork, PatientUpload, Doctor, Treatment, BillingInvoice, ClinicInformation
from django.utils import timezone




@login_required
def patients_table_body(request):
    # Base queryset
    patients_qs = Patient.objects.all().order_by('-updated_at')

    # Filters from query params
    q = request.GET.get('q', '').strip()
    gender = request.GET.get('gender', '').strip()
    status = request.GET.get('status', '').strip()

    if q:
        clean_q = q.replace(" ", "")
        fuzzy_pattern = '.*'.join(list(clean_q))

        patients_qs = patients_qs.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name')
        )
        if clean_q.isdigit():
            patients_qs = patients_qs.filter(
                Q(id=int(clean_q)) | Q(phone__iregex=fuzzy_pattern) | Q(full_name__iregex=fuzzy_pattern)
            )
        else:
            patients_qs = patients_qs.filter(
                Q(full_name__iregex=fuzzy_pattern) | Q(phone__iregex=fuzzy_pattern)
            )

    if gender:
        patients_qs = patients_qs.filter(gender__iexact=gender)

    if status:
        patients_qs = patients_qs.filter(status__iexact=status)

    # Pagination
    page_number = request.GET.get('page', 1)
    paginator = Paginator(patients_qs, 10)  # 10 patients per page
    page_obj = paginator.get_page(page_number)

    patients_data = [
        {
            
            'name': f"{p.first_name} {p.last_name}",
            'firstname': p.first_name,
            'lastname': p.last_name,
            'dob': p.date_of_birth.strftime('%Y-%m-%d') if p.date_of_birth else "None",
            'email': p.email,
            'medical_notes': p.medical_history,
            'id': p.id,
            'phone': p.phone,
            'age': p.age,
            'gender': p.gender,
            'last_visit': p.last_visit ,
            "updated_at":p.updated_at,
            'status': p.status,
            'color': getattr(p, 'color', 'blue')
        }
        for p in page_obj
    ]

    context = {
        
        "patients": patients_data,
        "page_obj": page_obj,
        "has_previous": page_obj.has_previous(),
        "has_next": page_obj.has_next(),
        "previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
        "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
        "start_index": page_obj.start_index(),
        "end_index": page_obj.end_index(),
        "total_count": paginator.count,
        "q": q,
        "gender": gender,
        "status": status,
        
    }
    
    return render(request, "ext/patients/patients_data.html", context)

class PatientsPartialView(LoginRequiredMixin, TemplateView):
    template_name = 'partials/patients.html'
    def get(self,request):
        q = request.GET.get('q', '')
        context={
            "labdetails":labdetails.objects.all().order_by("-id"),
            "labtest":labtest.objects.all().order_by("-id"),
            "doctors": Doctor.objects.all(),
            "treatment": Treatment.objects.all(),
            "q": q
        }
        return render(request,self.template_name,context)
   
    

class Patientsdatasave(LoginRequiredMixin, TemplateView):
    def post(self, request):
        first_name = request.POST.get('first_name') or ''
        last_name = request.POST.get('last_name') or ''
        name = first_name + " " + last_name or 'N/A'
        email = request.POST.get('email') or 'N/A'
        phone = request.POST.get('phone') or 'N/A'
        medical_notes1= request.POST.get('medical_notes') or "none"
        dob_main = request.POST.get('dob') or "1900-01-01"
        dob = datetime.strptime(dob_main, "%Y-%m-%d").date()  # Convert string to date
        today = date.today()
        # Calculate full years
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1  # Birthday hasn't occurred yet this year
        print(age)
        gender = request.POST.get('gender') or 'N/A'
        status = 'Active'  # Default status
        previous_visits = 'None'  # Default previous visits
        last_visit = date.today()  # Set last visit to today for new patient
        
        # Check for duplicates
        override_duplicate = request.POST.get('override_duplicate') == 'true'
        existing_patient = Patient.objects.filter(phone=phone).first() if phone else None
        if existing_patient and not override_duplicate:
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "patientExistsError": {"message": f"A patient with this phone number already exists! (Patient ID: #{existing_patient.id}, Name: {existing_patient.first_name} {existing_patient.last_name})"}
            })
            return response

        # Save to database
        Patient.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            date_of_birth=dob_main,
            age=age,
            gender=gender,
            status=status,
            medical_history=medical_notes1,
            previous_visits=previous_visits,
            last_visit=last_visit
        ).save()
        # 🔹 Save to database
        print(request.POST)

    
        # 🔹 Return success response
        response = patients_table_body(request) 
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"Patient added successfully for {name}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "patientModal"
            },
            
        })

        return response

class PatientEditView(LoginRequiredMixin, TemplateView):
    def post(self, request):
        patient_id = request.POST.get('patient_id')
        print(request.POST)
        print(patient_id)
        print("hello")
        patient = get_object_or_404(Patient, id=patient_id)
        patient.first_name = request.POST.get('first_name') or ""
        patient.last_name = request.POST.get('last_name') or " "
        patient.email = request.POST.get('email') or patient.email
        patient.phone = request.POST.get('phone') or patient.phone
        medical_notes= request.POST.get('medical_notes') or patient.medical_history
        dob_main = request.POST.get('dob') or patient.date_of_birth.strftime("%Y-%m-%d")
        dob = datetime.strptime(dob_main, "%Y-%m-%d").date()  # Convert string to date
        today = date.today()
        # Calculate full years
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1  # Birthday hasn't occurred yet this year
        print(age)
        patient.age = age
        patient.gender = request.POST.get('gender') or patient.gender
        patient.medical_history = medical_notes
        patient.save()
        name = patient.first_name + " " + patient.last_name
        # 🔹 Save to database
        print(f"Patient updated: {name}")


        # 🔹 Return success response
        response =patients_table_body(request) 
        
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"Patient updated successfully for {name}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "editPatientModal"
            },
        })

        return response

class PatientDeleteView(LoginRequiredMixin, TemplateView):
    def post(self, request):
        patient_id = request.POST.get('patient_id')
        print(request.POST)
        patient = get_object_or_404(Patient, id=int(patient_id))
        name = patient.first_name + " " + patient.last_name
        patient.delete()
        print(f"Patient deleted: {name}")
        response = patients_table_body(request) 
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"Patient deleted successfully for {name}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "deletePatientModal"
            },
        })

        return response
    
class today_patient_book(LoginRequiredMixin,TemplateView):
    
    def post(self, request, *args, **kwargs):
        patient_id = kwargs.get("id")
        print(patient_id)
        patient = get_object_or_404(Patient, id=int(patient_id))
        patient.last_visit=timezone.now()
        patient.save()
        DailyPatient.objects.create(
            patient=patient, 
            name=patient.first_name+" "+ patient.last_name    ,     # link ForeignKey
            complaint='',
            treatments='',
            date=timezone.now() 
        ).save()

        response = patients_table_body(request) 
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"Patient marked as visited for {patient_id}!",
                "type": "success",
                "duration": 4000,
                "closemodel": "todayPatientConfirmModal"
                
            },
        })
        return response


# --------------------------
# API Endpoints for Patient History Modal
# --------------------------

class PatientDailyVisitsAPIView(LoginRequiredMixin, View):
    """Get all daily visits for a patient"""
    def get(self, request, patient_id):
        try:
            visits = DailyPatient.objects.filter(patient_id=patient_id).order_by('-date').values(
                'id', 'name', 'date', 'treatments', 'doctor', 'status', 'complaint'
            )
            return JsonResponse(list(visits), safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class PatientBillingAPIView(LoginRequiredMixin, View):
    """Get all billing invoices for a patient"""
    def get(self, request, patient_id):
        try:
            invoices = BillingInvoice.objects.filter(patient_id=patient_id).order_by('-bill_date').values(
                'id', 'invoice_number', 'treatment', 'doctor', 'amount', 'status', 'note', 'bill_date', 'paid_at'
            )
            return JsonResponse(list(invoices), safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class PatientLabWorkAPIView(LoginRequiredMixin, View):
    """Get all lab work ordered for a patient"""
    def get(self, request, patient_id):
        try:
            labs = labwork.objects.filter(patient_id=patient_id).order_by('-date_sent').values(
                'id', 'patient_name', 'work_type', 'lab_name', 'workflow_status', 'date_sent'
            )
            return JsonResponse(list(labs), safe=False)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class DailyPatientPrescriptionAPIView(LoginRequiredMixin, View):
    """Get prescription details for a specific daily patient visit"""
    def get(self, request, daily_patient_id):
        try:
            prescription = Prescription.objects.filter(daily_patient_id=daily_patient_id).first()
            if not prescription:
                return JsonResponse({'error': 'Prescription not found'}, status=404)
            
            medicines = list(prescription.medicines.values('drug_name', 'dosage', 'frequency', 'duration', 'food'))
            treatments = list(prescription.treatments.values('treatment_name'))
            
            return JsonResponse({
                'id': prescription.id,
                'visit_date': prescription.visit_date.isoformat(),
                'chief_complaint': prescription.chief_complaint,
                'diagnosis': prescription.diagnosis,
                'advice': prescription.advice,
                'age_gender': prescription.age_gender,
                'allergies': prescription.allergies,
                'medicines': medicines,
                'treatments': treatments,
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class LabWorkDetailAPIView(LoginRequiredMixin, View):
    """Get detailed information about a lab work"""
    def get(self, request, labwork_id):
        try:
            lab = labwork.objects.filter(id=labwork_id).values(
                'id', 'patient_name', 'work_type', 'lab_name', 'workflow_status', 'date_sent', 'note'
            ).first()
            
            if not lab:
                return JsonResponse({'error': 'Lab work not found'}, status=404)
            
            return JsonResponse(lab)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class PatientFilesAPIView(LoginRequiredMixin, View):
    """Get all uploaded files for a patient"""
    def get(self, request, patient_id):
        try:
            patient = get_object_or_404(Patient, id=patient_id)
            uploads = PatientUpload.objects.filter(patient_id=patient_id).order_by('-created_at')
            

            uploads_data = []
            for upload in uploads:
                uploads_data.append({
                    'id': upload.id,
                    'original_name': upload.original_name,
                    'file_type': upload.file_type,
                    'mime_type': upload.mime_type,
                    'file': upload.file.url if upload.file else '',
                    'size_bytes': upload.size_bytes,
                    'created_at': upload.created_at.isoformat() if upload.created_at else '',
                    'uploader_username': upload.uploader_username or 'Unknown',
                })

            return JsonResponse({
                'patient_id': patient_id,
                'patient_name': f"{patient.first_name} {patient.last_name}",
                'uploads': uploads_data,
                'total': len(uploads_data),
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
class CheckPatientExistsView(LoginRequiredMixin, View):
    def post(self, request):
        phone = request.POST.get('phone') or ''
        
        existing_patient = Patient.objects.filter(phone=phone).first() if phone else None
        if phone and existing_patient:
            html = f"""<div id='addPatientErrorMsg' class='text-orange-700 text-xs font-medium mt-2 bg-orange-50 p-3 rounded-lg border border-orange-200'>
              <strong>Warning:</strong> A patient with this phone number already exists! (Patient ID: #{existing_patient.id}, Name: {existing_patient.first_name} {existing_patient.last_name})
              <label class='flex items-center mt-2 cursor-pointer'>
                <input type='checkbox' name='override_duplicate' value='true' class='w-4 h-4 text-orange-600 bg-white border-orange-300 rounded focus:ring-orange-500' onchange="var btn = document.getElementById('savePatientBtn'); btn.disabled = !this.checked; if(this.checked) {{ btn.className = 'bg-gradient-to-r from-teal-500 to-teal-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold shadow-lg shadow-teal-200 hover:shadow-xl transition'; }} else {{ btn.className = 'bg-gray-300 text-gray-500 px-5 py-2.5 rounded-xl text-sm font-semibold cursor-not-allowed transition'; }}">
                <span class='ml-2 text-orange-800 font-semibold'>Override and save this new patient anyway</span>
              </label>
            </div>
            <button type="submit" id="savePatientBtn" hx-swap-oob="true" disabled class="bg-gray-300 text-gray-500 px-5 py-2.5 rounded-xl text-sm font-semibold cursor-not-allowed transition">Save Patient</button>
            """
            return HttpResponse(html)
        else:
            html = """<div id='addPatientErrorMsg' class='text-red-600 text-xs font-medium hidden mt-2 bg-red-50 p-2 rounded-lg border border-red-100'></div>
            <button type="submit" id="savePatientBtn" hx-swap-oob="true" class="bg-gradient-to-r from-teal-500 to-teal-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold shadow-lg shadow-teal-200 hover:shadow-xl transition">Save Patient</button>
            """
            return HttpResponse(html)

class PatientFullReportView(LoginRequiredMixin, View):
    def get(self, request, patient_id):
        patient = get_object_or_404(Patient, pk=patient_id)
        sections = request.GET.get('sections', '').split(',')
        
        context = {
            'patient': patient,
            'clinic': ClinicInformation.objects.first(),
            'sections': sections,
            'today': timezone.now()
        }
        
        if 'visited' in sections:
            context['visits'] = DailyPatient.objects.filter(patient=patient).order_by('-date')
        
        if 'labwork' in sections:
            context['labworks'] = labwork.objects.filter(patient=patient).order_by('-date_sent')
            
        if 'prescriptions' in sections:
            context['prescriptions'] = Prescription.objects.filter(daily_patient__patient=patient).order_by('-created_at')
            
        if 'fileupload' in sections:
            context['files'] = PatientUpload.objects.filter(patient=patient).order_by('-created_at')
            
        if 'billing' in sections:
            context['bills'] = BillingInvoice.objects.filter(patient=patient).order_by('-bill_date')
            
        return render(request, 'ext/patients/patient_full_report_print.html', context)


class PatientCardPrintView(LoginRequiredMixin, View):
    def get(self, request, patient_id):
        patient = get_object_or_404(Patient, pk=patient_id)
        context = {
            'patient': patient,
            'clinic': ClinicInformation.objects.first(),
            'today': timezone.now()
        }
        return render(request, 'ext/patients/patient_card_print.html', context)

