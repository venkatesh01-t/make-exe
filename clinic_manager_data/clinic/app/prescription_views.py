from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from weasyprint import HTML
from django.http import HttpResponse
from django.template.loader import render_to_string

class PrescriptionPartialView(LoginRequiredMixin, TemplateView):
    def get(self, request):
        html_string = render_to_string("partials/prescription.html")
        html = HTML(string=html_string)
        pdf = html.write_pdf()
        response = HttpResponse(pdf, content_type="application/pdf")
        response['Content-Disposition'] = 'filename="invoice.pdf"'
        return response
    
    