from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.views import View
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
import json
from django.db.models import Q
from datetime import date, datetime
from django.http import HttpResponse, JsonResponse
from .models import Patient, labdetails, labtest, DailyPatient, Prescription, labwork, PatientUpload
from django.utils import timezone




@login_required
def patients_table_body(request):
    # Base queryset
    patients_qs = Patient.objects.all().order_by('-created_at')

    # Filters from query params
    q = request.GET.get('q', '').strip()
    gender = request.GET.get('gender', '').strip()
    status = request.GET.get('status', '').strip()

    if q:
        # numeric -> try id, otherwise search names and phone
        if q.isdigit():
            patients_qs = patients_qs.filter(id=int(q))
        else:
            patients_qs = patients_qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q)
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
    
    return render(request, "ext/patients_data.html", context)

class PatientsPartialView(LoginRequiredMixin, TemplateView):
    template_name = 'partials/patients.html'
    def get(self,request):
        context={
            "labdetails":labdetails.objects.all().order_by("-id"),
        "labtest":labtest.objects.all().order_by("-id")
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
            
            medicines = list(prescription.medicines.values('drug_name', 'dosage', 'frequency', 'duration'))
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