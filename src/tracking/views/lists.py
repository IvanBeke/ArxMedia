import logging

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.authentication import authenticated_user
from accounts.privacy import can_view_account_content, get_viewer_relationship

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
    _apply_media_search_filters,
    _apply_media_type_filter,
    _apply_missing_rating_filter,
    _apply_secondary_title_ordering,
    _apply_status_filter,
    _compute_mixed_runtime_and_counts,
    _ensure_local_metadata,
    _parse_bool_param,
    _parse_multi_param,
    _validated_sort,
)

logger = logging.getLogger(__name__)


def _can_view_public_lists(viewer, owner) -> bool:
    relationship = get_viewer_relationship(viewer, owner)
    return can_view_account_content(owner.account_visibility, relationship)

def _accessible_list(user, list_id):
    """The requested list, raising PermissionDenied when missing or not viewable."""
    try:
        custom_list = CustomList.objects.get(id=list_id)
    except CustomList.DoesNotExist:
        raise PermissionDenied('List not found.') from None
    if not _can_access_list(user, custom_list):
        raise PermissionDenied('You do not have permission to access this list.')
    return custom_list


def _writable_list(user, list_id, denied_message: str):
    """Like _accessible_list, but additionally requires owner/collaborator rights."""
    custom_list = _accessible_list(user, list_id)
    is_owner = custom_list.user_id == user.id
    is_collaborator = ListCollaborator.objects.filter(custom_list=custom_list, user=user).exists()
    if not (is_owner or is_collaborator):
        raise PermissionDenied(denied_message)
    return custom_list


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


def _with_list_summary(queryset):
    """Load everything CustomListSerializer reads, so listing lists costs a fixed number of queries."""
    return (
        queryset.select_related('user')
        .annotate(item_total=Count('items'))
        .prefetch_related('collaboratorships__user')
    )


def _parse_membership_params(request):
    """Return (media_type, tmdb_id) when the caller asks which lists contain an item.

    Invalid or partial params return None so plain list responses stay unchanged.
    """
    media_type = (request.query_params.get('media_type') or '').strip().lower()
    if media_type not in (MediaType.MOVIE, MediaType.TV):
        return None
    try:
        tmdb_id = int(str(request.query_params.get('tmdb_id') or '').strip())
    except (TypeError, ValueError):
        return None
    return media_type, tmdb_id


class CustomListListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return _with_list_summary(CustomList.objects.all())

        visible_public_lists = Q(privacy=ListPrivacy.PUBLIC) & (
            Q(user__account_visibility='public') |
            Q(
                user__account_visibility='friends_only',
                user__followers__follower=self.request.user,
                user__following__following=self.request.user,
            )
        )

        visible_ids = CustomList.objects.filter(
            Q(user=self.request.user) |
            Q(collaboratorships__user=self.request.user) |
            visible_public_lists
        ).values('id')
        # Filter by id so the item count is not multiplied by the visibility joins.
        return _with_list_summary(CustomList.objects.filter(id__in=visible_ids))

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_serializer_context(self):
        context = dict(super().get_serializer_context())
        parsed = _parse_membership_params(self.request)
        if parsed is None:
            return context
        media_type, tmdb_id = parsed
        # Single query for all visible lists; lazily nests the list queryset as a subquery.
        membership = dict(
            ListItem.objects.filter(
                custom_list__in=self.get_queryset().values('id'),
                media_type=media_type,
                tmdb_id=tmdb_id,
            ).values_list('custom_list_id', 'id')
        )
        context['membership_map'] = membership
        return context


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


_LIST_ITEM_VALID_SORTS = {
    'added_at', 'custom_order', 'title', 'release_date',
    'provider_rating', 'user_rating', 'runtime', 'total_episodes', 'vote_count',
    'watched_date', 'started_date', 'last_watched', 'progress_percent', 'episodes_left', 'time_left', 'next_episode_date'
}


def _list_item_status_and_flag_filters(queryset, request):
    selected_statuses = _parse_multi_param(request.query_params, 'status')
    if selected_statuses:
        queryset = _apply_status_filter(queryset, request.user, selected_statuses)
    if _parse_bool_param(request.query_params.get('missing_rating')) is True:
        queryset = _apply_missing_rating_filter(queryset, request.user)
    if _parse_bool_param(request.query_params.get('in_watchlist')) is True:
        queryset = _apply_in_watchlist_filter(queryset, request.user)
    return queryset


class ListItemListCreateView(generics.ListCreateAPIView):
    serializer_class = ListItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        custom_list = _accessible_list(self.request.user, self.kwargs.get('list_id'))
        queryset = ListItem.objects.filter(custom_list=custom_list).select_related('custom_list')

        query_params = self.request.query_params
        queryset = _apply_media_type_filter(queryset, query_params)
        # Search by title
        queryset = _apply_media_search_filters(queryset, query_params)
        queryset = _list_item_status_and_flag_filters(queryset, self.request)

        sort_key, direction = _validated_sort(
            query_params.get('sort'),
            query_params.get('direction'),
            default_sort='custom_order',
            valid_sorts=_LIST_ITEM_VALID_SORTS,
        )

        return _apply_secondary_title_ordering(queryset, sort_key, direction, user=self.request.user)

    def perform_create(self, serializer):
        user = authenticated_user(self.request)
        custom_list = _writable_list(
            user, self.kwargs.get('list_id'),
            'You can only add items to your lists or lists where you collaborate.',
        )
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
                raise ValidationError({'detail': 'Item is already in this list.'}) from None

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

        context = dict(self.get_serializer_context())
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


def _validated_reorder_ids(request, custom_list) -> list[int]:
    ordered_ids = request.data.get('custom_order')
    if not isinstance(ordered_ids, list):
        raise ValidationError({'custom_order': 'custom_order must be a list of item ids.'})

    try:
        ordered_ids = [int(i) for i in ordered_ids]
    except (TypeError, ValueError) as exc:
        raise ValidationError({'custom_order': 'custom_order must contain integers.'}) from exc

    if len(ordered_ids) != len(set(ordered_ids)):
        raise ValidationError({'custom_order': 'custom_order must not contain duplicates.'})

    existing_ids = set(ListItem.objects.filter(custom_list=custom_list).values_list('id', flat=True))
    if set(ordered_ids) != existing_ids:
        raise ValidationError({'custom_order': 'custom_order must contain all item ids for this list exactly once.'})
    return ordered_ids


def _bulk_reorder(custom_list, ordered_ids: list[int]) -> None:
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


class ListItemReorderView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        custom_list = _writable_list(
            request.user, self.kwargs.get('list_id'),
            'You can only reorder items in your lists or lists where you collaborate.',
        )
        ordered_ids = _validated_reorder_ids(request, custom_list)
        _bulk_reorder(custom_list, ordered_ids)

        return Response({'ordered': True, 'custom_order': ordered_ids})
