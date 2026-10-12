import factory
from factory.django import DjangoModelFactory

from social.models import Follow


class FollowFactory(DjangoModelFactory):
    class Meta:
        model = Follow

    follower = factory.SubFactory("accounts.tests.factories.UserFactory")
    following = factory.SubFactory("accounts.tests.factories.UserFactory")
