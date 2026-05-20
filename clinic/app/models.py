from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import os
import uuid

# Create your models here.

class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    custom_permissions=models.CharField(max_length=255, blank=True, null=True)
    doctor = models.OneToOneField('Doctor', on_delete=models.SET_NULL, null=True, blank=True, related_name='user')
    


class Patient(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255,blank=True, null=True)
    email = models.EmailField(max_length=255, unique=False)
    phone = models.CharField(max_length=20)
    date_of_birth = models.DateField()
    age = models.IntegerField()
    status = models.CharField(max_length=255, blank=True, null=True)
    gender = models.CharField(max_length=10)
    previous_visits = models.CharField(max_length=255)
    last_visit = models.DateTimeField()
    medical_history = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    


class DailyPatient(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    name=models.CharField(max_length=255,blank=True)
    date = models.DateTimeField(default=timezone.now)
    complaint = models.TextField()
    treatments = models.TextField()
    doctor=models.CharField(max_length=250,blank=True)
    status=models.CharField(max_length=40,default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

    
class appoinments(models.Model):
    
    name= models.CharField(max_length=255, blank=True, null=True)
    doctor = models.CharField(max_length=255)
    treatment = models.CharField(max_length=255)
    date = models.DateField()
    time = models.TimeField()
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):
        
        return f"Appointment for {self.name} with Dr. {self.doctor} on {self.date} at {self.time}"
    


# new models added for clinic settings and image upload
class ClinicInformation(models.Model):
    reg_no = models.CharField("Registration Number", max_length=100, unique=True)
    clinic_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    open_time = models.TimeField(max_length=255, null=True, blank=True)
    close_time = models.TimeField(max_length=255, null=True, blank=True)
    doctor_name = models.CharField(max_length=255, blank=True, null=True)
    doctor_specialist = models.CharField(max_length=255, blank=True, null=True)
    logo = models.ImageField(upload_to="clinic_logos/", blank=True, null=True)

    def __str__(self):
        return f"Clinic #{self.reg_no}"


class UploadedImage(models.Model):
    original = models.ImageField(upload_to="uploaded/%Y/%m/%d/")
    processed = models.ImageField(upload_to="uploaded/processed/%Y/%m/%d/", blank=True, null=True)

    def __str__(self):
        return f"Image {self.id}"
    
class Doctor(models.Model):
    name = models.CharField(max_length=100)
    initials= models.CharField(max_length=10, blank=True)
    education = models.CharField(max_length=120, blank=True)
    signature = models.ImageField(upload_to="doctor_signatures/", blank=True, null=True)
    specialization = models.CharField(max_length=100)
    experience = models.IntegerField(default=0)
    Patients=models.IntegerField(default=0)
    rating = models.CharField(max_length=10, blank=True)
    working_days = models.CharField(max_length=50, blank=True)  # e.g. "Mon,Tue,Wed"
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    def __str__(self):
        return self.name
    
class Treatment(models.Model):
    Treatment_name=models.CharField(max_length=100)
    Description=models.CharField(max_length=100)
    Price=models.CharField(max_length=30)
    Duration=models.CharField(max_length=20)
    def __str__(self):
        return self.Treatment_name

class MedicationTemplate(models.Model):
    """Store medication templates/presets for prescription generation"""
    category = models.CharField(max_length=100)  # e.g., 'pain', 'antibiotic', 'extraction'
    name = models.CharField(max_length=255)  # Drug name
    dosage = models.CharField(max_length=100)  # e.g., '1 Tab', '1 Cap'
    frequency = models.CharField(max_length=50)  # e.g., '1-0-1', 'SOS'
    duration = models.CharField(max_length=50)  # e.g., '5 Days'
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.category} - {self.name}"


class Prescription(models.Model):
    daily_patient = models.OneToOneField('DailyPatient', on_delete=models.CASCADE, null=True, blank=True, related_name='prescription')
    visit_date = models.DateField(default=timezone.now)
    age_gender = models.CharField(max_length=100, blank=True, null=True)
    allergies = models.TextField(blank=True, null=True)
    chief_complaint = models.TextField(blank=True, null=True)
    diagnosis = models.TextField(blank=True, null=True)
    advice = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_prescriptions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Prescription #{self.id} - {self.daily_patient.patient}"


class PrescriptionMedication(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='medicines')
    drug_name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=100, blank=True, null=True)
    frequency = models.CharField(max_length=100, blank=True, null=True)
    duration = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.drug_name} ({self.prescription_id})"


class PrescriptionTreatment(models.Model):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='treatments')
    treatment_name = models.CharField(max_length=255)
    tooth_number = models.CharField(max_length=50, blank=True, null=True, help_text="e.g., #11, #12, etc.")
    is_paid = models.BooleanField(default=True, help_text="Whether this treatment has been paid for")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        tooth_info = f" - Tooth {self.tooth_number}" if self.tooth_number else ""
        return f"{self.treatment_name}{tooth_info} ({self.prescription_id})"

  

class InventoryItem(models.Model):
    CATEGORY_CHOICES = [
        ('Medicine', 'Medicine'),
        ('Equipment', 'Equipment'),
        ('Supplies', 'Supplies'),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=50, 
        choices=CATEGORY_CHOICES, 
        default='Supplies'
    )
    qty = models.IntegerField(default=0)
    expiry = models.DateField(null=True, blank=True)
    # The view refers to this as 'description' in POST but saves it to 'notes'
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.category})"

    class Meta:
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
        ordering = ['-id']


class InventoryEvent(models.Model):
    """Track inventory operations (add/decrease) for audit trail"""
    EVENT_TYPE_CHOICES = [
        ('INCREASE', 'Quantity Increased'),
        ('DECREASE', 'Quantity Decreased'),
        ('CREATE', 'Item Created'),
        ('UPDATE', 'Item Updated'),
        ('DELETE', 'Item Deleted'),
    ]
    
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    quantity_changed = models.IntegerField(default=0)  # positive or negative number
    previous_qty = models.IntegerField(default=0)
    new_qty = models.IntegerField(default=0)
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Inventory Event"
        verbose_name_plural = "Inventory Events"
    
    def __str__(self):
        return f"{self.event_type} - {self.inventory_item.name} ({self.timestamp})"


class labwork(models.Model):
    patient = models.ForeignKey('Patient', on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_orders')
    patient_name = models.CharField(max_length=255)
    work_type = models.CharField(max_length=50)
    lab_name = models.CharField(max_length=100)
    workflow_status = models.CharField(max_length=50)
    date_sent = models.DateField()
    note= models.CharField( max_length=100,blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.patient_name} - {self.work_type}"
    
class labdetails(models.Model):
    lab_name = models.CharField(max_length=255)
    lab_address = models.CharField(max_length=255)
    lab_phone = models.CharField(max_length=20)
    lab_email = models.EmailField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.lab_name
    
class labtest(models.Model):
    test_name = models.CharField(max_length=255)
    test_price = models.DecimalField(max_digits=10, decimal_places=2)
    test_category = models.CharField(max_length=50, default='Other')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.test_name


def patient_upload_path(instance, filename):
    """Store uploads under patientid_username folders."""
    _, ext = os.path.splitext(filename)
    username = (instance.uploader_username or "anonymous").strip() or "anonymous"
    safe_username = username.replace("/", "_").replace("\\", "_").replace(" ", "_")
    patient_id = instance.patient_id or "unknown"
    return f"patient_uploads/{patient_id}_{safe_username}/{uuid.uuid4().hex}{ext.lower()}"


class PatientUpload(models.Model):
    FILE_TYPE_CHOICES = [
        ("image", "Image"),
        ("pdf", "PDF"),
        ("video", "Video"),
        ("docx", "DOCX"),
    ]

    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='uploads')
    daily_patient = models.ForeignKey('DailyPatient', on_delete=models.CASCADE, related_name='uploads')
    file = models.FileField(upload_to=patient_upload_path)
    original_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    mime_type = models.CharField(max_length=120, blank=True, null=True)
    size_bytes = models.BigIntegerField(default=0)
    uploader = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='patient_uploads')
    uploader_username = models.CharField(max_length=150, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.original_name


class BillingInvoice(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PAID, 'Paid'),
    ]

    invoice_number = models.CharField(max_length=30, unique=True, blank=True)
    patient = models.ForeignKey('Patient', on_delete=models.CASCADE, related_name='billing_invoices')
    daily_patient = models.ForeignKey('DailyPatient', on_delete=models.SET_NULL, null=True, blank=True, related_name='billing_invoices')
    treatment = models.CharField(max_length=255, blank=True, null=True)
    doctor = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    note = models.CharField(max_length=255, blank=True, null=True)
    bill_date = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_bills')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-bill_date', '-id']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['bill_date']),
        ]

    def __str__(self):
        return self.invoice_number or f"Invoice #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            prefix = timezone.now().strftime('%Y%m')
            last = BillingInvoice.objects.order_by('-id').first()
            next_no = (last.id + 1) if last else 1
            self.invoice_number = f"INV-{prefix}-{next_no:04d}"
        super().save(*args, **kwargs)