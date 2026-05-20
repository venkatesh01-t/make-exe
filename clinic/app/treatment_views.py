
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import render

from .models import Treatment
import json


class TreatmentsPartialView(LoginRequiredMixin, TemplateView):
    template_name = 'partials/treatments.html'

    def get(self, request):
        return render(request, self.template_name, {"treatment": Treatment.objects.all()})
        
    def post(self, request):
        action = request.POST.get("action")
        treatment_id = request.POST.get("treatment_id")
        message="not"
        close=""
        
        if action == "add":
            name = request.POST.get("name")
            description = request.POST.get("description")
            cost = request.POST.get("cost")
            duration = request.POST.get("duration")
            Treatment.objects.create(
                Treatment_name=name,
                Description=description,
                Price=cost,
                Duration=duration
            )
            message = f"Treatment added successfully for {name}!"
            close="treatmentModal"
            

        elif action == "edit" and treatment_id:
            treatment = Treatment.objects.get(id=treatment_id)
            treatment.Treatment_name = request.POST.get("name")
            treatment.Description = request.POST.get("description")
            treatment.Price = request.POST.get("cost")
            treatment.Duration = request.POST.get("duration")
            treatment.save()
            message = f"Treatment updated successfully for {treatment.Treatment_name}!"
            close="treatmentModal"

        elif action == "delete" and treatment_id:
            treatment = Treatment.objects.get(id=treatment_id)
            name = treatment.Treatment_name
            treatment.delete()
            message = f"Treatment '{name}' deleted successfully!"
            close="deleteModal"

        response = render(request, 'ext/treatment_data.html', {"treatment": Treatment.objects.all()})
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": message,
                "type": "success",
                "duration": 4000,
                "closemodel":close
            }
        })
        return response
