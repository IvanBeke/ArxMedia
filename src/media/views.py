from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db import models
from .models import Movie, TVShow, Season
from .serializers import MovieSerializer, TVShowSerializer, SeasonBriefSerializer
from .tmdb import tmdb
from tracking.choices import MediaType
from tracking.status_annotations import annotate_media_user_status, annotate_season_user_status
import logging

logger = logging.getLogger(__name__)


def _parse_int_query(request, key, default):
    raw = request.query_params.get(key, default)
    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, Response({'detail': f'{key} must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)


def _providers_for_region(raw_data, region):
    results = raw_data.get('results', {}) if isinstance(raw_data, dict) else {}
    region_data = results.get(region) or results.get('US') or {}
    return {
        'region': region if region in results else 'US',
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


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def search(request):
    query = request.query_params.get('q', '')
    media_type = request.query_params.get('type', 'multi')
    page, error = _parse_int_query(request, 'page', 1)
    if error:
        return error

    if not query:
        return Response({'results': [], 'page': 1, 'total_pages': 0, 'total_results': 0})

    try:
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
@permission_classes([permissions.AllowAny])
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
@permission_classes([permissions.AllowAny])
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
@permission_classes([permissions.AllowAny])
def movie_detail(request, tmdb_id):
    region = _resolve_region(request)
    try:
        movie = Movie.objects.get(tmdb_id=tmdb_id)
    except Movie.DoesNotExist:
        try:
            movie = tmdb.sync_movie(tmdb_id)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_404_NOT_FOUND)
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
@permission_classes([permissions.AllowAny])
def movie_credits(request, tmdb_id):
    credits_data = tmdb.get_movie_credits(tmdb_id)
    return Response(credits_data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def tv_detail(request, tmdb_id):
    region = _resolve_region(request)
    try:
        show = TVShow.objects.get(tmdb_id=tmdb_id)
    except TVShow.DoesNotExist:
        try:
            show = tmdb.sync_tv_show(tmdb_id)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_404_NOT_FOUND)

    # Sync seasons that don't exist yet or have no episodes synced
    existing_seasons = Season.objects.filter(show=show)
    for sn in range(1, show.number_of_seasons + 1):
        season = existing_seasons.filter(season_number=sn).first()
        if season is None or not season.episodes.exists():
            try:
                tmdb.sync_season(show, sn)
            except Exception as exc:
                logger.warning('Failed to sync season %s for show %s: %s', sn, tmdb_id, exc)

    data = TVShowSerializer(show).data
    seasons = show.seasons.order_by('season_number').annotate(
        actual_episode_count=models.Count('episodes')
    )
    data['seasons'] = SeasonBriefSerializer(seasons, many=True).data
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


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def season_detail(request, tmdb_id, season_number):
    # Always fetch fresh from TMDB to get latest data including credits
    try:
        season_data = tmdb.get_season(tmdb_id, season_number)
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_404_NOT_FOUND)

    if request.user.is_authenticated:
        tmdb_id_int = int(tmdb_id)
        season_number_int = int(season_number)
        season_status = annotate_season_user_status(
            request.user,
            [{'tmdb_id': tmdb_id_int, 'season_number': season_number_int}],
        ).get((tmdb_id_int, season_number_int))
        if season_status:
            season_data['user_status'] = season_status

    # Return the live TMDB data directly
    return Response(season_data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def episode_credits(request, tmdb_id, season_number, episode_number):
    try:
        credits_data = tmdb.get_episode_credits(tmdb_id, season_number, episode_number)
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_404_NOT_FOUND)

    return Response(credits_data)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def tv_credits(request, tmdb_id):
    """Get TV show aggregate credits (cast and crew) from TMDB."""
    try:
        data = tmdb.get_tv_aggregate_credits(tmdb_id)
    except Exception as e:
        return Response({'detail': str(e)}, status=status.HTTP_404_NOT_FOUND)

    cast = data.get('cast', [])
    crew = data.get('crew', [])

    main_cast = [c for c in cast if c.get('total_episode_count', 0) >= 3]
    guest_stars = [c for c in cast if c.get('total_episode_count', 0) < 3]

    return Response({
        'cast': main_cast,
        'crew': crew,
        'guest_stars': guest_stars
    })
