from django.core.management.base import BaseCommand
from django.db import models
from tracking.choices import WatchEntryMediaType
from tracking.models import WatchEntry

class Command(BaseCommand):
    help = 'Clean duplicate WatchEntry rows'

    def handle(self, *args, **options):
        # Clean episode duplicates (same season + episode)
        episode_dups = (
            WatchEntry.objects
            .filter(media_type=WatchEntryMediaType.EPISODE)
            .values('user_id', 'tmdb_id', 'season_number', 'episode_number')
            .annotate(cnt=models.Count('id'))
            .filter(cnt__gt=1)
        )
        
        count = 0
        for d in episode_dups:
            entries = (
                WatchEntry.objects
                .filter(
                    user_id=d['user_id'],
                    media_type=WatchEntryMediaType.EPISODE,
                    tmdb_id=d['tmdb_id'],
                    season_number=d['season_number'],
                    episode_number=d['episode_number']
                )
                .order_by('-created_at')
            )
            skip = True
            for entry in entries:
                if skip:
                    skip = False
                    continue
                entry.delete()
                count += 1
        
        # Clean non-episode duplicates (show, movie)
        other_dups = (
            WatchEntry.objects
            .exclude(media_type=WatchEntryMediaType.EPISODE)
            .values('user_id', 'media_type', 'tmdb_id')
            .annotate(cnt=models.Count('id'))
            .filter(cnt__gt=1)
        )
        
        for d in other_dups:
            entries = (
                WatchEntry.objects
                .filter(user_id=d['user_id'], media_type=d['media_type'], tmdb_id=d['tmdb_id'])
                .exclude(media_type=WatchEntryMediaType.EPISODE)
                .order_by('-created_at')
            )
            skip = True
            for entry in entries:
                if skip:
                    skip = False
                    continue
                entry.delete()
                count += 1
        
        self.stdout.write(f'Deleted {count} duplicate entries')
