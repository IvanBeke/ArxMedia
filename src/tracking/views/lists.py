import logging

from accounts.privacy import can_view_account_content, get_viewer_relationship
from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from ..choices import (
    ListPrivacy,
    MediaType,
)
from ..models import (
    CustomList,
    ListCollaborator,
    ListItem,
)
from ..serializers import (
    CustomListSerializer,
    ListItemSerializer,
)
from ..status_annotations import annotate_media_user_status
from ._helpers import (
    _apply_in_watchlist_filter,
    _apply_missing_rating_filter,
    _apply_secondary_title_ordering,
    _apply_status_filter,
    _compute_mixed_runtime_and_counts,
    _ensure_local_metadata,
    _normalize_sort,
    _parse_bool_param,
    _parse_multi_param,
)

logger = logging.getLogger(__name__)


def _can_view_public_lists(viewer, owner) -> bool:
    relationship = get_viewer_relationship(viewer, owner)
    return can_view_account_content(owner.account_visibility, relationship)

def _can_access_list(viewer, custom_list) -> bool:
    if viewer.is_staff:
        return True
    if custom_list.user_id == viewer.id:
        return True
    if ListCollaborator.objects.filter(custom_list=custom_list, user=viewer).exists():
        return True
    if custom_list.privacy == ListPrivacy.PRIVATE:
        return False
    return _can_view_public_lists(viewer, custom_list.user)


class CustomListListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return CustomList.objects.all()

        visible_public_lists = Q(privacy=ListPrivacy.PUBLIC) & (
            Q(user__account_visibility='public') |
            Q(
                user__account_visibility='friends_only',
                user__followers__follower=self.request.user,
                user__following__following=self.request.user,
            )
        )

        return CustomList.objects.filter(
            Q(user=self.request.user) |
            Q(collaboratorships__user=self.request.user) |
            visible_public_lists
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CustomListDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomList.objects.all()

    def get_object(self):
        obj = super().get_object()
        if not _can_access_list(self.request.user, obj):
            raise PermissionDenied('You do not have permission to access this list.')
        return obj

    def perform_update(self, serializer):
        # Only owner can update
        if serializer.instance.user != self.request.user:
            raise PermissionDenied('You can only edit your own lists.')
        serializer.save()

    def perform_destroy(self, instance):
        # Only owner can delete
        if instance.user != self.request.user:
            raise PermissionDenied('You can only delete your own lists.')
        instance.delete()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ListItemListCreateView(generics.ListCreateAPIView):
    serializer_class = ListItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        list_id = self.kwargs.get('list_id')
        try:
            custom_list = CustomList.objects.get(id=list_id)
        except CustomList.DoesNotExist:
            raise PermissionDenied('List not found.')

        if not _can_access_list(self.request.user, custom_list):
            raise PermissionDenied('You do not have permission to access this list.')

        queryset = ListItem.objects.filter(custom_list=custom_list).select_related('custom_list')

        media_type = (self.request.query_params.get('media_type') or '').strip().lower()
        if media_type in (MediaType.MOVIE, MediaType.TV):
            queryset = queryset.filter(media_type=media_type)

        # Search by title
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            from media.models import Movie, TVShow
            movie_ids = Movie.objects.filter(title__icontains=search).values_list('tmdb_id', flat=True)
            tv_ids = TVShow.objects.filter(name__icontains=search).values_list('tmdb_id', flat=True)
            queryset = queryset.filter(
                Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids) |
                Q(media_type=MediaType.TV, tmdb_id__in=tv_ids)
            ).distinct()

        selected_genres = _parse_multi_param(self.request.query_params, 'genres')
        if selected_genres:
            from media.models import Movie, TVShow
            movie_ids = Movie.objects.filter(genres__name__in=selected_genres).values_list('tmdb_id', flat=True)
            tv_ids = TVShow.objects.filter(genres__name__in=selected_genres).values_list('tmdb_id', flat=True)
            queryset = queryset.filter(
                Q(media_type=MediaType.MOVIE, tmdb_id__in=movie_ids)
                | Q(media_type=MediaType.TV, tmdb_id__in=tv_ids)
            ).distinct()

        selected_statuses = _parse_multi_param(self.request.query_params, 'status')
        if selected_statuses:
            queryset = _apply_status_filter(queryset, self.request.user, selected_statuses)

        missing_rating = _parse_bool_param(self.request.query_params.get('missing_rating'))
        if missing_rating is True:
            queryset = _apply_missing_rating_filter(queryset, self.request.user)

        in_watchlist = _parse_bool_param(self.request.query_params.get('in_watchlist'))
        if in_watchlist is True:
            queryset = _apply_in_watchlist_filter(queryset, self.request.user)

        sort_key, direction = _normalize_sort(
            self.request.query_params.get('sort'),
            self.request.query_params.get('direction'),
            default_sort='custom_order',
            default_direction='asc',
        )
        valid_sorts = {
            'added_at', 'custom_order', 'title', 'release_date',
            'provider_rating', 'user_rating', 'runtime', 'total_episodes', 'vote_count',
            'watched_date', 'started_date', 'last_watched', 'progress_percent', 'episodes_left', 'time_left', 'next_episode_date'
        }
        if sort_key not in valid_sorts:
            sort_key = 'custom_order'

        queryset = _apply_secondary_title_ordering(queryset, sort_key, direction, user=self.request.user)
        return queryset

    def perform_create(self, serializer):
        list_id = self.kwargs.get('list_id')
        try:
            custom_list = CustomList.objects.get(id=list_id)
        except CustomList.DoesNotExist:
            raise PermissionDenied('List not found.')
        is_owner = custom_list.user_id == self.request.user.id
        is_collaborator = ListCollaborator.objects.filter(custom_list=custom_list, user=self.request.user).exists()
        if not (is_owner or is_collaborator):
            raise PermissionDenied('You can only add items to your lists or lists where you collaborate.')
        from django.db.models import Max

        media_type = serializer.validated_data.get('media_type')
        tmdb_id = serializer.validated_data.get('tmdb_id')
        _ensure_local_metadata(media_type, tmdb_id)

        with transaction.atomic():
            max_order = ListItem.objects.filter(custom_list=custom_list).aggregate(m=Max('custom_order'))['m']
            next_order = (max_order + 1) if max_order is not None else 0
            try:
                serializer.save(custom_list=custom_list, custom_order=next_order)
            except IntegrityError:
                raise ValidationError({'detail': 'Item is already in this list.'})

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        items = page if page is not None else queryset

        from media.models import Movie, TVShow
        movie_ids = [entry.tmdb_id for entry in items if entry.media_type == MediaType.MOVIE]
        tv_ids = [entry.tmdb_id for entry in items if entry.media_type == MediaType.TV]
        movie_map = {m.tmdb_id: m for m in Movie.objects.filter(tmdb_id__in=movie_ids)}
        tv_map = {s.tmdb_id: s for s in TVShow.objects.filter(tmdb_id__in=tv_ids)}
        status_map = annotate_media_user_status(
            request.user,
            [{'media_type': entry.media_type, 'tmdb_id': entry.tmdb_id} for entry in items],
        )

        context = self.get_serializer_context()
        context.update({'movie_map': movie_map, 'tv_map': tv_map, 'status_map': status_map})
        serializer = self.get_serializer(items, many=True, context=context)
        total_runtime_minutes, counts = _compute_mixed_runtime_and_counts(queryset)

        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data['total_runtime_minutes'] = total_runtime_minutes
            response.data['counts'] = counts
            return response

        return Response({
            'results': serializer.data,
            'count': queryset.count(),
            'next': None,
            'previous': None,
            'total_runtime_minutes': total_runtime_minutes,
            'counts': counts,
        })


class ListItemDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = ListItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ListItem.objects.filter(
            Q(custom_list__user=self.request.user) |
            Q(custom_list__collaboratorships__user=self.request.user)
        ).distinct()


class ListItemReorderView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        list_id = self.kwargs.get('list_id')
        try:
            custom_list = CustomList.objects.get(id=list_id)
        except CustomList.DoesNotExist:
            raise PermissionDenied('List not found.')

        if not _can_access_list(request.user, custom_list):
            raise PermissionDenied('You do not have permission to access this list.')

        is_owner = custom_list.user_id == request.user.id
        is_collaborator = ListCollaborator.objects.filter(custom_list=custom_list, user=request.user).exists()
        if not (is_owner or is_collaborator):
            raise PermissionDenied('You can only reorder items in your lists or lists where you collaborate.')

        ordered_ids = request.data.get('custom_order')
        if not isinstance(ordered_ids, list):
            raise ValidationError({'custom_order': 'custom_order must be a list of item ids.'})

        try:
            ordered_ids = [int(i) for i in ordered_ids]
        except (TypeError, ValueError):
            raise ValidationError({'custom_order': 'custom_order must contain integers.'})

        if len(ordered_ids) != len(set(ordered_ids)):
            raise ValidationError({'custom_order': 'custom_order must not contain duplicates.'})

        existing_ids = set(ListItem.objects.filter(custom_list=custom_list).values_list('id', flat=True))
        if set(ordered_ids) != existing_ids:
            raise ValidationError({'custom_order': 'custom_order must contain all item ids for this list exactly once.'})

        # Update order atomically
        with transaction.atomic():
            items_map = {item.id: item for item in ListItem.objects.select_for_update().filter(custom_list=custom_list)}
            to_update = []
            for idx, item_id in enumerate(ordered_ids):
                item = items_map[item_id]
                if item.custom_order != idx:
                    item.custom_order = idx
                    to_update.append(item)
            if to_update:
                ListItem.objects.bulk_update(to_update, ['custom_order'])

        return Response({'ordered': True, 'custom_order': ordered_ids})
