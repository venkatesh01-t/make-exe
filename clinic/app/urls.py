from django.urls import path
from .views import *
from .reports_views import *
from .appoinments_views import *
from .patients_views import *
from .doctor_views import *
from .treatment_views import *
from .billing_views import *
from .settings_views import *
from .inventory_views import *
from .labwork_views import *
from .today_patient import *
from .medication_views import *
from .patient_uploads_api import PatientFileDetailAPIView

app_name = 'clinic'

urlpatterns = [
    # Main shell page
    path("users/create/", UserCreateView.as_view(), name="user_create"),
    path("users/edit/<int:pk>/", UserEditView.as_view(), name="user_edit"),
    path("doctors/list-json/", get_doctors_json, name="doctors_list_json"),

    path("login/", HtmxLoginView.as_view(), name="htmx_login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path('', IndexView.as_view(), name='index'),

    # HTMX partial views (loaded dynamically without page reload)
    path('partials/dashboard/', DashboardPartialView.as_view(), name='dashboard_partial'),
    path('partials/dashboard/chart-data/', DashboardChartDataView.as_view(), name='dashboard_chart_data'),


    path('partials/appointments/', AppointmentsPartialView.as_view(), name='appointments_partial'),


    path('partials/patients/', PatientsPartialView.as_view(), name='patients_partial'),


    path('partials/doctors/', DoctorsPartialView.as_view(), name='doctors_partial'),
    path('doctors/data/', doctor_data, name='doctor_data'),  # New endpoint for doctor data
    path('doctors/add/', DoctorAddView.as_view(), name='add_doctor'),
    path('doctors/edit/', DoctorEditView.as_view(), name='edit_doctor'),
    path('doctors/delete/', DoctorDeleteView.as_view(), name='doctor_delete'),

    path('partials/treatments/', TreatmentsPartialView.as_view(), name='treatments_partial'),

    path('partials/billing/', BillingPartialView.as_view(), name='billing_partial'),
    path('partials/billing/data/', BillingDataView.as_view(), name='billing_data'),
    path('partials/billing/create/', BillingCreateView.as_view(), name='billing_create'),
    path('partials/billing/<int:invoice_id>/mark-paid/', BillingMarkPaidView.as_view(), name='billing_mark_paid'),
    path('billing/invoice/<int:invoice_id>/a4/', BillingA4View.as_view(), name='billing_a4'),

    path('partials/reports/', ReportsPartialView.as_view(), name='reports_partial'),
    path('partials/reports/data/', ReportsDataView.as_view(), name='reports_data'),
    path('partials/reports/export/', ReportsExportView.as_view(), name='reports_export'),

    path('partials/settings/', SettingsPartialView.as_view(), name='settings_partial'),
    path('partials/settings/export-csv/', SettingsExportCSVView.as_view(), name='settings_export_csv'),
    path('partials/settings/backup-database/', SettingsBackupDatabaseView.as_view(), name='settings_backup_database'),
    path('partials/settings/clear-temporary-data/', SettingsClearTemporaryDataView.as_view(), name='settings_clear_temporary_data'),
    # endpoint to save/update clinic information via HTMX



    path('save-clinic-info/', ClinicInfoView.as_view(), name='save_clinic_info'),
    # optional legacy upload view

    



    path('partials/lab_work/', LabWorkPartialView.as_view(), name='lab_work_partial'),
    path('partials/lab_work/paginated/', LabWorkPaginatedView.as_view(), name='lab_work_paginated'),
    path('partials/lab_work/counts/', LabWorkStatusCountsView.as_view(), name='lab_work_counts'),
    path("partials/create/", LabCreateView.as_view(), name="lab_create"),
    path("partials/work/crud/", LabWorkCRUDView.as_view(), name="lab_work_crud"),
    path("partials/order/create/", LabOrderCreateView.as_view(), name="lab_order_create"),
    path("partials/order/update/", LabOrderStatusUpdateView.as_view(), name="lab_order_update"),
    path("partials/order/<int:order_id>/details/", LabOrderDetailsPrintView.as_view(), name="lab_order_details"),


    path('partials/inventory/', InventoryPartialView.as_view(), name='inventory_partial'),
    path('partials/inventory/paginated/', InventoryPaginatedView.as_view(), name='inventory_paginated'),
    path('partials/data/', InventoryeditView.as_view(), name='inventory_edit'),
    path('partials/<int:id>/<str:key>/', InventoryView.as_view(), name='inventoryop'),
    path('inventory/<int:id>/events/', InventoryEventsView.as_view(), name='inventory_events'),
    path('inventory/export/csv/', InventoryExportCSVView.as_view(), name='inventory_export_csv'),


    path('add_patient/', Patientsdatasave.as_view(), name='add_patient'),
    path('edit_patient/', PatientEditView.as_view(), name='edit_patient'),
    path('delete_patient/', PatientDeleteView.as_view(), name='delete_patient'),


    path('patients-table-body/', patients_table_body, name='patients_table_body') ,
    path('appointments-data/', get_appointment_data, name='appointments_data'),
    path('appointments-create/', AppointmentCreateView.as_view(), name='appointments_create'),
    path('appointments-edit/', AppointmentEditView.as_view(), name='appointments_edit'),
    path('appointments-delete/', AppointmentDeleteView.as_view(), name='appointments_delete'),
    path('users/delete/', UserDeleteView.as_view(), name='user_delete'),


    path('today_patient/<int:id>/', today_patient_book.as_view(), name="today_patient_book"),


    path('today_patient/',today_patient.as_view(),name='today_patient'),
    path('today_patient/prescription-submit/', PrescriptionSubmitView.as_view(), name='prescription_submit'),
    path('today_patient/prescription-latest/<int:patient_id>/', get_latest_prescription, name='patient_latest_prescription'),
    path('today_patient/prescription-by-daily/<int:daily_patient_id>/', get_daily_patient_prescription, name='daily_patient_prescription'),
    path('today_patient/delete/', DailyPatientDeleteView.as_view(), name='today_patient_delete'),
    path('today_patient/uploads/<int:daily_patient_id>/list/', PatientUploadListView.as_view(), name='patient_upload_list'),
    path('today_patient/uploads/create/', PatientUploadCreateView.as_view(), name='patient_upload_create'),
    path('today_patient/uploads/<int:upload_id>/delete/', PatientUploadDeleteView.as_view(), name='patient_upload_delete'),
    path('get_today_patient_data/', get_today_patient_data, name='today_patient_data'),
    
    # Medication Management CRUD
    path('medications/', MedicationListView.as_view(), name='medication_list'),
    path('medications/create/', MedicationCreateView.as_view(), name='medication_create'),
    path('medications/<int:pk>/update/', MedicationUpdateView.as_view(), name='medication_update'),
    path('medications/<int:pk>/delete/', MedicationDeleteView.as_view(), name='medication_delete'),
    path('medications/<int:pk>/edit-form/', MedicationEditFormView.as_view(), name='medication_edit_form'),
    path('medications/by-category/', MedicationByCategoryView.as_view(), name='medication_by_category'),
    
    # API Endpoints for Patient History Modal
    path('api/patient/<int:patient_id>/daily-visits/', PatientDailyVisitsAPIView.as_view(), name='api_patient_daily_visits'),
    path('api/patient/<int:patient_id>/labwork/', PatientLabWorkAPIView.as_view(), name='api_patient_labwork'),
    path('api/daily-patient/<int:daily_patient_id>/prescription/', DailyPatientPrescriptionAPIView.as_view(), name='api_daily_patient_prescription'),
    path('api/labwork/<int:labwork_id>/', LabWorkDetailAPIView.as_view(), name='api_labwork_detail'),
    path('api/patient/<int:patient_id>/uploads/', PatientFilesAPIView.as_view(), name='api_patient_uploads'),
    path('clinic/api/patient/<int:patient_id>/uploads/', PatientFilesAPIView.as_view(), name='api_patient_uploads_compat'),
    path('api/file/<int:file_id>/detail/', PatientFileDetailAPIView.as_view(), name='api_file_detail'),
    
    # Test error pages (remove in production)
    path('test-404/', test_404_page, name='test_404'),
    path('test-500/', test_500_page, name='test_500'),
    path('clinic-debug/', clinic_debug, name='clinic_debug'),
]
