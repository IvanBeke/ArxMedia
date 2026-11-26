from django.db.models import Avg, Count, Q
from django.db.models.functions import Round

from tracking.models import Rating

RATING_SCORES = range(1, 11)


def rating_stats(user_id):
    """Ratings count, average and the number of ratings per score (1-10), in a single query."""
    row = Rating.objects.filter(user_id=user_id).aggregate(
        ratings_count=Count('id'),
        average_rating=Round(Avg('score'), 1),
        **{f'score_{score}': Count('id', filter=Q(score=score)) for score in RATING_SCORES},
    )
    return {
        'ratings_count': row['ratings_count'],
        'average_rating': row['average_rating'],
        'rating_distribution': [row[f'score_{score}'] for score in RATING_SCORES],
    }
