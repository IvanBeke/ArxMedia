import logging
import re

from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from tracking.choices import MediaType
from tracking.status_annotations import annotate_media_user_status, annotate_season_user_status
from tracking.tasks import sync_show_episode_credits

from .models import Episode, EpisodeCredit, Movie, TVShow
from .serializers import (
    MovieSerializer,
    SeasonBriefSerializer,
    SeasonHeatmapSerializer,
    SeasonSerializer,
    TVShowSerializer,
)
from .tmdb import tmdb

logger = logging.getLogger(__name__)

# Every view here is marked non_atomic_requests: TMDB calls must not run inside a
# request-wide transaction, and catalog writes are idempotent upserts.

TRENDING_MEDIA_TYPES = ('all', 'movie', 'tv', 'person')
TRENDING_TIME_WINDOWS = ('day', 'week')
# External ids are interpolated into the TMDB URL path, so only allow plain identifier characters.
EXTERNAL_ID_RE = re.compile(r'^(?=.*[A-Za-z0-9])[A-Za-z0-9._-]{1,64}$')

_NOT_FOUND = {'detail': 'Resource not found.'}
_EMPTY_SEARCH = {'results': [], 'page': 1, 'total_pages': 0, 'total_results': 0}
_EMPTY_PREFIXED_SEARCH = {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}

TMDB_FIND_EXTERNAL_SOURCES = (
    'imdb_id',
    'facebook_id',
    'instagram_id',
    'tvdb_id',
    'tiktok_id',
    'twitter_id',
    'wikidata_id',
    'youtube_id',
)


def _parse_int_query(request, key, default):
    raw = request.query_params.get(key, default)
    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, Response({'detail': f'{key} must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)


def _providers_for_region(raw_data, region):
    results = raw_data.get('results', {}) if isinstance(raw_data, dict) else {}
    region_data = results.get(region) or {}
    return {
        'region': region,
        'link': region_data.get('link'),
        'flatrate': region_data.get('flatrate', []),
        'rent': region_data.get('rent', []),
        'buy': region_data.get('buy', []),
        'free': region_data.get('free', []),
        'ads': region_data.get('ads', []),
    }


def _resolve_region(request):
    query_region = request.query_params.get('region')
    if query_region:
        return query_region.upper()
    user = getattr(request, 'user', None)
    if user and user.is_authenticated and getattr(user, 'preferred_region', None):
        return user.preferred_region.upper()
    return 'US'


def _queue_episode_credits_sync(tmdb_id: int, *, season_numbers=None, use_cache=True) -> None:
    seasons = sorted(int(number) for number in season_numbers) if season_numbers else None
    lock_key = f'credits-sync:{int(tmdb_id)}:{",".join(map(str, seasons)) if seasons else "all"}:{int(use_cache)}'
    # add() is False when an identical sync is already queued; None means the cache is down, so queue anyway.
    if cache.add(lock_key, True, getattr(settings, 'TMDB_CREDITS_SYNC_LOCK_TTL', 600)) is False:
        return
    try:
        sync_show_episode_credits.delay(int(tmdb_id), seasons, use_cache)
    except Exception:
        logger.warning('Failed to queue episode credits sync for tv %s', tmdb_id, exc_info=True)


def _sync_tv_for_read(tmdb_id, *, user_id=None, use_cache=True, only_seasons=None):
    """Sync seasons/episodes on the read path without blocking on credits.

    Mirrors refresh_tv_metadata: per-episode credits fan out to Celery so a
    cold first load pays for seasons/episodes (and TVMaze schedules) only.
    """
    show = tmdb.sync_tv_show(
        tmdb_id,
        user_id=user_id,
        use_cache=use_cache,
        only_seasons=only_seasons,
    )
    transaction.on_commit(
        lambda: _queue_episode_credits_sync(tmdb_id, season_numbers=only_seasons, use_cache=use_cache)
    )
    return show


def _serialize_tv_show_detail(show):
    data = TVShowSerializer(show).data
    seasons = show.seasons.order_by('season_number').annotate(
        actual_episode_count=models.Count('episodes'),
        computed_air_date=models.Min('episodes__air_date'),
    )
    data['seasons'] = SeasonBriefSerializer(seasons, many=True).data
    return data


def _episode_credits_payload(credit):
    return {
        'cast': credit.cast,
        'crew': credit.crew,
        'guest_stars': credit.guest_stars,
    }


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def genres_list(request):
    from .models import Genre

    genres = list(Genre.objects.order_by('name').values('tmdb_id', 'name'))
    return Response(genres)


def _dedupe_media_results(results):
    deduped = []
    seen = set()
    for result in results:
        media_type = result.get('media_type')
        media_id = result.get('id')
        key = (media_type, media_id)
        if media_type not in (MediaType.MOVIE, MediaType.TV) or not media_id or key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def _filter_by_scope(results, scope):
    if scope == MediaType.MOVIE:
        return [item for item in results if item.get('media_type') == MediaType.MOVIE]
    if scope == MediaType.TV:
        return [item for item in results if item.get('media_type') == MediaType.TV]
    return [item for item in results if item.get('media_type') in (MediaType.MOVIE, MediaType.TV)]


def _annotate_results_with_user_status(user, results):
    items = [
        {'media_type': row.get('media_type'), 'tmdb_id': row.get('id')}
        for row in results
        if row.get('media_type') in (MediaType.MOVIE, MediaType.TV)
    ]
    if not items:
        return

    status_map = annotate_media_user_status(user, items)
    for row in results:
        key = (row.get('media_type'), row.get('id'))
        if key in status_map:
            row['user_status'] = status_map[key]


def _not_found():
    return Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)


def _tag_media_type(data, media_type):
    if media_type:
        for item in data.get('results', []):
            item['media_type'] = media_type


def _decorate_media_results(request, data):
    results = data.get('results', []) if isinstance(data, dict) else []
    _normalize_media_release_date(results)
    if request.user.is_authenticated:
        _annotate_results_with_user_status(request.user, results)
    return Response(data)


def _normalize_media_release_date(results):
    for row in results:
        media_type = row.get('media_type')
        if media_type not in (MediaType.MOVIE, MediaType.TV):
            continue
        if row.get('release_date'):
            continue
        row['release_date'] = row.get('first_air_date') or ''


def _search_by_prefixed_id(query, scope):
    raw_external_id = query[1:].strip()
    if not EXTERNAL_ID_RE.match(raw_external_id):
        return dict(_EMPTY_PREFIXED_SEARCH)

    merged_results = _direct_id_results(raw_external_id)
    merged_results.extend(_find_source_results(raw_external_id))

    scoped_results = _filter_by_scope(_dedupe_media_results(merged_results), scope)
    return {
        'results': scoped_results,
        'page': 1,
        'total_pages': 1,
        'total_results': len(scoped_results),
    }


def _direct_id_results(raw_external_id):
    if not raw_external_id.isdigit():
        return []
    return _direct_id_lookups(int(raw_external_id), raw_external_id)


def _direct_id_lookups(tmdb_id, raw_external_id):
    return [
        match
        for media_type, getter in ((MediaType.MOVIE, tmdb.get_movie), (MediaType.TV, tmdb.get_tv_show))
        for match in _tagged_direct_lookup(media_type, getter, tmdb_id, raw_external_id)
    ]


def _tagged_direct_lookup(media_type, getter, tmdb_id, raw_external_id):
    try:
        payload = getter(tmdb_id)
    except Exception as exc:
        logger.warning('Failed direct %s lookup for #%s: %s', media_type, raw_external_id, exc)
        return []
    if isinstance(payload, dict) and payload.get('id'):
        payload['media_type'] = media_type
        return [payload]
    return []


def _find_source_results(raw_external_id):
    merged_results = []
    for external_source in TMDB_FIND_EXTERNAL_SOURCES:
        try:
            payload = tmdb.find_by_external_id(raw_external_id, external_source)
        except Exception as exc:
            logger.warning('Failed find lookup for #%s with source %s: %s', raw_external_id, external_source, exc)
            continue

        merged_results.extend(payload.get('movie_results', []))
        merged_results.extend(payload.get('tv_results', []))
    return merged_results


_SEARCH_BY_TYPE = {
    'movie': (tmdb.search_movies, MediaType.MOVIE),
    'tv': (tmdb.search_tv, MediaType.TV),
}


def _media_type_search_data(query, media_type, page):
    if query.startswith('#'):
        return _search_by_prefixed_id(query, media_type)
    fetcher, tag = _SEARCH_BY_TYPE.get(media_type, (tmdb.search_multi, None))
    data = fetcher(query, page)
    _tag_media_type(data, tag)
    return data


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search(request):
    query = request.query_params.get('q', '')
    media_type = request.query_params.get('type', 'multi')
    page, error = _parse_int_query(request, 'page', 1)
    if error:
        return error

    if not query:
        return Response(dict(_EMPTY_SEARCH))

    try:
        data = _media_type_search_data(query, media_type, page)
        return _decorate_media_results(request, data)
    except Exception as e:
        logger.error("TMDB API error: %s", e)
        return Response(dict(_EMPTY_SEARCH))


def _validate_trending_query(media_type, time_window):
    if media_type not in TRENDING_MEDIA_TYPES:
        return Response({'type': f'Must be one of: {", ".join(TRENDING_MEDIA_TYPES)}.'}, status=status.HTTP_400_BAD_REQUEST)
    if time_window not in TRENDING_TIME_WINDOWS:
        return Response({'window': f'Must be one of: {", ".join(TRENDING_TIME_WINDOWS)}.'}, status=status.HTTP_400_BAD_REQUEST)
    return None


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def trending(request):
    media_type = request.query_params.get('type', 'all')
    time_window = request.query_params.get('window', 'week')
    error = _validate_trending_query(media_type, time_window)
    if error:
        return error
    try:
        data = tmdb.get_trending(media_type, time_window)
        if media_type in (MediaType.MOVIE, MediaType.TV):
            _tag_media_type(data, media_type)
        return _decorate_media_results(request, data)
    except Exception as e:
        logger.error("TMDB API error: %s", e)
        return Response(dict(_EMPTY_SEARCH))


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def popular(request):
    media_type = request.query_params.get('type', 'movie')
    page, error = _parse_int_query(request, 'page', 1)
    if error:
        return error
    try:
        data = tmdb.get_popular_tv(page) if media_type == 'tv' else tmdb.get_popular_movies(page)
        _tag_media_type(data, MediaType.TV if media_type == 'tv' else MediaType.MOVIE)
        return _decorate_media_results(request, data)
    except Exception as e:
        logger.error("TMDB API error: %s", e)
        return Response(dict(_EMPTY_SEARCH))


def _load_movie(tmdb_id):
    try:
        return Movie.objects.get(tmdb_id=tmdb_id)
    except Movie.DoesNotExist:
        return _sync_movie(tmdb_id)


def _sync_movie(tmdb_id):
    try:
        return tmdb.sync_movie(tmdb_id)
    except Exception:
        logger.warning('Failed to sync movie %s from TMDB', tmdb_id, exc_info=True)
        return None


def _safe_movie_details(tmdb_id):
    try:
        return tmdb.get_movie_details(tmdb_id)
    except Exception as exc:
        logger.warning('Failed to fetch movie details for %s: %s', tmdb_id, exc)
        return {}


def _collection_payload(collection):
    if isinstance(collection, dict) and collection.get('id'):
        return {
            'id': collection.get('id'),
            'name': collection.get('name', ''),
            'poster_path': collection.get('poster_path'),
            'backdrop_path': collection.get('backdrop_path'),
        }
    return None


def _external_ids_payload(ids_payload):
    return {
        key: ids_payload[key]
        for key in ('imdb_id', 'facebook_id', 'instagram_id', 'twitter_id', 'wikidata_id', 'youtube_id')
        if ids_payload.get(key)
    }


def _attach_user_status(request, data, media_type, tmdb_id):
    if not request.user.is_authenticated:
        return
    status_map = annotate_media_user_status(
        request.user,
        [{'media_type': media_type, 'tmdb_id': tmdb_id}],
    )
    key = (media_type, int(tmdb_id))
    if key in status_map:
        data['user_status'] = status_map[key]


def _movie_payload(request, tmdb_id, movie):
    details = _safe_movie_details(tmdb_id)
    data = MovieSerializer(movie).data
    data['watch_providers'] = _providers_for_region(details.get('watch/providers') or {}, _resolve_region(request))
    data['collection'] = _collection_payload(details.get('belongs_to_collection'))
    data['external_ids'] = _external_ids_payload(details.get('external_ids') or {})
    _attach_user_status(request, data, MediaType.MOVIE, tmdb_id)
    return data


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def movie_detail(request, tmdb_id):
    movie = _load_movie(tmdb_id)
    if movie is None:
        return _not_found()
    return Response(_movie_payload(request, tmdb_id, movie))


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def movie_credits(request, tmdb_id):
    credits_data = tmdb.get_movie_credits(tmdb_id)
    return Response(credits_data)


def _sync_show_for_request(request, tmdb_id):
    try:
        return _sync_tv_for_read(tmdb_id, user_id=request.user.id)
    except Exception:
        logger.warning('Failed to sync TV show %s from TMDB', tmdb_id, exc_info=True)
        return None


def _missing_season_numbers(show, required_seasons):
    season_stats = dict(
        show.seasons.filter(season_number__gte=1, season_number__lte=required_seasons)
        .annotate(ep_count=models.Count('episodes'))
        .values_list('season_number', 'ep_count')
    )
    return [n for n in range(1, required_seasons + 1) if season_stats.get(n, 0) == 0]


def _sync_missing_seasons(show, request, tmdb_id):
    missing = _missing_season_numbers(show, show.number_of_seasons or 0)
    if not missing:
        return show
    return _sync_tv_for_read(tmdb_id, user_id=request.user.id, only_seasons=missing)


def _load_tv_show(request, tmdb_id):
    show = TVShow.objects.filter(tmdb_id=tmdb_id).first()
    if show is None:
        return _sync_show_for_request(request, tmdb_id)
    return _sync_missing_seasons(show, request, tmdb_id)


def _tv_providers(tmdb_id):
    try:
        return tmdb.get_tv_details(tmdb_id).get('watch/providers') or {}
    except Exception as exc:
        logger.warning('Failed to fetch TV providers for %s: %s', tmdb_id, exc)
        return {}


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tv_detail(request, tmdb_id):
    show = _load_tv_show(request, tmdb_id)
    if show is None:
        return _not_found()

    data = _serialize_tv_show_detail(show)
    data['watch_providers'] = _providers_for_region(_tv_providers(tmdb_id), _resolve_region(request))
    _attach_user_status(request, data, MediaType.TV, tmdb_id)
    return Response(data)


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tv_heatmap(request, tmdb_id):
    try:
        show = TVShow.objects.get(tmdb_id=tmdb_id)
    except TVShow.DoesNotExist:
        try:
            show = _sync_tv_for_read(tmdb_id, user_id=request.user.id)
        except Exception:
            logger.warning('Failed to sync TV show %s from TMDB', tmdb_id, exc_info=True)
            return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    seasons = show.seasons.filter(season_number__gte=1).prefetch_related(
        models.Prefetch('episodes', queryset=Episode.objects.annotate(
            display_number=Window(
                expression=RowNumber(),
                partition_by=[F('season_id')],
                order_by=[F('air_date').asc(), F('episode_number').asc()],
            )
        ).only('season_id', 'air_date', 'episode_number', 'vote_average'))
    ).order_by('season_number')
    data = SeasonHeatmapSerializer(seasons, many=True).data
    return Response(data)


class MetadataRefreshThrottle(UserRateThrottle):
    scope = 'metadata_refresh'


@transaction.non_atomic_requests
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([UserRateThrottle, MetadataRefreshThrottle])
def refresh_movie_metadata(request, tmdb_id):
    try:
        movie = tmdb.sync_movie(tmdb_id, use_cache=False)
    except Exception:
        logger.warning('Failed to refresh movie %s from TMDB', tmdb_id, exc_info=True)
        return Response({'detail': 'Unable to refresh metadata right now.'}, status=status.HTTP_502_BAD_GATEWAY)

    return Response(MovieSerializer(movie).data)


@transaction.non_atomic_requests
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([UserRateThrottle, MetadataRefreshThrottle])
def refresh_tv_metadata(request, tmdb_id):
    try:
        show = _sync_tv_for_read(
            tmdb_id,
            user_id=request.user.id,
            use_cache=False,
        )
    except Exception:
        logger.warning('Failed to refresh TV show %s from TMDB', tmdb_id, exc_info=True)
        return Response({'detail': 'Unable to refresh metadata right now.'}, status=status.HTTP_502_BAD_GATEWAY)

    show.refresh_from_db()
    return Response(_serialize_tv_show_detail(show))


def _season_with_episodes(show, season_number):
    return show.seasons.filter(season_number=season_number).select_related('show').prefetch_related('episodes__credits').first()


def _sync_missing_season(request, show, tmdb_id, season_number):
    try:
        _sync_tv_for_read(tmdb_id, user_id=request.user.id, only_seasons=[season_number])
    except Exception:
        logger.warning('Failed to fetch season %s for show %s from TMDB', season_number, tmdb_id, exc_info=True)
        return None
    return _season_with_episodes(show, season_number)


def _load_season_for_read(request, show, tmdb_id, season_number):
    season = _season_with_episodes(show, season_number)
    if season is not None and season.episodes.exists():
        return season
    return _sync_missing_season(request, show, tmdb_id, season_number)


def _merge_live_season_fields(season_data, live):
    credits = live.get('credits') or {}
    season_data['credits'] = {
        'cast': credits.get('cast') or [],
        'crew': credits.get('crew') or [],
    }
    vote_average = live.get('vote_average')
    if isinstance(vote_average, (int, float)):
        season_data['vote_average'] = vote_average
        vote_count = live.get('vote_count')
        season_data['vote_count'] = vote_count if isinstance(vote_count, int) else 0
    _merge_live_season_external_ids(season_data, live.get('external_ids') or {})


def _merge_live_season_external_ids(season_data, live_external):
    if live_external:
        merged_ids = dict(season_data.get('external_ids') or {})
        merged_ids.update({k: v for k, v in live_external.items() if v})
        season_data['external_ids'] = merged_ids


def _merge_live_season_data(season_data, tmdb_id, season_number):
    try:
        live = tmdb.get_season(tmdb_id, season_number)
    except Exception as exc:
        logger.warning('Failed to fetch season credits for show %s season %s: %s', tmdb_id, season_number, exc)
        season_data.setdefault('credits', {'cast': [], 'crew': []})
        return
    if isinstance(live, dict):
        _merge_live_season_fields(season_data, live)


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def season_detail(request, tmdb_id, season_number):
    tmdb_id = int(tmdb_id)
    season_number = int(season_number)

    show = _load_tv_show(request, tmdb_id)
    if show is None:
        return _not_found()

    season = _load_season_for_read(request, show, tmdb_id, season_number)
    if season is None:
        return _not_found()

    season_data = SeasonSerializer(season).data
    season_data['show_name'] = show.name
    season_data['show_external_ids'] = show.external_ids or {}
    _merge_live_season_data(season_data, tmdb_id, season_number)

    season_status = annotate_season_user_status(
        request.user,
        [{'tmdb_id': tmdb_id, 'season_number': season_number}],
    ).get((tmdb_id, season_number))
    if season_status:
        season_data['user_status'] = season_status

    return Response(season_data)


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def season_credits(request, tmdb_id, season_number):
    """Get season aggregate credits (cast with episode counts, crew) from TMDB."""
    try:
        data = tmdb.get_season_aggregate_credits(tmdb_id, season_number)
    except Exception:
        logger.warning('Failed to fetch season aggregate credits for show %s season %s from TMDB', tmdb_id, season_number, exc_info=True)
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'cast': data.get('cast', []) if isinstance(data, dict) else [],
        'crew': data.get('crew', []) if isinstance(data, dict) else [],
    })


def _episode_for(show, season_number, episode_number):
    season = show.seasons.filter(season_number=season_number).first()
    return season.episodes.filter(episode_number=episode_number).first() if season else None


def _sync_episode_for_read(request, show, tmdb_id, season_number, episode_number):
    try:
        _sync_tv_for_read(tmdb_id, user_id=request.user.id, only_seasons=[season_number])
    except Exception:
        logger.warning(
            'Failed to sync season %s for show %s while loading episode credits',
            season_number,
            tmdb_id,
            exc_info=True,
        )
        return None
    return _episode_for(show, season_number, episode_number)


def _load_episode_for_read(request, show, tmdb_id, season_number, episode_number):
    episode = _episode_for(show, season_number, episode_number)
    if episode is not None:
        return episode
    return _sync_episode_for_read(request, show, tmdb_id, season_number, episode_number)


def _episode_credits_for(show, tmdb_id, season_number, episode_number, episode):
    credit = EpisodeCredit.objects.filter(episode=episode).first()
    if credit is None:
        try:
            credit = tmdb.sync_episode_credits(tmdb_id, season_number, episode_number, show=show)
        except Exception:
            logger.warning(
                'Failed to fetch episode credits for show %s season %s episode %s from TMDB',
                tmdb_id,
                season_number,
                episode_number,
                exc_info=True,
            )
            return _not_found()
    return Response(_episode_credits_payload(credit))


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def episode_credits(request, tmdb_id, season_number, episode_number):
    tmdb_id = int(tmdb_id)
    season_number = int(season_number)
    episode_number = int(episode_number)

    show = _load_tv_show(request, tmdb_id)
    if show is None:
        return _not_found()

    episode = _load_episode_for_read(request, show, tmdb_id, season_number, episode_number)
    if episode is None:
        return _not_found()

    return _episode_credits_for(show, tmdb_id, season_number, episode_number, episode)


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tv_credits(request, tmdb_id):
    """Get TV show aggregate credits (cast and crew) from TMDB."""
    try:
        data = tmdb.get_tv_aggregate_credits(tmdb_id)
    except Exception:
        logger.warning('Failed to fetch TV aggregate credits for show %s from TMDB', tmdb_id, exc_info=True)
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    cast = data.get('cast', []) if isinstance(data, dict) else []
    crew = data.get('crew', []) if isinstance(data, dict) else []

    return Response({
        'cast': cast,
        'crew': crew,
    })


def _annotate_recommendation_results(user, results, media_type):
    for item in results:
        item['media_type'] = media_type
    _normalize_media_release_date(results)
    if user and user.is_authenticated:
        status_map = annotate_media_user_status(
            user,
            [{'media_type': media_type, 'tmdb_id': item.get('id')} for item in results if item.get('id')],
        )
        for item in results:
            key = (media_type, item.get('id'))
            if key in status_map:
                item['user_status'] = status_map[key]


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def movie_external_ids(request, tmdb_id):
    try:
        data = tmdb.get_movie_details(tmdb_id).get('external_ids')
    except Exception:
        logger.warning('Failed to fetch movie external ids for %s from TMDB', tmdb_id, exc_info=True)
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(data if isinstance(data, dict) else {})


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tv_external_ids(request, tmdb_id):
    try:
        show = TVShow.objects.filter(tmdb_id=tmdb_id).first()
        stored = dict(show.external_ids) if show and show.external_ids else {}
    except Exception:
        stored = {}
    try:
        live = tmdb.get_tv_details(tmdb_id).get('external_ids')
        if isinstance(live, dict):
            stored.update({k: v for k, v in live.items() if v})
    except Exception as exc:
        logger.warning('Failed to fetch TV external ids for %s: %s', tmdb_id, exc)
        if not stored:
            return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(stored)


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def episode_external_ids(request, tmdb_id, season_number, episode_number):
    episode = Episode.objects.filter(
        season__show__tmdb_id=tmdb_id, season__season_number=season_number, episode_number=episode_number,
    ).first()
    stored = dict(episode.external_ids) if episode and episode.external_ids else {}
    try:
        live = tmdb.get_episode_external_ids(tmdb_id, season_number, episode_number)
        if isinstance(live, dict):
            stored.update({k: v for k, v in live.items() if v})
    except Exception as exc:
        logger.warning('Failed to fetch episode external ids for %s S%sE%s: %s', tmdb_id, season_number, episode_number, exc)
        if not stored:
            return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(stored)


def _recommendations_response(request, tmdb_id, fetcher, media_type, label):
    page, error = _parse_int_query(request, 'page', 1)
    if error:
        return error
    try:
        data = fetcher(tmdb_id, page)
    except Exception:
        logger.warning('Failed to fetch %s recommendations for %s from TMDB', label, tmdb_id, exc_info=True)
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
    results = data.get('results', []) if isinstance(data, dict) else []
    _annotate_recommendation_results(request.user, results, media_type)
    return Response(data)


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def movie_recommendations(request, tmdb_id):
    return _recommendations_response(request, tmdb_id, tmdb.get_movie_recommendations, MediaType.MOVIE, 'movie')


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tv_recommendations(request, tmdb_id):
    return _recommendations_response(request, tmdb_id, tmdb.get_tv_recommendations, MediaType.TV, 'TV')


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def collection_detail(request, collection_id):
    try:
        data = tmdb.get_collection(collection_id)
    except Exception:
        logger.warning('Failed to fetch collection %s from TMDB', collection_id, exc_info=True)
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not isinstance(data, dict) or not data.get('id'):
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
    parts = data.get('parts', []) or []
    _annotate_recommendation_results(request.user, parts, MediaType.MOVIE)
    return Response(data)


def _person_profile_url(profile_path):
    if profile_path:
        return f'https://image.tmdb.org/t/p/w500{profile_path}'
    return None


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def person_detail(request, person_id):
    try:
        data = tmdb.get_person(person_id)
    except Exception:
        logger.warning('Failed to fetch person %s from TMDB', person_id, exc_info=True)
        return _not_found()
    if not isinstance(data, dict) or not data.get('id'):
        return _not_found()
    return _person_profile_response(person_id, data)


def _try_merge_person_external_ids(person_id, data):
    try:
        ids_payload = tmdb.get_person_external_ids(person_id)
    except Exception as exc:
        logger.warning('Failed to fetch person external ids for %s: %s', person_id, exc)
        return
    if isinstance(ids_payload, dict) and (external_ids := {k: v for k, v in ids_payload.items() if v}):
        data['external_ids'] = external_ids


def _person_profile_response(person_id, data):
    _try_merge_person_external_ids(person_id, data)
    data.setdefault('external_ids', {})
    data['profile_url'] = _person_profile_url(data.get('profile_path'))
    return Response(data)


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def people_search(request):
    query = request.query_params.get('q', '').strip()
    page, error = _parse_int_query(request, 'page', 1)
    if error:
        return error

    if not query:
        return Response({'results': [], 'page': 1, 'total_pages': 0, 'total_results': 0})

    try:
        data = tmdb.search_people(query, page)
    except Exception as e:
        logger.error("TMDB API error: %s", e)
        return Response({'results': [], 'page': 1, 'total_pages': 0, 'total_results': 0})

    if not isinstance(data, dict):
        return Response({'results': [], 'page': 1, 'total_pages': 0, 'total_results': 0})
    return Response(data)


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def person_credits(request, person_id):
    try:
        data = tmdb.get_person_combined_credits(person_id)
    except Exception:
        logger.warning('Failed to fetch person credits for %s from TMDB', person_id, exc_info=True)
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not isinstance(data, dict):
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
    cast = data.get('cast', []) if isinstance(data.get('cast'), list) else []
    crew = data.get('crew', []) if isinstance(data.get('crew'), list) else []
    _annotate_recommendation_results(request.user, [i for i in cast if i.get('media_type') == MediaType.MOVIE], MediaType.MOVIE)
    _annotate_recommendation_results(request.user, [i for i in cast if i.get('media_type') == MediaType.TV], MediaType.TV)
    _annotate_recommendation_results(request.user, [i for i in crew if i.get('media_type') == MediaType.MOVIE], MediaType.MOVIE)
    _annotate_recommendation_results(request.user, [i for i in crew if i.get('media_type') == MediaType.TV], MediaType.TV)
    return Response({'cast': cast, 'crew': crew})


@transaction.non_atomic_requests
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def person_external_ids(request, person_id):
    try:
        data = tmdb.get_person_external_ids(person_id)
    except Exception:
        logger.warning('Failed to fetch person external ids for %s from TMDB', person_id, exc_info=True)
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(data if isinstance(data, dict) else {})
