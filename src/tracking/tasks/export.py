import json

from celery import shared_task
from django.core.files.base import ContentFile

from ..choices import DataTransferStatus
from ..models import CustomList, DataTransferJob, Rating, UserMediaStatus, WatchEntry


@shared_task(name='tracking.export_user_data')
def export_user_data(job_id: int) -> dict[str, str]:
    job = DataTransferJob.objects.get(id=job_id)
    job.status = DataTransferStatus.PROCESSING
    job.save(update_fields=['status', 'updated_at'])

    try:
        user = job.user
        watch_history = list(WatchEntry.objects.filter(user=user).values())
        watchlist = [
            {
                'media_type': item.media_type,
                'tmdb_id': item.tmdb_id,
                'plan_to_watch_at': item.plan_to_watch_at.isoformat() if item.plan_to_watch_at else None,
            }
            for item in UserMediaStatus.objects.for_user(user).planning()
        ]
        ratings = list(Rating.objects.filter(user=user).values())
        lists = []
        for custom_list in CustomList.objects.filter(user=user).prefetch_related('items'):
            lists.append({
                'name': custom_list.name,
                'description': custom_list.description,
                'privacy': custom_list.privacy,
                'items': [
                    {
                        'media_type': item.media_type,
                        'tmdb_id': item.tmdb_id,
                        'added_at': item.added_at.isoformat(),
                        'custom_order': item.custom_order,
                    }
                    for item in custom_list.items.all()
                ],
            })
        payload = {
            'watch_history': watch_history,
            'watchlist': watchlist,
            'ratings': ratings,
            'lists': lists,
        }
        raw = json.dumps(payload, default=str, indent=2)
        filename = f'user-{user.id}-export-{job.id}.json'
        job.output_file.save(filename, ContentFile(raw.encode('utf-8')), save=False)
        job.status = DataTransferStatus.DONE
        job.total_items = len(watch_history) + len(watchlist) + len(ratings) + sum(
            1 + len(custom_list['items']) for custom_list in lists
        )
        job.processed_items = job.total_items
        job.error_message = ''
        job.save()
        return {'status': DataTransferStatus.DONE}
    except Exception as exc:
        job.status = DataTransferStatus.FAILED
        job.error_message = str(exc)
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        return {'status': DataTransferStatus.FAILED}
