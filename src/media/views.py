import logging

from django.db import models
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from tracking.choices import MediaType
from tracking.status_annotations import annotate_media_user_status, annotate_season_user_status
from tracking.status_sync import refresh_all_statuses_for_show

from .models import EpisodeCredit, Movie, Season, TVShow
from .serializers import MovieSerializer, SeasonBriefSerializer, SeasonSerializer, TVShowSerializer
from .tmdb import tmdb

logger = logging.getLogger(__name__)

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


def _serialize_tv_show_detail(show):
    data = TVShowSerializer(show).data
    seasons = show.seasons.order_by('season_number').annotate(
        actual_episode_count=models.Count('episodes')
    )
    data['seasons'] = SeasonBriefSerializer(seasons, many=True).data
    return data


def _episode_credits_payload(credit):
    return {
        'cast': credit.cast,
        'crew': credit.crew,
        'guest_stars': credit.guest_stars,
    }


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


def _search_by_prefixed_id(query, scope):
    raw_external_id = query[1:].strip()
    if not raw_external_id:
        return {'results': [], 'page': 1, 'total_pages': 1, 'total_results': 0}

    merged_results = []

    if raw_external_id.isdigit():
        tmdb_id = int(raw_external_id)
        for media_type, getter in ((MediaType.MOVIE, tmdb.get_movie), (MediaType.TV, tmdb.get_tv_show)):
            try:
                payload = getter(tmdb_id)
            except Exception as exc:
                logger.warning('Failed direct %s lookup for #%s: %s', media_type, raw_external_id, exc)
                continue
            if isinstance(payload, dict) and payload.get('id'):
                payload['media_type'] = media_type
                merged_results.append(payload)

    for external_source in TMDB_FIND_EXTERNAL_SOURCES:
        try:
            payload = tmdb.find_by_external_id(raw_external_id, external_source)
        except Exception as exc:
            logger.warning('Failed find lookup for #%s with source %s: %s', raw_external_id, external_source, exc)
            continue

        merged_results.extend(payload.get('movie_results', []))
        merged_results.extend(payload.get('tv_results', []))

    deduped = _dedupe_media_results(merged_results)
    scoped_results = _filter_by_scope(deduped, scope)
    return {
        'results': scoped_results,
        'page': 1,
        'total_pages': 1,
        'total_results': len(scoped_results),
    }


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search(request):
    query = request.query_params.get('q', '')
    media_type = request.query_params.get('type', 'multi')
    page, error = _parse_int_query(request, 'page', 1)
    if error:
        return error

    if not query:
        return Response({'results': [], 'page': 1, 'total_pages': 0, 'total_results': 0})

    try:
        if query.startswith('#'):
            data = _search_by_prefixed_id(query, media_type)
        else:
            if media_type == 'movie':
                data = tmdb.search_movies(query, page)
                for item in data.get('results', []):
                    item['media_type'] = MediaType.MOVIE
            elif media_type == 'tv':
                data = tmdb.search_tv(query, page)
                for item in data.get('results', []):
                    item['media_type'] = MediaType.TV
            else:
                data = tmdb.search_multi(query, page)

        if request.user.is_authenticated:
            _annotate_results_with_user_status(request.user, data.get('results', []))

        return Response(data)
    except Exception as e:
        logger.error(f"TMDB API error: {e}")
        return Response({'results': [], 'page': 1, 'total_pages': 0, 'total_results': 0})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def trending(request):
    media_type = request.query_params.get('type', 'all')
    time_window = request.query_params.get('window', 'week')
    try:
        data = tmdb.get_trending(media_type, time_window)
        if media_type in (MediaType.MOVIE, MediaType.TV):
            for result in data.get('results', []):
                result['media_type'] = media_type

        if request.user.is_authenticated:
            items = []
            for result in data.get('results', []):
                if result.get('media_type') in (MediaType.MOVIE, MediaType.TV):
                    items.append({
                        'media_type': result['media_type'],
                        'tmdb_id': result.get('id'),
                    })
            status_map = annotate_media_user_status(request.user, items)
            for result in data.get('results', []):
                key = (result.get('media_type'), result.get('id'))
                if key in status_map:
                    result['user_status'] = status_map[key]
        return Response(data)
    except Exception as e:
        logger.error(f"TMDB API error: {e}")
        return Response({'results': [], 'page': 1, 'total_pages': 0, 'total_results': 0})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def popular(request):
    media_type = request.query_params.get('type', 'movie')
    page, error = _parse_int_query(request, 'page', 1)
    if error:
        return error
    try:
        if media_type == 'tv':
            data = tmdb.get_popular_tv(page)
            resolved_media_type = MediaType.TV
        else:
            data = tmdb.get_popular_movies(page)

        if media_type != 'tv':
            resolved_media_type = MediaType.MOVIE

        for result in data.get('results', []):
            result['media_type'] = resolved_media_type

        if request.user.is_authenticated:
            status_map = annotate_media_user_status(
                request.user,
                [
                    {'media_type': resolved_media_type, 'tmdb_id': item.get('id')}
                    for item in data.get('results', [])
                ],
            )
            for result in data.get('results', []):
                key = (resolved_media_type, result.get('id'))
                if key in status_map:
                    result['user_status'] = status_map[key]

        return Response(data)
    except Exception as e:
        logger.error(f"TMDB API error: {e}")
        return Response({'results': [], 'page': 1, 'total_pages': 0, 'total_results': 0})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def movie_detail(request, tmdb_id):
    region = _resolve_region(request)
    try:
        movie = Movie.objects.get(tmdb_id=tmdb_id)
    except Movie.DoesNotExist:
        try:
            movie = tmdb.sync_movie(tmdb_id)
        except Exception:
            logger.warning('Failed to sync movie %s from TMDB', tmdb_id, exc_info=True)
            return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)
    data = MovieSerializer(movie).data
    try:
        providers = tmdb.get_movie_watch_providers(tmdb_id)
        data['watch_providers'] = _providers_for_region(providers, region)
    except Exception as exc:
        logger.warning('Failed to fetch movie providers for %s: %s', tmdb_id, exc)
        data['watch_providers'] = _providers_for_region({}, region)

    if request.user.is_authenticated:
        status_map = annotate_media_user_status(
            request.user,
            [{'media_type': MediaType.MOVIE, 'tmdb_id': tmdb_id}],
        )
        key = (MediaType.MOVIE, int(tmdb_id))
        if key in status_map:
            data['user_status'] = status_map[key]

    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def movie_credits(request, tmdb_id):
    credits_data = tmdb.get_movie_credits(tmdb_id)
    return Response(credits_data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tv_detail(request, tmdb_id):
    region = _resolve_region(request)
    try:
        show = TVShow.objects.get(tmdb_id=tmdb_id)
    except TVShow.DoesNotExist:
        try:
            show = tmdb.sync_tv_show(tmdb_id)
        except Exception:
            logger.warning('Failed to sync TV show %s from TMDB', tmdb_id, exc_info=True)
            return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Sync seasons that don't exist yet or have no episodes synced
    existing_seasons = Season.objects.filter(show=show)
    for sn in range(1, show.number_of_seasons + 1):
        season = existing_seasons.filter(season_number=sn).first()
        if season is None or not season.episodes.exists():
            try:
                tmdb.sync_season(show, sn)
            except Exception as exc:
                logger.warning('Failed to sync season %s for show %s: %s', sn, tmdb_id, exc)

    data = _serialize_tv_show_detail(show)
    try:
        providers = tmdb.get_tv_watch_providers(tmdb_id)
        data['watch_providers'] = _providers_for_region(providers, region)
    except Exception as exc:
        logger.warning('Failed to fetch TV providers for %s: %s', tmdb_id, exc)
        data['watch_providers'] = _providers_for_region({}, region)

    if request.user.is_authenticated:
        status_map = annotate_media_user_status(
            request.user,
            [{'media_type': MediaType.TV, 'tmdb_id': tmdb_id}],
        )
        key = (MediaType.TV, int(tmdb_id))
        if key in status_map:
            data['user_status'] = status_map[key]

    return Response(data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def refresh_movie_metadata(request, tmdb_id):
    try:
        movie = tmdb.sync_movie(tmdb_id)
    except Exception:
        logger.warning('Failed to refresh movie %s from TMDB', tmdb_id, exc_info=True)
        return Response({'detail': 'Unable to refresh metadata right now.'}, status=status.HTTP_502_BAD_GATEWAY)

    return Response(MovieSerializer(movie).data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def refresh_tv_metadata(request, tmdb_id):
    try:
        show = tmdb.sync_tv_show(tmdb_id)
    except Exception:
        logger.warning('Failed to refresh TV show %s from TMDB', tmdb_id, exc_info=True)
        return Response({'detail': 'Unable to refresh metadata right now.'}, status=status.HTTP_502_BAD_GATEWAY)

    season_numbers = set(range(1, max((show.number_of_seasons or 0), 0) + 1))
    season_numbers.update(show.seasons.values_list('season_number', flat=True))
    for season_number in sorted(season_numbers):
        try:
            tmdb.sync_season(show, season_number)
        except Exception:
            logger.warning(
                'Failed to refresh season %s for show %s from TMDB',
                season_number,
                tmdb_id,
                exc_info=True,
            )
            continue

        season = show.seasons.filter(season_number=season_number).first()
        if season is None:
            continue

        for episode_number in season.episodes.values_list('episode_number', flat=True):
            try:
                tmdb.sync_episode_credits(int(tmdb_id), season_number, int(episode_number), show=show)
            except Exception:
                logger.warning(
                    'Failed to refresh episode credits for show %s season %s episode %s from TMDB',
                    tmdb_id,
                    season_number,
                    episode_number,
                    exc_info=True,
                )

    show.refresh_from_db()
    refresh_all_statuses_for_show(int(tmdb_id))
    return Response(_serialize_tv_show_detail(show))


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def season_detail(request, tmdb_id, season_number):
    tmdb_id = int(tmdb_id)
    season_number = int(season_number)

    try:
        show = TVShow.objects.get(tmdb_id=tmdb_id)
    except TVShow.DoesNotExist:
        try:
            show = tmdb.sync_tv_show(tmdb_id)
        except Exception:
            logger.warning('Failed to sync TV show %s from TMDB', tmdb_id, exc_info=True)
            return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    season = show.seasons.filter(season_number=season_number).prefetch_related('episodes__credits').first()
    if season is None or not season.episodes.exists():
        try:
            tmdb.sync_season(show, season_number)
            season = show.seasons.filter(season_number=season_number).prefetch_related('episodes__credits').first()
        except Exception:
            logger.warning('Failed to fetch season %s for show %s from TMDB', season_number, tmdb_id, exc_info=True)
            return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    if season is None:
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    season_data = SeasonSerializer(season).data

    season_status = annotate_season_user_status(
        request.user,
        [{'tmdb_id': tmdb_id, 'season_number': season_number}],
    ).get((tmdb_id, season_number))
    if season_status:
        season_data['user_status'] = season_status

    return Response(season_data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def episode_credits(request, tmdb_id, season_number, episode_number):
    tmdb_id = int(tmdb_id)
    season_number = int(season_number)
    episode_number = int(episode_number)

    try:
        show = TVShow.objects.get(tmdb_id=tmdb_id)
    except TVShow.DoesNotExist:
        try:
            show = tmdb.sync_tv_show(tmdb_id)
        except Exception:
            logger.warning('Failed to sync TV show %s from TMDB', tmdb_id, exc_info=True)
            return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    season = show.seasons.filter(season_number=season_number).first()
    episode = season.episodes.filter(episode_number=episode_number).first() if season else None

    if episode is None:
        try:
            tmdb.sync_season(show, season_number)
            season = show.seasons.filter(season_number=season_number).first()
            episode = season.episodes.filter(episode_number=episode_number).first() if season else None
        except Exception:
            logger.warning(
                'Failed to sync season %s for show %s while loading episode credits',
                season_number,
                tmdb_id,
                exc_info=True,
            )

    if episode is None:
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    credit = EpisodeCredit.objects.filter(episode=episode).first()
    if credit:
        return Response(_episode_credits_payload(credit))

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
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(_episode_credits_payload(credit))


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tv_credits(request, tmdb_id):
    """Get TV show aggregate credits (cast and crew) from TMDB."""
    try:
        data = tmdb.get_tv_aggregate_credits(tmdb_id)
    except Exception:
        logger.warning('Failed to fetch TV aggregate credits for show %s from TMDB', tmdb_id, exc_info=True)
        return Response({'detail': 'Resource not found.'}, status=status.HTTP_404_NOT_FOUND)

    cast = data.get('cast', [])
    crew = data.get('crew', [])

    main_cast = [c for c in cast if c.get('total_episode_count', 0) >= 3]
    guest_stars = [c for c in cast if c.get('total_episode_count', 0) < 3]

    return Response({
        'cast': main_cast,
        'crew': crew,
        'guest_stars': guest_stars
    })
