from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import csv
import io
import json

from app.models import BillingInvoice, DailyPatient, appoinments
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek, TruncYear
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView


def _format_inr(value):
    try:
        amount = Decimal(value or 0)
    except (TypeError, ValueError, InvalidOperation):
        amount = Decimal('0')

    amount = amount.quantize(Decimal('0.01'))
    sign = '-' if amount < 0 else ''
    whole, fraction = f'{abs(amount):.2f}'.split('.')

    if len(whole) > 3:
        prefix = whole[:-3]
        suffix = whole[-3:]
        groups = []
        while len(prefix) > 2:
            groups.insert(0, prefix[-2:])
            prefix = prefix[:-2]
        if prefix:
            groups.insert(0, prefix)
        whole = ','.join(groups + [suffix])

    return f'{sign}{whole}.{fraction}'


def _split_treatment_names(raw_value):
    if not raw_value:
        return []
    return [part.strip() for part in raw_value.replace('\n', ',').replace('|', ',').replace(';', ',').split(',') if part.strip()]


class ReportsAnalyticsMixin:
    period_labels = {
        'today': 'Today',
        'week': 'This Week',
        'month': 'This Month',
        'last_month': 'Last Month',
        'quarter': 'This Quarter',
        'year': 'This Year',
        'custom': 'Custom Range',
        'all': 'All Time',
    }

    def _period_key(self, request):
        period = (request.GET.get('period') or 'month').strip().lower()
        return period if period in self.period_labels else 'month'

    def _period_windows(self, period_key, request=None):
        today = timezone.localdate()

        if period_key == 'today':
            current_start_date = today
            current_end_date = today
        elif period_key == 'week':
            weekday = today.weekday()
            current_start_date = today - timedelta(days=weekday)
            current_end_date = current_start_date + timedelta(days=6)
        elif period_key == 'last_month':
            current_end_date = today.replace(day=1) - timedelta(days=1)
            current_start_date = current_end_date.replace(day=1)
        elif period_key == 'quarter':
            start_month = ((today.month - 1) // 3) * 3 + 1
            current_start_date = date(today.year, start_month, 1)
            current_end_date = today
        elif period_key == 'year':
            current_start_date = date(today.year, 1, 1)
            current_end_date = today
        elif period_key == 'custom' and request:
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')
            if start_date_str and end_date_str:
                try:
                    current_start_date = date.fromisoformat(start_date_str)
                    current_end_date = date.fromisoformat(end_date_str)
                except ValueError:
                    current_start_date = today.replace(day=1)
                    current_end_date = today
            else:
                current_start_date = today.replace(day=1)
                current_end_date = today
        elif period_key == 'all':
            # Find the earliest date from available data
            min_dates = []
            if BillingInvoice.objects.filter(status=BillingInvoice.STATUS_PAID).exists():
                min_dates.append(BillingInvoice.objects.filter(status=BillingInvoice.STATUS_PAID).earliest('paid_at').paid_at.date())
            if DailyPatient.objects.exists():
                min_dates.append(DailyPatient.objects.earliest('date').date.date())
            if appoinments.objects.exists():
                min_dates.append(appoinments.objects.earliest('date').date)
            if min_dates:
                current_start_date = min(min_dates)
            else:
                current_start_date = date(today.year - 1, 1, 1)  # fallback
            current_end_date = today
        else:
            current_start_date = today.replace(day=1)
            current_end_date = today

        span_days = (current_end_date - current_start_date).days + 1
        previous_end_date = current_start_date - timedelta(days=1)
        previous_start_date = previous_end_date - timedelta(days=span_days - 1)

        current_start_dt = timezone.make_aware(datetime.combine(current_start_date, time.min))
        current_end_dt = timezone.make_aware(datetime.combine(current_end_date + timedelta(days=1), time.min))
        previous_start_dt = timezone.make_aware(datetime.combine(previous_start_date, time.min))
        previous_end_dt = timezone.make_aware(datetime.combine(previous_end_date + timedelta(days=1), time.min))

        return {
            'current_start_date': current_start_date,
            'current_end_date': current_end_date,
            'current_start_dt': current_start_dt,
            'current_end_dt': current_end_dt,
            'previous_start_date': previous_start_date,
            'previous_end_date': previous_end_date,
            'previous_start_dt': previous_start_dt,
            'previous_end_dt': previous_end_dt,
            'span_days': span_days,
        }

    def _period_label(self, period_key):
        return self.period_labels.get(period_key, self.period_labels['month'])

    def _bucket_unit(self, period_key):
        if period_key in {'today', 'week', 'month', 'last_month', 'custom'}:
            return 'day'
        if period_key == 'quarter':
            return 'week'
        if period_key == 'all':
            return 'year'
        return 'month'

    def _previous_group_key(self, period_key):
        return 'month' if period_key == 'quarter' else 'day'

    def _comparison_growth(self, current_value, previous_value):
        current = float(current_value or 0)
        previous = float(previous_value or 0)
        if previous == 0:
            if current == 0:
                return 0.0, '0%'
            return 100.0, '+100%'

        percentage = ((current - previous) / previous) * 100
        sign = '+' if percentage >= 0 else ''
        return percentage, f'{sign}{percentage:.1f}%'

    def _group_dates(self, start_date, end_date, bucket_unit):
        dates = []
        if bucket_unit == 'day':
            current = start_date
            while current <= end_date:
                dates.append(current)
                current += timedelta(days=1)
        elif bucket_unit == 'week':
            current = start_date - timedelta(days=start_date.weekday())
            while current <= end_date:
                dates.append(current)
                current += timedelta(days=7)
        elif bucket_unit == 'year':
            current = date(start_date.year, 1, 1)
            while current <= end_date:
                dates.append(current)
                current = date(current.year + 1, 1, 1)
        else:
            current = date(start_date.year, start_date.month, 1)
            while current <= end_date:
                dates.append(current)
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)
        return dates

    def _group_label(self, value, bucket_unit):
        if bucket_unit == 'month':
            return value.strftime('%b %Y')
        if bucket_unit == 'year':
            return value.strftime('%Y')
        return value.strftime('%d %b')

    def _series_from_queryset(self, queryset, field_name, start_date, end_date, bucket_unit, is_datetime=False):
        trunc_map = {
            'day': TruncDay,
            'week': TruncWeek,
            'month': TruncMonth,
            'year': TruncYear,
        }
        rows = (
            queryset.annotate(bucket=trunc_map[bucket_unit](field_name))
            .values('bucket')
            .annotate(total=Count('id'))
            .order_by('bucket')
        )

        totals = {}
        for row in rows:
            bucket_value = row['bucket']
            if hasattr(bucket_value, 'date'):
                bucket_key = bucket_value.date()
            else:
                bucket_key = bucket_value
            totals[bucket_key] = row['total']

        bucket_dates = self._group_dates(start_date, end_date, bucket_unit)
        labels = [self._group_label(bucket_date, bucket_unit) for bucket_date in bucket_dates]
        values = [int(totals.get(bucket_date, 0)) for bucket_date in bucket_dates]
        return labels, values

    def _treatment_analysis(self, start_dt, end_dt):
        daily_patients = DailyPatient.objects.filter(date__gte=start_dt, date__lt=end_dt)
        treatment_counter = Counter()
        for raw_treatments in daily_patients.values_list('treatments', flat=True):
            treatment_counter.update(_split_treatment_names(raw_treatments))

        treatment_revenue_rows = (
            BillingInvoice.objects.filter(
                status=BillingInvoice.STATUS_PAID,
                paid_at__gte=start_dt,
                paid_at__lt=end_dt,
            )
            .exclude(treatment__isnull=True)
            .exclude(treatment='')
            .values('treatment')
            .annotate(total=Sum('amount'), count=Count('id'))
        )
        treatment_revenue_map = {
            row['treatment']: float(row['total'] or 0)
            for row in treatment_revenue_rows
        }

        top_treatments = []
        for name, count in treatment_counter.most_common(6):
            revenue_amount = treatment_revenue_map.get(name, 0.0)
            top_treatments.append({
                'name': name,
                'count': int(count),
                'revenue': revenue_amount,
                'revenue_display': _format_inr(revenue_amount),
            })

        if not top_treatments:
            top_treatments = [{
                'name': 'No treatment data',
                'count': 0,
                'revenue': 0.0,
                'revenue_display': '0.00',
            }]

        return top_treatments, int(sum(treatment_counter.values()))

    def _doctor_revenue_analysis(self, start_dt, end_dt):
        rows = (
            BillingInvoice.objects.filter(
                status=BillingInvoice.STATUS_PAID,
                paid_at__gte=start_dt,
                paid_at__lt=end_dt,
            )
            .exclude(doctor__isnull=True)
            .exclude(doctor='')
            .values('doctor')
            .annotate(total=Sum('amount'), count=Count('id'))
            .order_by('-total', 'doctor')[:6]
        )

        doctor_revenue = []
        for row in rows:
            revenue_amount = float(row['total'] or 0)
            doctor_revenue.append({
                'doctor': row['doctor'],
                'count': int(row['count'] or 0),
                'revenue': revenue_amount,
                'revenue_display': _format_inr(revenue_amount),
            })

        if not doctor_revenue:
            doctor_revenue = [{
                'doctor': 'No doctor data',
                'count': 0,
                'revenue': 0.0,
                'revenue_display': '0.00',
            }]

        return doctor_revenue

    def build_reports_payload(self, period_key, request=None):
        windows = self._period_windows(period_key, request)
        bucket_unit = self._bucket_unit(period_key)

        current_paid_invoices = BillingInvoice.objects.filter(
            status=BillingInvoice.STATUS_PAID,
            paid_at__gte=windows['current_start_dt'],
            paid_at__lt=windows['current_end_dt'],
        )
        previous_paid_invoices = BillingInvoice.objects.filter(
            status=BillingInvoice.STATUS_PAID,
            paid_at__gte=windows['previous_start_dt'],
            paid_at__lt=windows['previous_end_dt'],
        )

        current_revenue = current_paid_invoices.aggregate(total=Sum('amount')).get('total') or Decimal('0')
        previous_revenue = previous_paid_invoices.aggregate(total=Sum('amount')).get('total') or Decimal('0')
        revenue_growth_pct, revenue_growth_display = self._comparison_growth(current_revenue, previous_revenue)

        current_total_invoices = BillingInvoice.objects.filter(
            bill_date__gte=windows['current_start_dt'],
            bill_date__lt=windows['current_end_dt'],
        )
        current_total_invoice_count = current_total_invoices.count()
        current_paid_count = current_paid_invoices.count()
        current_pending_count = current_total_invoices.filter(status=BillingInvoice.STATUS_PENDING).count()
        collection_rate = (current_paid_count / current_total_invoice_count * 100) if current_total_invoice_count else 0.0
        average_invoice = float(current_revenue) / current_paid_count if current_paid_count else 0.0

        current_patients = DailyPatient.objects.filter(
            date__gte=windows['current_start_dt'],
            date__lt=windows['current_end_dt'],
        )
        previous_patients = DailyPatient.objects.filter(
            date__gte=windows['previous_start_dt'],
            date__lt=windows['previous_end_dt'],
        )
        current_patient_count = current_patients.count()
        previous_patient_count = previous_patients.count()
        patient_growth_pct, patient_growth_display = self._comparison_growth(current_patient_count, previous_patient_count)

        current_appointments = appoinments.objects.filter(
            date__gte=windows['current_start_date'],
            date__lte=windows['current_end_date'],
        )
        previous_appointments = appoinments.objects.filter(
            date__gte=windows['previous_start_date'],
            date__lte=windows['previous_end_date'],
        )
        current_appointment_count = current_appointments.count()
        previous_appointment_count = previous_appointments.count()
        appointment_growth_pct, appointment_growth_display = self._comparison_growth(current_appointment_count, previous_appointment_count)

        patient_growth_labels, patient_growth_values = self._series_from_queryset(
            current_patients,
            'date',
            windows['current_start_date'],
            windows['current_end_date'],
            bucket_unit,
            is_datetime=True,
        )
        appointment_trends_labels, appointment_trends_values = self._series_from_queryset(
            current_appointments,
            'date',
            windows['current_start_date'],
            windows['current_end_date'],
            bucket_unit,
        )

        # For 'all' period, filter out years with no data
        if period_key == 'all':
            # Filter patient growth
            filtered_patient_labels = []
            filtered_patient_values = []
            for l, v in zip(patient_growth_labels, patient_growth_values):
                if v > 0:
                    filtered_patient_labels.append(l)
                    filtered_patient_values.append(v)
            patient_growth_labels = filtered_patient_labels
            patient_growth_values = filtered_patient_values

            # Filter appointment trends
            filtered_appointment_labels = []
            filtered_appointment_values = []
            for l, v in zip(appointment_trends_labels, appointment_trends_values):
                if v > 0:
                    filtered_appointment_labels.append(l)
                    filtered_appointment_values.append(v)
            appointment_trends_labels = filtered_appointment_labels
            appointment_trends_values = filtered_appointment_values

        top_treatments, treatment_volume = self._treatment_analysis(windows['current_start_dt'], windows['current_end_dt'])
        doctor_revenue = self._doctor_revenue_analysis(windows['current_start_dt'], windows['current_end_dt'])

        period_label = self._period_label(period_key)

        return {
            'reports_period': period_key,
            'reports_period_label': period_label,
            'period_bucket_unit': bucket_unit,
            'total_revenue': float(current_revenue),
            'total_revenue_display': _format_inr(current_revenue),
            'revenue_growth_pct': round(float(revenue_growth_pct), 1),
            'revenue_growth_display': revenue_growth_display,
            'revenue_growth_class': 'text-green-600 bg-green-50' if revenue_growth_pct >= 0 else 'text-red-600 bg-red-50',
            'paid_invoice_count': current_paid_count,
            'pending_invoice_count': current_pending_count,
            'new_patient_count': current_patient_count,
            'patient_growth_pct': round(float(patient_growth_pct), 1),
            'patient_growth_display': patient_growth_display,
            'patient_growth_class': 'text-green-600 bg-green-50' if patient_growth_pct >= 0 else 'text-red-600 bg-red-50',
            'appointment_count': current_appointment_count,
            'appointment_growth_pct': round(float(appointment_growth_pct), 1),
            'appointment_growth_display': appointment_growth_display,
            'appointment_growth_class': 'text-green-600 bg-green-50' if appointment_growth_pct >= 0 else 'text-red-600 bg-red-50',
            'collection_rate': round(float(collection_rate), 1),
            'collection_rate_display': f'{collection_rate:.1f}%',
            'average_invoice_display': _format_inr(average_invoice),
            'patient_growth_labels': patient_growth_labels,
            'patient_growth_values': patient_growth_values,
            'appointment_trends_labels': appointment_trends_labels,
            'appointment_trends_values': appointment_trends_values,
            'top_treatments': top_treatments,
            'doctor_revenue': doctor_revenue,
            'treatment_volume': treatment_volume,
        }


class ReportsPartialView(LoginRequiredMixin, ReportsAnalyticsMixin, TemplateView):
    template_name = 'partials/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period_key = self._period_key(self.request)
        payload = self.build_reports_payload(period_key, self.request)
        context.update(payload)
        context.update({
            'patient_growth_labels_json': json.dumps(payload['patient_growth_labels']),
            'patient_growth_values_json': json.dumps(payload['patient_growth_values']),
            'appointment_trends_labels_json': json.dumps(payload['appointment_trends_labels']),
            'appointment_trends_values_json': json.dumps(payload['appointment_trends_values']),
            'top_treatments_json': json.dumps(payload['top_treatments']),
            'doctor_revenue_json': json.dumps(payload['doctor_revenue']),
        })
        return context


class ReportsDataView(LoginRequiredMixin, ReportsAnalyticsMixin, View):
    def get(self, request, *args, **kwargs):
        payload = self.build_reports_payload(self._period_key(request), request)
        return JsonResponse(payload)


class ReportsExportView(LoginRequiredMixin, ReportsAnalyticsMixin, View):
    def get(self, request, *args, **kwargs):
        period_key = self._period_key(request)
        payload = self.build_reports_payload(period_key, request)
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        safe_period = period_key.replace(' ', '_')
        response['Content-Disposition'] = f'attachment; filename="reports-{safe_period}.csv"'

        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(['Reports Summary'])
        writer.writerow(['Period', payload['reports_period_label']])
        writer.writerow(['Total Revenue', payload['total_revenue_display']])
        writer.writerow(['Revenue Growth', payload['revenue_growth_display']])
        writer.writerow(['Paid Invoices', payload['paid_invoice_count']])
        writer.writerow(['Pending Invoices', payload['pending_invoice_count']])
        writer.writerow(['New Patients', payload['new_patient_count']])
        writer.writerow(['Patient Growth', payload['patient_growth_display']])
        writer.writerow(['Appointments', payload['appointment_count']])
        writer.writerow(['Appointment Growth', payload['appointment_growth_display']])
        writer.writerow(['Collection Rate', payload['collection_rate_display']])
        writer.writerow(['Average Invoice', payload['average_invoice_display']])
        writer.writerow([])

        writer.writerow(['Patient Growth Series'])
        writer.writerow(['Label', 'Count'])
        for label, value in zip(payload['patient_growth_labels'], payload['patient_growth_values']):
            writer.writerow([label, value])
        writer.writerow([])

        writer.writerow(['Appointment Trends'])
        writer.writerow(['Label', 'Count'])
        for label, value in zip(payload['appointment_trends_labels'], payload['appointment_trends_values']):
            writer.writerow([label, value])
        writer.writerow([])

        writer.writerow(['Top Treatments'])
        writer.writerow(['Name', 'Procedures', 'Revenue'])
        for item in payload['top_treatments']:
            writer.writerow([item['name'], item['count'], item['revenue_display']])
        writer.writerow([])

        writer.writerow(['Revenue by Doctor'])
        writer.writerow(['Doctor', 'Invoices', 'Revenue'])
        for item in payload['doctor_revenue']:
            writer.writerow([item['doctor'], item['count'], item['revenue_display']])

        response.write(buffer.getvalue())
        return response
