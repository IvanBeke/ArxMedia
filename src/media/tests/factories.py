import factory
from factory.django import DjangoModelFactory

from media.models import Episode, EpisodeCredit, Genre, Movie, Season, TVShow


class GenreFactory(DjangoModelFactory):
    class Meta:
        model = Genre

    tmdb_id = factory.Sequence(lambda n: 900000 + n)
    name = factory.Sequence(lambda n: f"Genre {n}")


class MovieFactory(DjangoModelFactory):
    class Meta:
        model = Movie

    tmdb_id = factory.Sequence(lambda n: 100000 + n)
    title = factory.Sequence(lambda n: f"Movie {n}")


class TVShowFactory(DjangoModelFactory):
    class Meta:
        model = TVShow

    tmdb_id = factory.Sequence(lambda n: 200000 + n)
    name = factory.Sequence(lambda n: f"Show {n}")
    status = "Ended"


class SeasonFactory(DjangoModelFactory):
    class Meta:
        model = Season

    show = factory.SubFactory(TVShowFactory)
    tmdb_id = factory.Sequence(lambda n: 300000 + n)
    season_number = factory.Sequence(lambda n: n + 1)
    name = factory.LazyAttribute(lambda o: f"Season {o.season_number}")


class EpisodeFactory(DjangoModelFactory):
    class Meta:
        model = Episode

    season = factory.SubFactory(SeasonFactory)
    tmdb_id = factory.Sequence(lambda n: 400000 + n)
    episode_number = factory.Sequence(lambda n: (n % 50) + 1)
    name = factory.Sequence(lambda n: f"Episode {n}")


class EpisodeCreditFactory(DjangoModelFactory):
    class Meta:
        model = EpisodeCredit

    episode = factory.SubFactory(EpisodeFactory)
    cast = factory.LazyFunction(list)
    crew = factory.LazyFunction(list)
    guest_stars = factory.LazyFunction(list)
