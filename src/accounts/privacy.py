from django.contrib.auth.models import AnonymousUser
from django.db.models import Q
from social.models import Follow

from .models import AccountVisibility


def get_viewer_relationship(viewer, target) -> dict[str, bool]:
    is_authenticated = bool(viewer and not isinstance(viewer, AnonymousUser) and viewer.is_authenticated)
    is_self = is_authenticated and viewer.id == target.id

    if not is_authenticated:
        return {
            'is_self': False,
            'is_following': False,
            'follows_you': False,
            'is_friend': False,
        }

    if is_self:
        return {
            'is_self': True,
            'is_following': False,
            'follows_you': False,
            'is_friend': True,
        }

    is_following = viewer.following.filter(following=target).exists()
    follows_you = viewer.followers.filter(follower=target).exists()
    return {
        'is_self': False,
        'is_following': is_following,
        'follows_you': follows_you,
        'is_friend': is_following and follows_you,
    }


def can_view_account_content(visibility: str, relationship: dict[str, bool]) -> bool:
    if relationship['is_self']:
        return True
    if visibility == AccountVisibility.PUBLIC:
        return True
    if visibility == AccountVisibility.FRIENDS_ONLY:
        return relationship['is_friend']
    return False


def visible_owner_q(viewer, field: str = 'user') -> Q:
    """Filter for rows owned by accounts whose content `viewer` may see (queryset form of can_view_account_content)."""
    following = Follow.objects.filter(follower=viewer).values('following_id')
    followers = Follow.objects.filter(following=viewer).values('follower_id')
    return (
        Q(**{f'{field}_id': viewer.id})
        | Q(**{f'{field}__account_visibility': AccountVisibility.PUBLIC})
        | Q(
            **{
                f'{field}__account_visibility': AccountVisibility.FRIENDS_ONLY,
                f'{field}_id__in': following,
            }
        ) & Q(**{f'{field}_id__in': followers})
    )
