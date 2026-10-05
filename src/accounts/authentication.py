from rest_framework import authentication


class SessionAuthentication(authentication.SessionAuthentication):
    """Session auth that answers unauthenticated requests with 401 instead of 403."""

    def authenticate_header(self, request):
        return 'Session'
