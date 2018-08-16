from django.conf import settings

def settings_processor(request):
    return {
        "SITE_URL": settings.SITE_URL
    }
