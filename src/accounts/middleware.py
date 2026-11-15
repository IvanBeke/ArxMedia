from django.conf import settings
from django.utils import translation


class UserLanguageMiddleware:
    """Serve every response in the signed-in user's language; anonymous requests use the default."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        language = user.language if user is not None and user.is_authenticated else settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = language
        try:
            response = self.get_response(request)
        finally:
            translation.deactivate()
        response.headers.setdefault('Content-Language', language)
        return response
