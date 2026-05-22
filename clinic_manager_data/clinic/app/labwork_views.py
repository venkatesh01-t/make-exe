from django import template
from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.shortcuts import render,get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from datetime import timedelta
from django.core.paginator import Paginator

from .models import ClinicInformation, Doctor, Patient, labdetails,labwork,labtest
import json
from django.utils import timezone



class LabWorkPartialView(LoginRequiredMixin, TemplateView):

    template_name = 'partials/lab_work.html'
    def get(self,request):
        context={
           "labdetails": labdetails.objects.all(),
           "labwork":labwork.objects.all(),
           "labtest":labtest.objects.all()

        }
        return render(self.request,self.template_name,context)


class LabWorkPaginatedView(LoginRequiredMixin, TemplateView):
    """Handle paginated lab work data with HTMX"""
    template_name = 'ext/lab_data_paginated.html'
    
    def get(self, request):
        page_num = request.GET.get('page', 1)
        all_labwork = labwork.objects.all().order_by("-id")
        
        paginator = Paginator(all_labwork, 10)  # 10 items per page
        page_obj = paginator.get_page(page_num)
        
        context = {
            'page_obj': page_obj,
            'labwork': page_obj.object_list,
            'total_pages': paginator.num_pages,
            'is_paginated': paginator.num_pages > 1
        }
        
        return render(request, self.template_name, context)


class LabWorkStatusCountsView(LoginRequiredMixin, TemplateView):
    """Return JSON with total counts of all lab work by status"""
    
    def get(self, request):
        from django.db.models import Count
        from django.http import JsonResponse
        
        # Get all lab work grouped by status
        all_labwork = labwork.objects.all()
        total = all_labwork.count()
        
        counts = {
            'SEND': all_labwork.filter(workflow_status='SEND').count(),
            'RECEIVED': all_labwork.filter(workflow_status='RECEIVED').count(),
            'INFORMED': all_labwork.filter(workflow_status='INFORMED').count(),
            'QA': all_labwork.filter(workflow_status='QA').count(),
            'FINSHED': all_labwork.filter(workflow_status='FINSHED').count(),
        }
        
        return JsonResponse({
            'total': total,
            'counts': counts
        })


class LabCreateView(TemplateView):

    def post(self, request, *args, **kwargs):

        lab_id = request.POST.get("ld-id")
        name = request.POST.get("ld-name")
        address = request.POST.get("ld-address")
        phone = request.POST.get("ld-phone")
        email = request.POST.get("ld-email")

        message = ""

        if lab_id:
            # Edit existing lab
            lab = labdetails.objects.get(id=lab_id)
            lab.lab_name = name
            lab.lab_address = address
            lab.lab_phone = phone
            lab.lab_email = email
            lab.save()
            message = "Lab details updated successfully"

        else:
            # Add new lab
            labdetails.objects.create(
                lab_name=name,
                lab_address=address,
                lab_phone=phone,
                lab_email=email
            )
            message = "Lab details added successfully"

        # Get all labs to render table rows
        labs = labdetails.objects.all().order_by("-id")
        response = render(request, "ext/lab_details_data.html", {"labdetails": labs})

        # HTMX Trigger for notification and modal close
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": message,
                "type": "success",
                "duration": 4000,
                "closemodel": "lab-details-modal"
            }
        })
        return response

class LabWorkCRUDView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        item_id = request.POST.get("lw-id")
        name = request.POST.get("lw-name")
        price = request.POST.get("lw-price")
        category = request.POST.get("lw-category")

        message = ""
        if item_id:
            item = get_object_or_404(labtest, id=item_id)
            item.test_name = name
            item.test_price = price
            item.test_category = category
            item.save()
            message = "Lab work item updated successfully"
        else:
            labtest.objects.create(
                test_name=name,
                test_price=price,
                test_category=category
            )
            message = "Lab work item added successfully"

        labtests = labtest.objects.all().order_by("-id")
        response = render(request, "ext/lab_item_data.html", {"labtest": labtests})
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": message,
                "type": "success",
                "duration": 4000,
                "closemodel": "lab-work-modal"
            }
        })
        return response


class LabOrderCreateView(LoginRequiredMixin, TemplateView):

    def post(self, request, *args, **kwargs):
        patient_id_raw = request.POST.get("in-patient-id", "0")
        patient_name = request.POST.get("in-patient")
        work_type = request.POST.get("in-type")
        lab_name = request.POST.get("in-lab")
        note = request.POST.get("in-notes")

        try:
            patient_id = int(patient_id_raw)
        except (TypeError, ValueError):
            patient_id = 0

        patient_obj = Patient.objects.filter(id=patient_id).first() if patient_id > 0 else None

        lab_work_instance = labwork.objects.create(
            patient=patient_obj,
            patient_name=patient_name,
            work_type=work_type,
            lab_name=lab_name,
            note=note,
            workflow_status="SEND",
            date_sent=timezone.now().date()
        )

        # Get paginated data
        all_labwork = labwork.objects.all().order_by("-id")
        paginator = Paginator(all_labwork, 10)
        page_obj = paginator.get_page(1)
        
        context = {
            'page_obj': page_obj,
            'labwork': page_obj.object_list,
            'total_pages': paginator.num_pages,
            'is_paginated': paginator.num_pages > 1
        }
        
        response = render(request, "ext/lab_data_paginated.html", context)

        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": "Lab order created successfully",
                "type": "success",
                "duration": 4000,
                "closemodel": "add-lab-modal"
            }
        })
        response["HX-Retarget"] = "#lab-orders-table-body"

    # change swap behavior
        response["HX-Reswap"] = "innerHTML"
        return response

class LabOrderStatusUpdateView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        order_id = request.POST.get("order_id")
        status_node = request.POST.get("status_node")

        status_map = {
            "1": "SEND",
            "2": "RECEIVED",
            "3": "INFORMED",
            "4": "QA",
            "5": "FINSHED"
        }

        new_status = status_map.get(status_node, "SEND")

        order = get_object_or_404(labwork, id=order_id)
        order.workflow_status = new_status
        order.save()

        response = HttpResponse()
        response["HX-Trigger"] = json.dumps({
            "showNotification": {
                "message": f"Status updated to {new_status}",
                "type": "success",
                "duration": 4000,
                "closemodel": "not"
            }
        })
        return response


class LabOrderDetailsPrintView(LoginRequiredMixin, TemplateView):
    template_name = "ext/labwork_details_print.html"

    @method_decorator(xframe_options_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, order_id, *args, **kwargs):
        order = get_object_or_404(labwork.objects.select_related("patient"), id=order_id)

        clinic_info = ClinicInformation.objects.order_by("-id").first()
        lab_info = labdetails.objects.filter(lab_name__iexact=order.lab_name).first()
        if not lab_info:
            lab_info = labdetails.objects.order_by("-id").first()

        doctor_signature = None
        if clinic_info and clinic_info.doctor_name:
            doctor_signature = Doctor.objects.filter(
                name__iexact=clinic_info.doctor_name,
                signature__isnull=False,
            ).first()
        if not doctor_signature:
            doctor_signature = Doctor.objects.filter(signature__isnull=False).order_by("-id").first()

        sent_date = order.date_sent
        received_date = sent_date
        finish_date = sent_date + timedelta(days=2)

        context = {
            "order": order,
            "clinic_info": clinic_info,
            "lab_info": lab_info,
            "doctor_signature": doctor_signature,
            "sent_date": sent_date,
            "received_date": received_date,
            "finish_date": finish_date,
            "today": timezone.now().date(),
        }
        return render(request, self.template_name, context)
        
