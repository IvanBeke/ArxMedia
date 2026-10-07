from django.db.models import Q

from .choices import MediaType, WatchEntryMediaType


def media_ids_q(movie_ids, tv_ids):
    return (
        Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids)
        | Q(media_type=MediaType.TV, tmdb_id__in=tv_ids)
    )


def build_season_map(pairs):
    """Map (show tmdb_id, season_number) to its Season (or None) in one query."""
    from media.models import Season

    unique_pairs = {(int(tmdb_id), int(season_number)) for tmdb_id, season_number in pairs}
    if not unique_pairs:
        return {}
    seasons_by_key = {
        (season.show.tmdb_id, season.season_number): season
        for season in Season.objects.filter(show__tmdb_id__in={tmdb_id for tmdb_id, _ in unique_pairs}).select_related('show')
    }
    return {pair: seasons_by_key.get(pair) for pair in unique_pairs}


def watch_entry_context(entries):
    """Serializer context with every movie, show, season and episode a page of watch entries needs."""
    from media.models import Episode, Movie, TVShow

    movie_ids = {entry.tmdb_id for entry in entries if entry.media_type == WatchEntryMediaType.MOVIE}
    episode_entries = [entry for entry in entries if entry.media_type == WatchEntryMediaType.EPISODE]
    season_map = build_season_map(
        (entry.tmdb_id, entry.season_number) for entry in episode_entries if entry.season_number
    )
    season_keys = {season.id: key for key, season in season_map.items() if season is not None}
    episode_map = {}
    if season_keys:
        episode_numbers = {entry.episode_number for entry in episode_entries if entry.episode_number}
        for episode in Episode.objects.filter(season_id__in=season_keys, episode_number__in=episode_numbers):
            episode_map[(*season_keys[episode.season_id], episode.episode_number)] = episode
    return {
        'movie_map': {movie.tmdb_id: movie for movie in Movie.objects.filter(tmdb_id__in=movie_ids)},
        'tv_map': {
            show.tmdb_id: show
            for show in TVShow.objects.filter(tmdb_id__in={entry.tmdb_id for entry in episode_entries})
        },
        'season_map': season_map,
        'episode_map': episode_map,
    }
