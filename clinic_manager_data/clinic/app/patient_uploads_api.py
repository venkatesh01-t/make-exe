"""API endpoints for patient uploads"""
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.http import JsonResponse
from .models import Patient, PatientUpload


class PatientUploadsListAPIView(LoginRequiredMixin, View):
    """API endpoint to get all uploads for a patient"""
    
    def get(self, request, *args, **kwargs):
        patient_id = kwargs.get('patient_id')  # Get from URL path, not query params
        
        if not patient_id:
            return JsonResponse({'error': 'patient_id is required'}, status=400)
        
        try:
            patient = get_object_or_404(Patient, id=patient_id)
        except:
            return JsonResponse({'error': 'Patient not found'}, status=404)
        
        # Get all uploads for this patient, sorted by date (newest first)
        uploads = PatientUpload.objects.filter(patient=patient).order_by('-created_at')
        
        # Serialize the uploads
        uploads_data = []
        for upload in uploads:
            uploads_data.append({
                'id': upload.id,
                'original_name': upload.original_name,
                'file_type': upload.file_type,
                'mime_type': upload.mime_type,
                'file': upload.file.url if upload.file else '',
                'size_bytes': upload.size_bytes,
                'created_at': upload.created_at.isoformat() if upload.created_at else '',
                'uploader_username': upload.uploader_username or 'Unknown',
            })
        
        return JsonResponse({
            'patient_id': patient_id,
            'patient_name': f"{patient.first_name} {patient.last_name}",
            'uploads': uploads_data,
            'total': len(uploads_data)
        })


class PatientFileDetailAPIView(LoginRequiredMixin, View):
    """API endpoint to get details of a single patient file"""
    
    def get(self, request, *args, **kwargs):
        file_id = kwargs.get('file_id')
        
        if not file_id:
            return JsonResponse({'error': 'file_id is required'}, status=400)
        
        try:
            upload = get_object_or_404(PatientUpload, id=file_id)
        except:
            return JsonResponse({'error': 'File not found'}, status=404)
        
        # Build file detail response
        file_data = {
            'id': upload.id,
            'patient_id': upload.patient.id,
            'patient_name': f"{upload.patient.first_name} {upload.patient.last_name}",
            'original_name': upload.original_name,
            'file_type': upload.file_type,
            'mime_type': upload.mime_type,
            'file': upload.file.url if upload.file else '',
            'file_size': upload.size_bytes,
            'size_formatted': self._format_file_size(upload.size_bytes),
            'created_at': upload.created_at.isoformat() if upload.created_at else '',
            'created_date': upload.created_at.strftime('%B %d, %Y') if upload.created_at else 'Unknown',
            'uploader_username': upload.uploader_username or 'Unknown',
            'description': upload.description if hasattr(upload, 'description') else '',
        }
        
        return JsonResponse({
            'success': True,
            'file': file_data
        })
    
    @staticmethod
    def _format_file_size(bytes_size):
        """Convert bytes to human readable format"""
        if bytes_size is None:
            return 'Unknown'
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"
