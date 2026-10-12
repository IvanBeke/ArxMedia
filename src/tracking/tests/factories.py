import factory
from factory.django import DjangoModelFactory

from tracking.models import (
    CustomList,
    DataTransferJob,
    ListCollaborator,
    ListItem,
    Rating,
    Review,
    UserMediaStatus,
    WatchEntry,
)


class WatchEntryFactory(DjangoModelFactory):
    class Meta:
        model = WatchEntry

    user = factory.SubFactory("accounts.tests.factories.UserFactory")
    media_type = "movie"
    tmdb_id = factory.Sequence(lambda n: 600000 + n)


class EpisodeWatchEntryFactory(WatchEntryFactory):
    media_type = "episode"
    season_number = 1
    episode_number = factory.Sequence(lambda n: (n % 20) + 1)


class RatingFactory(DjangoModelFactory):
    class Meta:
        model = Rating

    user = factory.SubFactory("accounts.tests.factories.UserFactory")
    media_type = "movie"
    tmdb_id = factory.Sequence(lambda n: 610000 + n)
    score = 8


class ReviewFactory(DjangoModelFactory):
    class Meta:
        model = Review

    user = factory.SubFactory("accounts.tests.factories.UserFactory")
    media_type = "movie"
    tmdb_id = 550
    content = factory.Sequence(lambda n: f"Review {n}")


class UserMediaStatusFactory(DjangoModelFactory):
    class Meta:
        model = UserMediaStatus

    user = factory.SubFactory("accounts.tests.factories.UserFactory")
    media_type = "movie"
    tmdb_id = factory.Sequence(lambda n: 620000 + n)
    status = "plan_to_watch"


class CustomListFactory(DjangoModelFactory):
    class Meta:
        model = CustomList

    user = factory.SubFactory("accounts.tests.factories.UserFactory")
    name = factory.Sequence(lambda n: f"List {n}")
    privacy = "public"


class ListItemFactory(DjangoModelFactory):
    class Meta:
        model = ListItem

    custom_list = factory.SubFactory(CustomListFactory)
    media_type = "movie"
    tmdb_id = factory.Sequence(lambda n: 630000 + n)


class ListCollaboratorFactory(DjangoModelFactory):
    class Meta:
        model = ListCollaborator

    custom_list = factory.SubFactory(CustomListFactory)
    user = factory.SubFactory("accounts.tests.factories.UserFactory")


class DataTransferJobFactory(DjangoModelFactory):
    class Meta:
        model = DataTransferJob

    user = factory.SubFactory("accounts.tests.factories.UserFactory")
    job_type = "export"
    data_format = "zip"
    status = "pending"
