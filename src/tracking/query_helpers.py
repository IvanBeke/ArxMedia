from django.db.models import Q

from .choices import MediaType


def media_ids_q(movie_ids, tv_ids):
    return (
        Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids)
        | Q(media_type=MediaType.TV, tmdb_id__in=tv_ids)
    )
