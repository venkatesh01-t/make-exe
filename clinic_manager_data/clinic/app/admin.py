from django.contrib import admin
from .models import CustomUser, Patient, appoinments, ClinicInformation, UploadedImage,DailyPatient,Doctor,Treatment,InventoryItem,labwork,labtest,labdetails, MedicationTemplate, InventoryEvent

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(Patient)
admin.site.register(appoinments)
admin.site.register(ClinicInformation)
admin.site.register(UploadedImage)
admin.site.register(DailyPatient)
admin.site.register(Doctor)
admin.site.register(Treatment)
admin.site.register(InventoryItem)
admin.site.register(InventoryEvent)
admin.site.register(labwork)
admin.site.register(labtest)
admin.site.register(labdetails)
admin.site.register(MedicationTemplate)
