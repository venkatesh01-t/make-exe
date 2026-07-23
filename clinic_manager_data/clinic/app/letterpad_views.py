import json
import re
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone

from .models import Patient, ClinicInformation, Doctor, Letterpad, CustomUser


def get_logged_in_doctor_name(user, clinic=None):
    doc_info = get_doctor_details(user, clinic=clinic)
    return doc_info['name']


def get_doctor_details(user, doctor_name_override=None, clinic=None):
    """Retrieve doctor details (name, education, specialization, signature) using user foreign key or doctor query."""
    doc_data = {
        'name': 'Doctor',
        'education': '',
        'specialization': '',
        'signature_url': None
    }

    # 1. Foreign key on CustomUser
    if user and user.is_authenticated:
        if hasattr(user, 'doctor') and user.doctor:
            doc = user.doctor
            doc_data['name'] = doc.name
            doc_data['education'] = doc.education or ''
            doc_data['specialization'] = doc.specialization or ''
            if doc.signature:
                doc_data['signature_url'] = doc.signature.url
            return doc_data

        # Match doctor by user full_name or username
        full_name = f"{user.first_name} {user.last_name}".strip() or user.username
        matched = Doctor.objects.filter(name__icontains=full_name).first()
        if matched:
            doc_data['name'] = matched.name
            doc_data['education'] = matched.education or ''
            doc_data['specialization'] = matched.specialization or ''
            if matched.signature:
                doc_data['signature_url'] = matched.signature.url
            return doc_data

        doc_data['name'] = full_name if full_name else user.username

    # 2. Check doctor_name_override
    if doctor_name_override:
        matched_by_override = Doctor.objects.filter(name__icontains=doctor_name_override).first()
        if matched_by_override:
            doc_data['name'] = matched_by_override.name
            doc_data['education'] = matched_by_override.education or ''
            doc_data['specialization'] = matched_by_override.specialization or ''
            if matched_by_override.signature:
                doc_data['signature_url'] = matched_by_override.signature.url
            return doc_data
        doc_data['name'] = doctor_name_override

    # 3. Fallback to clinic info
    if clinic:
        if not doc_data['name'] or doc_data['name'] == 'Doctor':
            doc_data['name'] = clinic.doctor_name or "Doctor"
        if not doc_data['specialization']:
            doc_data['specialization'] = clinic.doctor_specialist or ""

    return doc_data


def parse_letterpad_content(content, patient, clinic_info=None, doctor_name=None, user=None):
    """Replace placeholder tags with actual patient and clinic details."""
    if not content:
        return ""

    now = timezone.localtime()
    date_str = now.strftime("%b %d, %Y")
    
    patient_full_name = f"{patient.first_name} {patient.last_name or ''}".strip()
    
    clinic = clinic_info or ClinicInformation.objects.first()
    clinic_name = clinic.clinic_name if clinic and clinic.clinic_name else "Dental & Medical Clinic"
    clinic_reg = clinic.reg_no if clinic and clinic.reg_no else ""
    clinic_phone = clinic.phone if clinic and clinic.phone else ""
    clinic_address = clinic.address if clinic and clinic.address else ""

    resolved_doctor = doctor_name or get_logged_in_doctor_name(user, clinic)

    replacements = {
        r"\{name\}": patient_full_name,
        r"\{NAME\}": patient_full_name,
        r"\{age\}": str(patient.age) if patient.age is not None else "",
        r"\{AGE\}": str(patient.age) if patient.age is not None else "",
        r"\{gender\}": patient.gender or "",
        r"\{GENDER\}": patient.gender or "",
        r"\{date\}": date_str,
        r"\{DATE\}": date_str,
        r"\{doctor\}": resolved_doctor,
        r"\{DOCTOR\}": resolved_doctor,
        r"\{phone\}": patient.phone or "",
        r"\{PHONE\}": patient.phone or "",
        r"\{email\}": patient.email or "",
        r"\{EMAIL\}": patient.email or "",
        r"\{dob\}": patient.date_of_birth.strftime("%Y-%m-%d") if patient.date_of_birth else "",
        r"\{DOB\}": patient.date_of_birth.strftime("%Y-%m-%d") if patient.date_of_birth else "",
        r"\{medical_history\}": patient.medical_history or "N/A",
        r"\{MEDICAL_HISTORY\}": patient.medical_history or "N/A",
        r"\{history\}": patient.medical_history or "N/A",
        r"\{clinic_name\}": clinic_name,
        r"\{reg_no\}": clinic_reg,
        r"\{address\}": clinic_address,
        r"\{tab\}": "    ",
        r"\{TAB\}": "    ",
        r"\{indent\}": "    ",
        r"\{INDENT\}": "    ",
        r"\{space\}": "    ",
    }

    parsed = content
    for pattern, value in replacements.items():
        parsed = re.sub(pattern, str(value), parsed)

    return parsed


class LetterpadPatientDataView(LoginRequiredMixin, View):
    """Fetch patient information, presets, and letterpad history for modal."""
    def get(self, request, patient_id):
        patient = get_object_or_404(Patient, pk=patient_id)
        clinic = ClinicInformation.objects.first()
        
        # Doctor options
        doctors = list(Doctor.objects.values('id', 'name', 'specialization', 'education'))
        
        default_doctor_name = get_logged_in_doctor_name(request.user, clinic)

        # Patient letterpad history
        letterpads = Letterpad.objects.filter(patient=patient).select_related('created_by')
        history_data = []
        for lp in letterpads:
            history_data.append({
                'id': lp.id,
                'title': lp.title,
                'template_type': lp.template_type,
                'content': lp.content,
                'parsed_content': parse_letterpad_content(lp.content, patient, clinic, lp.doctor_name or default_doctor_name, user=request.user),
                'doctor_name': lp.doctor_name or default_doctor_name,
                'border_style': lp.border_style or 'dental_frame',
                'hide_header': lp.hide_header,
                'created_by': lp.created_by.username if lp.created_by else 'System',
                'created_at': lp.created_at.strftime("%b %d, %Y %I:%M %p")
            })

        patient_full_name = f"{patient.first_name} {patient.last_name or ''}".strip()

        # Default letter templates with keys
        templates = [
            {
                'id': 'medical_cert',
                'name': 'Medical Fitness Certificate',
                'title': 'MEDICAL FITNESS CERTIFICATE',
                'content': f"{{tab}}This is to certify that Mr./Ms. {{name}}, aged {{age}} years, {{gender}}, has been examined by me on {{date}}.\n\n{{tab}}Upon clinical evaluation, the patient is found to be physically fit and free from any contagious or infectious disease.\n\n{{tab}}Remark: Fit to resume work/studies from {{date}}.\n\n{{tab}}Prescribed Advice: Take adequate rest and maintain prescribed medication."
            },
            {
                'id': 'sick_leave',
                'name': 'Medical Leave Certificate',
                'title': 'MEDICAL LEAVE CERTIFICATE',
                'content': f"To Whom It May Concern,\n\n{{tab}}This is to certify that {{name}}, {{age}} yrs / {{gender}}, has been under my medical treatment for illness.\n\n{{tab}}Patient is advised complete medical rest for [_____] days starting from {{date}}.\n\n{{tab}}Patient is expected to be fit to resume normal duties on [_____].\n\n{{tab}}Diagnosis / Notes: Rest and follow-up as advised."
            },
            {
                'id': 'referral',
                'name': 'Doctor Referral Letter',
                'title': 'PATIENT REFERRAL LETTER',
                'content': f"Dear Doctor,\n\nRe: {{name}}, Age: {{age}} yrs, {{gender}}\nPhone: {{phone}}\n\n{{tab}}I am referring the above-named patient to your esteemed department for further evaluation and management regarding [____________________].\n\n{{tab}}Brief Clinical History: {{medical_history}}\n\n{{tab}}Kindly do the needful and revert back with your expert advice.\n\nThanking You,\nYours Sincerely,\n{{doctor}}"
            },
            {
                'id': 'blank',
                'name': 'General Letterpad / Note',
                'title': 'TO WHOM IT MAY CONCERN',
                'content': f"Patient Name: {{name}}\nAge/Gender: {{age}} yrs / {{gender}}\nDate: {{date}}\n\n{{tab}}Write content here using keys like {{name}}, {{age}}, {{doctor}}, {{date}}, {{phone}}, {{tab}}, etc."
            }
        ]

        data = {
            'patient': {
                'id': patient.id,
                'name': patient_full_name,
                'first_name': patient.first_name,
                'last_name': patient.last_name or '',
                'age': patient.age,
                'gender': patient.gender,
                'phone': patient.phone,
                'email': patient.email,
                'medical_history': patient.medical_history or '',
            },
            'clinic': {
                'name': clinic.clinic_name if clinic else 'Clinic Manager',
                'reg_no': clinic.reg_no if clinic else '',
                'phone': clinic.phone if clinic else '',
                'email': clinic.email if clinic else '',
                'address': clinic.address if clinic else '',
                'doctor_name': default_doctor_name,
                'doctor_specialist': clinic.doctor_specialist if clinic else '',
                'logo_url': clinic.logo.url if clinic and clinic.logo else '',
            },
            'doctors': doctors,
            'templates': templates,
            'history': history_data,
            'today_date': timezone.localtime().strftime("%b %d, %Y")
        }

        return JsonResponse({'success': True, 'data': data})


class LetterpadSaveView(LoginRequiredMixin, View):
    """Save or update a Letterpad in DB."""
    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8'))
            patient_id = body.get('patient_id')
            title = body.get('title', 'Medical Letter').strip()
            template_type = body.get('template_type', 'General').strip()
            content = body.get('content', '').strip()
            doctor_name = body.get('doctor_name', '').strip()
            border_style = body.get('border_style', 'dental_frame').strip()
            hide_header_val = body.get('hide_header', False)
            hide_header = hide_header_val == '1' or hide_header_val is True or str(hide_header_val).lower() == 'true'
            letterpad_id = body.get('letterpad_id')

            if not patient_id or not content:
                return JsonResponse({'success': False, 'error': 'Patient and content are required.'}, status=400)

            patient = get_object_or_404(Patient, pk=patient_id)
            clinic = ClinicInformation.objects.first()

            if not doctor_name:
                doctor_name = get_logged_in_doctor_name(request.user, clinic)

            if letterpad_id:
                lp = get_object_or_404(Letterpad, pk=letterpad_id, patient=patient)
                lp.title = title
                lp.template_type = template_type
                lp.content = content
                lp.doctor_name = doctor_name
                lp.border_style = border_style
                lp.hide_header = hide_header
                lp.save()
            else:
                lp = Letterpad.objects.create(
                    patient=patient,
                    title=title,
                    template_type=template_type,
                    content=content,
                    doctor_name=doctor_name,
                    border_style=border_style,
                    hide_header=hide_header,
                    created_by=request.user
                )

            return JsonResponse({
                'success': True,
                'message': 'Letterpad saved successfully.',
                'letterpad': {
                    'id': lp.id,
                    'title': lp.title,
                    'template_type': lp.template_type,
                    'content': lp.content,
                    'doctor_name': lp.doctor_name,
                    'border_style': lp.border_style,
                    'hide_header': lp.hide_header,
                    'created_by': request.user.username,
                    'created_at': lp.created_at.strftime("%b %d, %Y %I:%M %p")
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class LetterpadDeleteView(LoginRequiredMixin, View):
    """Delete a Letterpad from DB."""
    def post(self, request, letterpad_id):
        lp = get_object_or_404(Letterpad, pk=letterpad_id)
        lp.delete()
        return JsonResponse({'success': True, 'message': 'Letterpad deleted.'})


@method_decorator(xframe_options_exempt, name='dispatch')
class LetterpadPrintView(LoginRequiredMixin, View):
    """Render printable A4 Letterpad page."""
    def get(self, request, letterpad_id=None):
        clinic = ClinicInformation.objects.first()
        doctor_obj = None

        if letterpad_id:
            lp = get_object_or_404(Letterpad, pk=letterpad_id)
            patient = lp.patient
            title = lp.title
            doctor_name = lp.doctor_name
            content_raw = lp.content
            created_at = lp.created_at
            default_border = lp.border_style or 'dental_frame'
            default_hide_header = lp.hide_header
        else:
            # Query param mode or preview mode
            patient_id = request.GET.get('patient_id')
            patient = get_object_or_404(Patient, pk=patient_id) if patient_id else None
            title = request.GET.get('title', 'MEDICAL LETTER')
            doctor_name = request.GET.get('doctor_name', '')
            content_raw = request.GET.get('content', '')
            created_at = timezone.now()
            default_border = 'dental_frame'
            default_hide_header = False

        if not doctor_name:
            doctor_name = get_logged_in_doctor_name(request.user, clinic)

        if doctor_name:
            doctor_obj = Doctor.objects.filter(name__icontains=doctor_name).first()

        parsed_content = parse_letterpad_content(content_raw, patient, clinic, doctor_name, user=request.user) if patient else content_raw

        hide_header_param = request.GET.get('hide_header')
        if hide_header_param is not None:
            hide_header = hide_header_param == '1'
        else:
            hide_header = default_hide_header

        border_style = request.GET.get('border_style') or default_border
        preview_mode = request.GET.get('preview_mode') == '1'

        doc_info = get_doctor_details(request.user, doctor_name_override=doctor_name, clinic=clinic)

        context = {
            'clinic': clinic,
            'patient': patient,
            'title': title,
            'doctor_name': doc_info['name'],
            'doctor_education': doc_info['education'],
            'doctor_specialist': doc_info['specialization'] or (clinic.doctor_specialist if clinic else ''),
            'doctor_signature_url': doc_info['signature_url'],
            'doctor_obj': doctor_obj,
            'parsed_content': parsed_content,
            'hide_header': hide_header,
            'border_style': border_style,
            'preview_mode': preview_mode,
            'created_at': created_at,
            'date_formatted': created_at.strftime("%b %d, %Y") if created_at else timezone.now().strftime("%b %d, %Y"),
        }
        return render(request, 'letterpad_print.html', context)
