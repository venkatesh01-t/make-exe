from collections import Counter
from calendar import month_abbr, monthrange
import re
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from app.models import BillingInvoice, ClinicInformation, DailyPatient, Doctor, appoinments
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import  render
from django.urls import reverse
from django.db.models import Sum
from django.db.models.functions import TruncDay, TruncHour, TruncMonth
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
import json
from django.views.decorators.csrf import csrf_exempt

# --------------------------
# Error Handlers
# --------------------------
def page_not_found(request, exception=None):
    """Custom 404 handler"""
    from .models import ClinicInformation
    try:
        clinic = ClinicInformation.objects.first()
    except:
        clinic = None
    context = {'clinic': clinic}
    return render(request, '404.html', context, status=404)

def server_error(request, exception=None):
    """Custom 500 handler"""
    from .models import ClinicInformation
    try:
        clinic = ClinicInformation.objects.first()
    except:
        clinic = None
    context = {'clinic': clinic}
    return render(request, '500.html', context, status=500)

def test_404_page(request):
    """Test view to see 404 page during development"""
    raise Http404("Test 404 page")

def test_500_page(request):
    """Test view to see 500 page during development"""
    raise Exception("Test 500 error")

def clinic_debug(request):
    """Debug view to check clinic data"""
    from .models import ClinicInformation
    try:
        clinic = ClinicInformation.objects.first()
        if clinic:
            data = {
                'status': 'Clinic found',
                'clinic_name': clinic.clinic_name,
                'clinic_id': clinic.id,
                'has_logo': bool(clinic.logo),
                'logo_path': str(clinic.logo) if clinic.logo else 'No logo',
                'logo_url': clinic.logo.url if clinic.logo else 'N/A',
                'phone': clinic.phone or 'No phone',
                'email': clinic.email or 'No email',
            }
        else:
            data = {
                'status': 'No clinic found in database',
                'instruction': 'Create a clinic record in Django admin: /admin/app/clinicinformation/',
                'all_clinics': list(ClinicInformation.objects.all().values())
            }
    except Exception as e:
        data = {'error': str(e)}
    
    return JsonResponse(data)

# --------------------------
# Error Handlers
# --------------------------
class CustomLogoutView(TemplateView):
    def post(self, request):
        logout(request)
        response = HttpResponse()
        response["HX-Redirect"] = reverse("clinic:htmx_login")
        return response

    def get(self, request):
        if request.user.is_authenticated:
            return TemplateView.as_view(template_name="base.html")(request)
        else:
            return TemplateView.as_view(template_name="login.html")(request)
        

class HtmxLoginView(TemplateView):
    
    @csrf_exempt
    def get(self, request):
        if request.user.is_authenticated:
            return TemplateView.as_view(template_name="base.html")(request)
        else:
            return TemplateView.as_view(template_name="login.html")(request)
        
    @csrf_exempt    
    def post(self, request):
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            response = HttpResponse()
            response["HX-Redirect"] = reverse("clinic:index")
            
            return response
        else:
            response = HttpResponse("Invalid email or password")
            response["HX-Retarget"] = "#email-error-text"
            response["HX-Reswap"] = "innerHTML"
            response["HX-Trigger"] = "loginFailed"
            response["HX-Trigger"] = json.dumps({
                    "showNotification": {
                        "message": f"Login failed ",
                        "type": "error",
                        "duration": 4000,
                        "closemodel":""
                    }
                })
            return response


# --------------------------6
# Template-only Views
# --------------------------
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
    return [part.strip() for part in re.split(r'[;,|\n]+', raw_value) if part.strip()]


def _yearly_revenue_series(year):
    monthly_totals = {month: Decimal('0') for month in range(1, 13)}
    rows = (
        BillingInvoice.objects.filter(status=BillingInvoice.STATUS_PAID, paid_at__year=year)
        .annotate(month_bucket=TruncMonth('paid_at'))
        .values('month_bucket')
        .annotate(total=Sum('amount'))
        .order_by('month_bucket')
    )

    for row in rows:
        month_bucket = row.get('month_bucket')
        if month_bucket:
            monthly_totals[month_bucket.month] = row.get('total') or Decimal('0')

    return [float(monthly_totals[month]) for month in range(1, 13)]


def _year_revenue_title(year, reference_date):
    if year == reference_date.year:
        return f'This Year ({year})'
    if year == reference_date.year - 1:
        return f'Last Year ({year})'
    return f'Year {year}'


def _monthly_revenue_series(year, month):
    days_in_month = monthrange(year, month)[1]
    daily_totals = {day: Decimal('0') for day in range(1, days_in_month + 1)}
    rows = (
        BillingInvoice.objects.filter(status=BillingInvoice.STATUS_PAID, paid_at__year=year, paid_at__month=month)
        .annotate(day_bucket=TruncDay('paid_at'))
        .values('day_bucket')
        .annotate(total=Sum('amount'))
        .order_by('day_bucket')
    )

    for row in rows:
        day_bucket = row.get('day_bucket')
        if day_bucket:
            daily_totals[day_bucket.day] = row.get('total') or Decimal('0')

    return [float(daily_totals[day]) for day in range(1, days_in_month + 1)]


def _month_revenue_title(year, month, reference_date):
    if year == reference_date.year and month == reference_date.month:
        return f'This Month ({month_abbr[month]} {year})'

    previous_month = reference_date.replace(day=1) - timedelta(days=1)
    if year == previous_month.year and month == previous_month.month:
        return f'Last Month ({month_abbr[month]} {year})'

    return f'{month_abbr[month]} {year}'


def _daily_revenue_series(day_date):
    hourly_totals = {hour: Decimal('0') for hour in range(24)}
    rows = (
        BillingInvoice.objects.filter(status=BillingInvoice.STATUS_PAID, paid_at__date=day_date)
        .annotate(hour_bucket=TruncHour('paid_at'))
        .values('hour_bucket')
        .annotate(total=Sum('amount'))
        .order_by('hour_bucket')
    )

    for row in rows:
        hour_bucket = row.get('hour_bucket')
        if hour_bucket:
            hourly_totals[hour_bucket.hour] = row.get('total') or Decimal('0')

    labels = []
    values = []
    for hour in range(24):
        display_hour = hour % 12 or 12
        suffix = 'AM' if hour < 12 else 'PM'
        labels.append(f'{display_hour} {suffix}')
        values.append(float(hourly_totals[hour]))

    return labels, values


def _today_revenue_title(day_date):
    return f'Today ({day_date.strftime("%d %b %Y")})'


def _dashboard_revenue_series_map(base_year, reference_date):
    previous_month = reference_date.replace(day=1) - timedelta(days=1)
    current_year_series = {
        'title': _year_revenue_title(base_year, reference_date),
        'labels': [month_abbr[index] for index in range(1, 13)],
        'values': _yearly_revenue_series(base_year),
    }
    previous_year = base_year - 1
    previous_year_series = {
        'title': _year_revenue_title(previous_year, reference_date),
        'labels': [month_abbr[index] for index in range(1, 13)],
        'values': _yearly_revenue_series(previous_year),
    }
    this_month_series = {
        'title': _month_revenue_title(reference_date.year, reference_date.month, reference_date),
        'labels': [str(day) for day in range(1, monthrange(reference_date.year, reference_date.month)[1] + 1)],
        'values': _monthly_revenue_series(reference_date.year, reference_date.month),
    }
    last_month_series = {
        'title': _month_revenue_title(previous_month.year, previous_month.month, reference_date),
        'labels': [str(day) for day in range(1, monthrange(previous_month.year, previous_month.month)[1] + 1)],
        'values': _monthly_revenue_series(previous_month.year, previous_month.month),
    }
    today_labels, today_values = _daily_revenue_series(reference_date)
    today_series = {
        'title': _today_revenue_title(reference_date),
        'labels': today_labels,
        'values': today_values,
    }

    return {
        str(base_year): current_year_series,
        str(previous_year): previous_year_series,
        'this_month': this_month_series,
        'last_month': last_month_series,
        'today': today_series,
    }


def _normalize_dashboard_revenue_selection(selection_raw, reference_date):
    selection = str(selection_raw or '').strip().lower()
    if not selection:
        return str(reference_date.year)
    if selection in {'this_month', 'last_month', 'today'}:
        return selection
    try:
        return str(int(selection))
    except (TypeError, ValueError):
        return str(reference_date.year)


def _daily_patient_treatment_analysis():
    daily_patients = DailyPatient.objects.all()
    treatment_counter = Counter()

    for raw_treatments in daily_patients.values_list('treatments', flat=True):
        treatment_counter.update(_split_treatment_names(raw_treatments))

    treatment_pairs = treatment_counter.most_common(6)
    if not treatment_pairs:
        treatment_pairs = [('No treatment data', 1)]

    return {
        'daily_patient_count': daily_patients.count(),
        'daily_treatment_total': sum(treatment_counter.values()),
        'daily_treatment_labels': [label for label, _ in treatment_pairs],
        'daily_treatment_values': [count for _, count in treatment_pairs],
        'top_treatment_name': treatment_pairs[0][0],
    }


def _dashboard_chart_payload(selection_raw):
    reference_date = timezone.localdate()
    selected_key = _normalize_dashboard_revenue_selection(selection_raw, reference_date)
    base_year = int(selected_key) if selected_key.isdigit() else reference_date.year
    previous_year = base_year - 1
    revenue_series_map = _dashboard_revenue_series_map(base_year, reference_date)
    active_series = revenue_series_map.get(selected_key) or revenue_series_map[str(base_year)]
    treatment_analysis = _daily_patient_treatment_analysis()

    return {
        'revenue_chart_year': base_year,
        'revenue_chart_previous_year': previous_year,
        'revenue_chart_default_key': str(base_year),
        'revenue_chart_selected_key': selected_key,
        'revenue_chart_title': active_series['title'],
        'revenue_chart_labels': active_series['labels'],
        'revenue_chart_data_map': revenue_series_map,
        'daily_treatment_labels': treatment_analysis['daily_treatment_labels'],
        'daily_treatment_values': treatment_analysis['daily_treatment_values'],
        'daily_patient_count': treatment_analysis['daily_patient_count'],
        'daily_treatment_total': treatment_analysis['daily_treatment_total'],
        'top_treatment_name': treatment_analysis['top_treatment_name'],
    }


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = 'base.html'
    def get(self, request):
        ClinicInformationdata=ClinicInformation.objects.first()  # ensure clinic info exists for sidebar display
        return render(request, self.template_name, {"clinic": ClinicInformationdata,"appoinment":appoinments.objects.count()})

# --------------------------
class DashboardPartialView(LoginRequiredMixin, TemplateView):
    template_name = 'partials/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        app = appoinments.objects.all()
        monthly_paid_total = (
            BillingInvoice.objects.filter(
                status=BillingInvoice.STATUS_PAID,
                paid_at__year=today.year,
                paid_at__month=today.month,
            ).aggregate(total=Sum('amount')).get('total')
            or Decimal('0')
        )

        chart_context = _dashboard_chart_payload(today.year)

        context.update({
            'appointments_today': app.filter(date=today).count(),
            'total_patients': app,
            'monthly_revenue': _format_inr(monthly_paid_total),
            'pending_bills': BillingInvoice.objects.filter(status=BillingInvoice.STATUS_PENDING).count(),
            'appoments': app.filter(date=today),
            'doctor': Doctor.objects.all(),
            'revenue_chart_year': chart_context['revenue_chart_year'],
            'revenue_chart_previous_year': chart_context['revenue_chart_previous_year'],
            'revenue_chart_default_key': chart_context['revenue_chart_default_key'],
            'revenue_chart_selected_key': chart_context['revenue_chart_selected_key'],
            'revenue_chart_title': chart_context['revenue_chart_title'],
            'revenue_chart_labels_json': json.dumps(chart_context['revenue_chart_labels']),
            'revenue_chart_data_json': json.dumps(chart_context['revenue_chart_data_map']),
            'daily_treatment_labels_json': json.dumps(chart_context['daily_treatment_labels']),
            'daily_treatment_values_json': json.dumps(chart_context['daily_treatment_values']),
            'daily_patient_count': chart_context['daily_patient_count'],
            'daily_treatment_total': chart_context['daily_treatment_total'],
            'today_treatment_labels_json': json.dumps(chart_context['daily_treatment_labels']),
            'today_treatment_values_json': json.dumps(chart_context['daily_treatment_values']),
            'today_patient_count': chart_context['daily_patient_count'],
            'today_treatment_total': chart_context['daily_treatment_total'],
            'top_treatment_name': chart_context['top_treatment_name'],
        })

        return context


class DashboardChartDataView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        selection_raw = request.GET.get('year') or timezone.localdate().year
        payload = _dashboard_chart_payload(selection_raw)
        return JsonResponse(payload)



