from typing import TYPE_CHECKING, cast

from rest_framework import authentication

if TYPE_CHECKING:
    from .models import User


def authenticated_user(request):
    """request.user narrowed to a real user for endpoints that require authentication."""
    return cast("User", request.user)


class SessionAuthentication(authentication.SessionAuthentication):
    """Session auth that answers unauthenticated requests with 401 instead of 403."""

    def authenticate_header(self, request):
        return 'Session'
