from django.utils import timezone

class TimezoneMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        timezone.activate("Asia/Kolkata")

        response = self.get_response(request)

        return response