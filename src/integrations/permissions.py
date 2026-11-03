from rest_framework import permissions

from .clients import radarr_credentials, sonarr_credentials

SONARR_RADARR_PERMISSION = 'accounts.use_sonarr_radarr'


class CanUseSonarrRadarr(permissions.BasePermission):
    message = 'You do not have permission to use Sonarr and Radarr.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.has_perm(SONARR_RADARR_PERMISSION))


def enabled_integrations(user) -> dict[str, bool]:
    """Which external services this user may use and that are configured."""
    can_use_arr = user.has_perm(SONARR_RADARR_PERMISSION)
    return {
        'radarr': can_use_arr and all(radarr_credentials()),
        'sonarr': can_use_arr and all(sonarr_credentials()),
        'jellyfin': False,
    }
