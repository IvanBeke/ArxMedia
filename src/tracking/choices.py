from django.db import models


class WatchEntryMediaType(models.TextChoices):
    MOVIE = 'movie', 'Movie'
    EPISODE = 'episode', 'Episode'


class TvShowStatus(models.TextChoices):
    PLAN_TO_WATCH = 'plan_to_watch', 'Plan to Watch'
    WATCHING = 'watching', 'Watching'
    WATCHED = 'watched', 'Watched'
    DROPPED = 'dropped', 'Dropped'


class SeasonStatus(models.TextChoices):
    WATCHING = 'watching', 'Watching'
    WATCHED = 'watched', 'Watched'


class MediaType(models.TextChoices):
    MOVIE = 'movie', 'Movie'
    TV = 'tv', 'TV Show'


class ListPrivacy(models.TextChoices):
    PUBLIC = 'public', 'Public'
    PRIVATE = 'private', 'Private'


class DataTransferSource(models.TextChoices):
    ARXMEDIA = 'arxmedia', 'ArxMedia'
    TRAKT = 'trakt', 'Trakt'
    YAMTRACK = 'yamtrack', 'Yamtrack'


class DataTransferJobType(models.TextChoices):
    IMPORT = 'import', 'Import'
    EXPORT = 'export', 'Export'


class DataTransferFormat(models.TextChoices):
    JSON = 'json', 'JSON'
    CSV = 'csv', 'CSV'
    ZIP = 'zip', 'ZIP'


class DataTransferStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    AWAITING_CONFIRMATION = 'awaiting_confirmation', 'Awaiting confirmation'
    DONE = 'done', 'Done'
    FAILED = 'failed', 'Failed'


class DataImportMode(models.TextChoices):
    NEW_ITEMS = 'new_items', 'New Items'
    UPDATE_EXISTING = 'update_existing', 'Update Existing'
    MIRROR_IMPORTED_SET = 'mirror_imported_set', 'Mirror Imported Set'
