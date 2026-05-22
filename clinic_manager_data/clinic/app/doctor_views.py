from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404
import json
from django.core.files.base import ContentFile

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None


from .models import Doctor


def _build_signature_png(image_file):
    if not image_file or cv2 is None or np is None:
        return None

    image_file.seek(0)
    file_bytes = np.frombuffer(image_file.read(), np.uint8)
    if file_bytes.size == 0:
        return None

    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Extract strokes by inverting near-white background into alpha mask.
    _, alpha = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # Signature content as black ink with transparent background.
    h, w = gray.shape
    black = np.zeros((h, w), dtype=np.uint8)
    rgba = cv2.merge([black, black, black, alpha])

    success, png_data = cv2.imencode('.png', rgba)
    if not success:
        return None

    return ContentFile(png_data.tobytes())


def doctor_data(request):
    doctor=Doctor.objects.all()

    return render(request, "ext/doctor_data.html", {"doctors": doctor})

class DoctorsPartialView(LoginRequiredMixin, TemplateView):
    template_name = 'partials/doctors.html'
    def get(self,request):
        return render(request, self.template_name, {"doctors": Doctor.objects.all()})

class DoctorDeleteView(LoginRequiredMixin, TemplateView):
    def post(self, request):
        doctor_id = request.POST.get('doctor_id')
        doctor = get_object_or_404(Doctor, id=doctor_id)
        name = doctor.name
        doctor.delete()
        print(f"Doctor deleted: {name}")      
        response = doctor_data(request)
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": "Doctor deleted successfully!",
                "type": "success",
                "duration": 4000,
                "closemodel": "deleteModal"
            }
        })
        
        # Wrap dict into JsonResponse
        return response
class DoctorEditView(LoginRequiredMixin, TemplateView):
    def post(self,request):

        

            doctor_id = request.POST.get("doctor_id")

            doctor = Doctor.objects.get(id=doctor_id)

            doctor.name = request.POST.get("name")
            doctor.initials=request.POST.get("name").split(" ")[0][:1].upper() + request.POST.get("name").split(" ")[-1][:1].upper() if len(request.POST.get("name").split(" ")) > 1 else request.POST.get("name").split(" ")[0][:1].upper()
            doctor.specialization = request.POST.get("specialization")
            doctor.education = request.POST.get("education", "").strip()
            doctor.experience = request.POST.get("experience")
            doctor.rating = request.POST.get("rating")

            days = request.POST.getlist("working_days")
            doctor.working_days = ",".join(days)

            doctor.start_time = request.POST.get("start_time")
            doctor.end_time = request.POST.get("end_time")

            remove_signature = request.POST.get("remove_signature") == "1"
            if remove_signature and doctor.signature:
                doctor.signature.delete(save=False)

            signature_file = request.FILES.get("signature")
            if signature_file:
                processed = _build_signature_png(signature_file)
                if processed:
                    doctor.signature.save(f"doctor_signature_{doctor.pk}.png", processed, save=False)
                else:
                    # Fallback: save original upload if processing is unavailable.
                    doctor.signature = signature_file

            doctor.save()

            response = doctor_data(request)

            response["HX-Trigger"] = json.dumps({
                "showNotification": {
                    "message": "Doctor updated successfully!",
                    "type": "success",
                    "duration": 4000,
                    "closemodel": "editDoctorModal"
                }
            })
            return response


class DoctorAddView(LoginRequiredMixin, TemplateView):
    def post(self,request):
        
            # Get selected working days (can be multiple checkboxes)
            days = request.POST.getlist("working_days")
            working_days = ",".join(days)

            doctor = Doctor.objects.create(
                name=request.POST.get("name"),
                initials=request.POST.get("name").split(" ")[0][:1].upper() + request.POST.get("name").split(" ")[-1][:1].upper() if len(request.POST.get("name").split(" ")) > 1 else request.POST.get("name").split(" ")[0][:1].upper(),
                specialization=request.POST.get("specialization"),
                education=request.POST.get("education", "").strip(),
                experience=request.POST.get("experience") or 0,
                Patients=0,
                rating=request.POST.get("rating"),
                working_days=working_days,
                start_time=request.POST.get("start_time"),
                end_time=request.POST.get("end_time"),
            )

            signature_file = request.FILES.get("signature")
            if signature_file:
                processed = _build_signature_png(signature_file)
                if processed:
                    doctor.signature.save(f"doctor_signature_{doctor.pk}.png", processed, save=False)
                else:
                    # Fallback: save original upload if processing is unavailable.
                    doctor.signature = signature_file
                doctor.save()

            # Return only the new doctor card (HTMX)
            response = doctor_data(request)
            
            response["HX-Trigger"] = json.dumps({
                "showNotification": {
                    "message": f"User created successfully for {request.POST.get('name')}!",
                    "type": "success",
                    "duration": 4000,
                    "closemodel": "addDoctorModal"
                
                }
            })

            return response