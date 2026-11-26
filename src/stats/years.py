from django.db.models import Min
from django.db.models.functions import ExtractYear
from django.utils import timezone

from tracking.models import WatchEntry


def years_stats(user_id):
    """The range of years the stats can be browsed: from the first year with a dated watch entry to the current one.

    `earliest_year` is null when there is no dated entry; found in a single query.
    """
    row = WatchEntry.objects.for_user(user_id).aggregate(earliest_year=Min(ExtractYear('watched_at')))
    return {'current_year': timezone.localdate().year, 'earliest_year': row['earliest_year']}
