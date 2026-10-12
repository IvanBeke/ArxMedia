import pytest
from django.contrib.auth.models import AnonymousUser

from accounts.models import AccountVisibility
from accounts.privacy import can_view_account_content, get_viewer_relationship, visible_owner_q
from accounts.tests.factories import UserFactory
from social.models import Follow
from tracking.models import Review

pytestmark = pytest.mark.django_db


def _relationship(*, is_self=False, is_following=False, follows_you=False):
    return {
        'is_self': is_self,
        'is_following': is_following,
        'follows_you': follows_you,
        'is_friend': is_following and follows_you,
    }


class TestCanViewAccountContent:
    @pytest.mark.parametrize(
        'visibility',
        [AccountVisibility.PUBLIC, AccountVisibility.PRIVATE, AccountVisibility.FRIENDS_ONLY],
    )
    def test_self_sees_everything(self, visibility):
        assert can_view_account_content(visibility, _relationship(is_self=True))

    @pytest.mark.parametrize(
        'relationship',
        [
            _relationship(),
            _relationship(is_following=True),
            _relationship(follows_you=True),
            _relationship(is_following=True, follows_you=True),
        ],
    )
    def test_public_visible_to_everyone(self, relationship):
        assert can_view_account_content(AccountVisibility.PUBLIC, relationship)

    @pytest.mark.parametrize(
        'relationship',
        [
            _relationship(),
            _relationship(is_following=True),
            _relationship(follows_you=True),
            _relationship(is_following=True, follows_you=True),
        ],
    )
    def test_private_hidden_from_everyone_else(self, relationship):
        assert not can_view_account_content(AccountVisibility.PRIVATE, relationship)

    def test_friends_only_visible_to_mutual_friends_only(self):
        assert can_view_account_content(
            AccountVisibility.FRIENDS_ONLY, _relationship(is_following=True, follows_you=True)
        )
        for relationship in (
            _relationship(),
            _relationship(is_following=True),
            _relationship(follows_you=True),
        ):
            assert not can_view_account_content(AccountVisibility.FRIENDS_ONLY, relationship)

    def test_anonymous_viewer_relationship(self):
        relationship = get_viewer_relationship(AnonymousUser(), None)
        assert not relationship['is_self']
        assert not relationship['is_friend']
        assert can_view_account_content(AccountVisibility.PUBLIC, relationship)
        assert not can_view_account_content(AccountVisibility.PRIVATE, relationship)


class TestVisibleOwnerQuery:
    """visible_owner_q must agree with can_view_account_content for every relationship."""

    def test_queryset_filter_matches_privacy_verdicts(self):
        viewer = UserFactory(username='viewer')
        targets = {
            'myself': (viewer, AccountVisibility.PRIVATE),
            'public': (None, AccountVisibility.PUBLIC),
            'private': (None, AccountVisibility.PRIVATE),
            'friend': (None, AccountVisibility.FRIENDS_ONLY),
            'oneway': (None, AccountVisibility.FRIENDS_ONLY),
        }
        users = {}
        for name, (user, visibility) in targets.items():
            users[name] = user or UserFactory(username=name, account_visibility=visibility)
        for name in ('public', 'private', 'friend', 'oneway'):
            Follow.objects.create(follower=viewer, following=users[name])
        Follow.objects.create(follower=users['friend'], following=viewer)
        for name, user in users.items():
            Review.objects.create(user=user, media_type='movie', tmdb_id=550, content=f'{name} review')

        visible_ids = set(
            Review.objects.filter(visible_owner_q(viewer)).values_list('user_id', flat=True)
        )
        expected = {
            user.id
            for name, user in users.items()
            if can_view_account_content(
                user.account_visibility, get_viewer_relationship(viewer, user)
            )
        }

        assert visible_ids == expected
        assert {users[name].id for name in ('myself', 'public', 'friend')} == visible_ids
