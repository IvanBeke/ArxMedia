import json

from celery import shared_task
from django.core.files.base import ContentFile

from ..choices import DataTransferStatus
from ..models import DataTransferJob, Rating, Review, WatchEntry, Watchlist


@shared_task(name='tracking.export_user_data')
def export_user_data(job_id: int) -> dict[str, str]:
    job = DataTransferJob.objects.get(id=job_id)
    job.status = DataTransferStatus.PROCESSING
    job.save(update_fields=['status', 'updated_at'])

    try:
        user = job.user
        watch_history = list(WatchEntry.objects.filter(user=user).values())
        watchlist = list(Watchlist.objects.filter(user=user).values())
        ratings = list(Rating.objects.filter(user=user).values())
        reviews = list(Review.objects.filter(user=user).values())
        payload = {
            'watch_history': watch_history,
            'watchlist': watchlist,
            'ratings': ratings,
            'reviews': reviews,
        }
        raw = json.dumps(payload, default=str, indent=2)
        filename = f'user-{user.id}-export-{job.id}.json'
        job.output_file.save(filename, ContentFile(raw.encode('utf-8')), save=False)
        job.status = DataTransferStatus.DONE
        job.total_items = len(watch_history) + len(watchlist) + len(ratings) + len(reviews)
        job.processed_items = job.total_items
        job.error_message = ''
        job.save()
        return {'status': DataTransferStatus.DONE}
    except Exception as exc:
        job.status = DataTransferStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return {'status': DataTransferStatus.FAILED}
