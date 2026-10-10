from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from accounts.models import AccountVisibility, User
from accounts.privacy import can_view_account_content, get_viewer_relationship, visible_owner_q
from social.models import Follow
from tracking.models import Review


def _relationship(*, is_self=False, is_following=False, follows_you=False):
    return {
        'is_self': is_self,
        'is_following': is_following,
        'follows_you': follows_you,
        'is_friend': is_following and follows_you,
    }


class CanViewAccountContentTests(TestCase):
    def test_self_sees_everything(self):
        relationship = _relationship(is_self=True)
        for visibility in (AccountVisibility.PUBLIC, AccountVisibility.PRIVATE, AccountVisibility.FRIENDS_ONLY):
            with self.subTest(visibility=visibility):
                self.assertTrue(can_view_account_content(visibility, relationship))

    def test_public_visible_to_everyone(self):
        for relationship in (
            _relationship(),
            _relationship(is_following=True),
            _relationship(follows_you=True),
            _relationship(is_following=True, follows_you=True),
        ):
            with self.subTest(relationship=relationship):
                self.assertTrue(can_view_account_content(AccountVisibility.PUBLIC, relationship))

    def test_private_hidden_from_everyone_else(self):
        for relationship in (
            _relationship(),
            _relationship(is_following=True),
            _relationship(follows_you=True),
            _relationship(is_following=True, follows_you=True),
        ):
            with self.subTest(relationship=relationship):
                self.assertFalse(can_view_account_content(AccountVisibility.PRIVATE, relationship))

    def test_friends_only_visible_to_mutual_friends_only(self):
        self.assertTrue(
            can_view_account_content(
                AccountVisibility.FRIENDS_ONLY, _relationship(is_following=True, follows_you=True)
            )
        )
        for relationship in (
            _relationship(),
            _relationship(is_following=True),
            _relationship(follows_you=True),
        ):
            with self.subTest(relationship=relationship):
                self.assertFalse(can_view_account_content(AccountVisibility.FRIENDS_ONLY, relationship))

    def test_anonymous_viewer_relationship(self):
        relationship = get_viewer_relationship(AnonymousUser(), None)
        self.assertFalse(relationship['is_self'])
        self.assertFalse(relationship['is_friend'])
        self.assertTrue(can_view_account_content(AccountVisibility.PUBLIC, relationship))
        self.assertFalse(can_view_account_content(AccountVisibility.PRIVATE, relationship))


class VisibleOwnerQueryTests(TestCase):
    """visible_owner_q must agree with can_view_account_content for every relationship."""

    def test_queryset_filter_matches_privacy_verdicts(self):
        viewer = User.objects.create_user(username='viewer', password='pass12345')
        targets = {
            'myself': (viewer, AccountVisibility.PRIVATE),
            'public': (None, AccountVisibility.PUBLIC),
            'private': (None, AccountVisibility.PRIVATE),
            'friend': (None, AccountVisibility.FRIENDS_ONLY),
            'oneway': (None, AccountVisibility.FRIENDS_ONLY),
        }
        users = {}
        for name, (user, visibility) in targets.items():
            users[name] = user or User.objects.create_user(
                username=name, password='pass12345', account_visibility=visibility
            )
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

        self.assertEqual(visible_ids, expected)
        self.assertEqual(
            {users[name].id for name in ('myself', 'public', 'friend')}, visible_ids
        )
