import json
import re
from decimal import Decimal, InvalidOperation

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt

from .models import BillingInvoice, DailyPatient, Treatment, Doctor, ClinicInformation, Patient


def _money(value):
    value = value or Decimal('0')
    try:
        return f"{Decimal(value):,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"


def _base_billing_queryset():
    return BillingInvoice.objects.select_related('patient', 'daily_patient').order_by('-bill_date', '-id')


def _billing_metrics_context():
    now = timezone.localtime()
    today = now.date()

    paid_today = (
        BillingInvoice.objects.filter(status=BillingInvoice.STATUS_PAID, paid_at__date=today)
        .aggregate(total=Sum('amount'))
        .get('total')
    )
    paid_this_month = (
        BillingInvoice.objects.filter(
            status=BillingInvoice.STATUS_PAID,
            paid_at__year=today.year,
            paid_at__month=today.month,
        )
        .aggregate(total=Sum('amount'))
        .get('total')
    )
    unpaid_total = (
        BillingInvoice.objects.filter(status=BillingInvoice.STATUS_PENDING)
        .aggregate(total=Sum('amount'))
        .get('total')
    )

    return {
        'today_revenue': paid_today or Decimal('0'),
        'month_revenue': paid_this_month or Decimal('0'),
        'unpaid_total': unpaid_total or Decimal('0'),
        'today_revenue_label': _money(paid_today),
        'month_revenue_label': _money(paid_this_month),
        'unpaid_total_label': _money(unpaid_total),
    }


def _calendar_dates_json():
    values = list(
        BillingInvoice.objects.annotate(d=TruncDate('bill_date'))
        .values_list('d', flat=True)
        .distinct()
    )
    iso_dates = [d.isoformat() for d in values if d]
    return json.dumps(iso_dates)


def _billing_calendar_data_json():
    """Generate billing calendar data grouped by date with status counts"""
    calendar_data = {}
    invoices = BillingInvoice.objects.all().order_by('bill_date')
    
    for invoice in invoices:
        date_str = invoice.bill_date.date().isoformat()
        if date_str not in calendar_data:
            calendar_data[date_str] = {
                'total': 0,
                'paid': 0,
                'pending': 0
            }
        
        calendar_data[date_str]['total'] += 1
        
        status = invoice.status.lower() if invoice.status else 'pending'
        if status == 'paid':
            calendar_data[date_str]['paid'] += 1
        elif status == 'pending':
            calendar_data[date_str]['pending'] += 1
    
    return json.dumps(calendar_data)


def _split_treatment_names(raw_value):
    if not raw_value:
        return []
    return [part.strip() for part in re.split(r'[;,]+', raw_value) if part.strip()]


def _doctor_display_name(raw_name):
    name = (raw_name or '').strip()
    if not name:
        return ''
    if name.lower().startswith('dr.') or name.lower().startswith('dr '):
        return name
    return f"Dr. {name}"


def _render_billing_data(request, trigger_message=None, trigger_type='success', closemodel=''):
    qs = _base_billing_queryset()

    doctor = request.GET.get('doctor', '').strip()
    status = request.GET.get('status', '').strip()
    treatment = request.GET.get('treatment', '').strip()
    q_date = request.GET.get('date', '').strip()

    try:
        page_number = int(request.GET.get('page', 1))
    except (TypeError, ValueError):
        page_number = 1

    # Apply all filters first
    if q_date:
        try:
            q_date_obj = timezone.datetime.strptime(q_date, '%Y-%m-%d').date()
            qs = qs.filter(bill_date__date=q_date_obj)
        except ValueError:
            qs = BillingInvoice.objects.none()

    if doctor and doctor.lower() != 'all':
        qs = qs.filter(doctor__icontains=doctor)
    
    if status and status.lower() != 'all':
        qs = qs.filter(status__iexact=status)
    
    if treatment and treatment.lower() != 'all':
        qs = qs.filter(treatment__icontains=treatment)

    # Get pagination info
    total_count = qs.count()
    per_page = 10
    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
    
    if page_number < 1:
        page_number = 1
    if page_number > total_pages:
        page_number = total_pages

    # Apply pagination
    start_idx = (page_number - 1) * per_page
    end_idx = start_idx + per_page
    page_qs = qs[start_idx:end_idx]

    context = {
        'invoices': page_qs,
        'has_previous': page_number > 1,
        'has_next': page_number < total_pages,
        'previous_page_number': page_number - 1 if page_number > 1 else None,
        'next_page_number': page_number + 1 if page_number < total_pages else None,
        'total_count': total_count,
        'current_page': page_number,
        'per_page': per_page,
    }
    response = render(request, 'ext/billing_data.html', context)

    if trigger_message:
        response['HX-Trigger'] = json.dumps({
            'showNotification': {
                'message': trigger_message,
                'type': trigger_type,
                'duration': 3500,
                'closemodel': closemodel,
            }
        })
    return response


class BillingPartialView(LoginRequiredMixin, TemplateView):
    template_name = 'partials/billing.html'

    def get(self, request, *args, **kwargs):
        context = {
            'treatment': Treatment.objects.all(),
            'doctors': Doctor.objects.all(),
            'clinic': ClinicInformation.objects.first(),
            'today_patients': DailyPatient.objects.select_related('patient').order_by('-date')[:300],
            'billing_calendar_dates_json': _calendar_dates_json(),
            'billing_calendar_data_json': _billing_calendar_data_json(),
        }
        context.update(_billing_metrics_context())
        return render(request, self.template_name, context)


class BillingDataView(LoginRequiredMixin, TemplateView):
    template_name = 'ext/billing_data.html'

    def get(self, request, *args, **kwargs):
        return _render_billing_data(request)


class BillingCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        daily_patient_id = (request.POST.get('daily_patient_id') or '').strip()
        patient_id = (request.POST.get('patient_id') or '').strip()
        treatment = (request.POST.get('treatment') or '').strip()
        doctor = (request.POST.get('doctor') or '').strip()
        note = (request.POST.get('note') or '').strip()
        amount_raw = (request.POST.get('amount') or '').strip()
        bill_date_raw = (request.POST.get('bill_date') or '').strip()

        if not amount_raw:
            return _render_billing_data(request, 'Amount is required', 'error')

        try:
            amount = Decimal(amount_raw)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            return _render_billing_data(request, 'Amount must be a valid positive number', 'error')

        daily_patient = None
        patient = None

        if daily_patient_id:
            try:
                daily_patient = DailyPatient.objects.select_related('patient').get(pk=int(daily_patient_id))
                patient = daily_patient.patient
            except (DailyPatient.DoesNotExist, ValueError):
                return _render_billing_data(request, 'Selected today patient not found', 'error')
        elif patient_id:
            try:
                patient = Patient.objects.get(pk=int(patient_id))
            except (Patient.DoesNotExist, ValueError):
                return _render_billing_data(request, 'Selected patient not found', 'error')
        else:
            return _render_billing_data(request, 'Please select a patient', 'error')

        bill_date = timezone.now()
        if bill_date_raw:
            try:
                parsed = timezone.datetime.strptime(bill_date_raw, '%Y-%m-%d')
                bill_date = timezone.make_aware(parsed)
            except ValueError:
                return _render_billing_data(request, 'Invalid bill date format', 'error')

        if daily_patient:
            treatment = treatment or (daily_patient.treatments or '')
            doctor = doctor or (daily_patient.doctor or '')

        BillingInvoice.objects.create(
            patient=patient,
            daily_patient=daily_patient,
            treatment=treatment or None,
            doctor=doctor or None,
            amount=amount,
            note=note or None,
            bill_date=bill_date,
            status=BillingInvoice.STATUS_PENDING,
            created_by=request.user if request.user.is_authenticated else None,
        )

        return _render_billing_data(
            request,
            trigger_message='Invoice created successfully',
            trigger_type='success',
            closemodel='createBillModal',
        )


class BillingMarkPaidView(LoginRequiredMixin, View):
    def post(self, request, invoice_id, *args, **kwargs):
        invoice = get_object_or_404(BillingInvoice, pk=invoice_id)
        if invoice.status == BillingInvoice.STATUS_PAID:
            return _render_billing_data(request, 'Invoice is already paid', 'info')

        invoice.status = BillingInvoice.STATUS_PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=['status', 'paid_at', 'updated_at'])

        return _render_billing_data(request, 'Invoice marked as paid', 'success')


@method_decorator(xframe_options_exempt, name='dispatch')
class BillingA4View(LoginRequiredMixin, TemplateView):
    template_name = 'ext/billing_invoice_a4.html'

    def get(self, request, invoice_id, *args, **kwargs):
        invoice = get_object_or_404(
            BillingInvoice.objects.select_related('patient', 'daily_patient'),
            pk=invoice_id,
        )

        clinic = ClinicInformation.objects.first()
        treatment_names = _split_treatment_names(invoice.treatment)
        matched_treatments = list(Treatment.objects.filter(Treatment_name__in=treatment_names))
        treatment_description = ' | '.join(
            [t.Description for t in matched_treatments if getattr(t, 'Description', None)]
        )

        # Get prescription treatments with tooth numbers and payment status
        prescription_treatments = []
        if invoice.daily_patient and invoice.daily_patient.prescription:
            last_prescription = invoice.daily_patient.prescription
            if last_prescription:
                prescription_treatments = list(
                    last_prescription.treatments.all().values(
                        'treatment_name', 'tooth_number', 'is_paid'
                    )
                )

        doctor_obj = None
        raw_doctor = (invoice.doctor or '').strip()
        if raw_doctor:
            normalized = re.sub(r'^dr\.?\s*', '', raw_doctor, flags=re.IGNORECASE).strip()
            doctor_obj = Doctor.objects.filter(name__iexact=normalized).first()

        context = {
            'invoice': invoice,
            'clinic': clinic,
            'generated_at': timezone.localtime(),
            'doctor_display_name': _doctor_display_name(raw_doctor or (clinic.doctor_name if clinic else '')),
            'doctor_education': (doctor_obj.education if doctor_obj else ''),
            'doctor_specialization': (
                doctor_obj.specialization if doctor_obj else (clinic.doctor_specialist if clinic else '')
            ),
            'doctor_signature': doctor_obj,
            'treatment_description': treatment_description,
            'prescription_treatments': prescription_treatments,
        }
        return render(request, self.template_name, context)

