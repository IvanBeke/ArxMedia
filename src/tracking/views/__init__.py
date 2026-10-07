"""Tracking API views, grouped by feature."""

from .episodes import (
    mark_episode_watched,
    mark_season_watched,
    mark_show_watched,
    unmark_episode_watched,
    unmark_season_watched,
    unmark_show_watched,
    watched_episodes,
)
from .history import (
    RatingListCreateView,
    ReviewListCreateView,
    WatchEntryDetailView,
    WatchEntryListCreateView,
    user_stats,
)
from .library import (
    my_movies_list,
    my_shows_list,
    up_next,
    upcoming,
)
from .lists import (
    CustomListDetailView,
    CustomListListCreateView,
    ListItemDetailView,
    ListItemListCreateView,
    ListItemReorderView,
)
from .recommendations import recommendations
from .transfer import (
    DataExportView,
    DataImportView,
    DataJobCancelView,
    DataJobConfirmView,
    DataJobFileView,
    DataJobListView,
    DataJobStatusView,
)
from .watchlist import (
    WatchlistDetailView,
    WatchlistListCreateView,
    drop_media,
)

__all__ = [
    'CustomListDetailView',
    'CustomListListCreateView',
    'DataExportView',
    'DataImportView',
    'DataJobCancelView',
    'DataJobConfirmView',
    'DataJobFileView',
    'DataJobListView',
    'DataJobStatusView',
    'ListItemDetailView',
    'ListItemListCreateView',
    'ListItemReorderView',
    'RatingListCreateView',
    'ReviewListCreateView',
    'WatchEntryDetailView',
    'WatchEntryListCreateView',
    'WatchlistDetailView',
    'WatchlistListCreateView',
    'drop_media',
    'mark_episode_watched',
    'mark_season_watched',
    'mark_show_watched',
    'my_movies_list',
    'my_shows_list',
    'recommendations',
    'unmark_episode_watched',
    'unmark_season_watched',
    'unmark_show_watched',
    'up_next',
    'upcoming',
    'user_stats',
    'watched_episodes',
]
