from django.contrib import admin

from .models import (
    CustomList,
    DataTransferJob,
    ListCollaborator,
    ListItem,
    Rating,
    Review,
    UserMediaStatus,
    WatchEntry,
)


@admin.register(WatchEntry)
class WatchEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'media_type', 'tmdb_id', 'watched_at']
    list_filter = ['media_type', 'watched_at', 'created_at']
    search_fields = ['user__username', 'user__email', 'tmdb_id']
    ordering = ['-watched_at', '-created_at']
    list_select_related = ['user']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Entry', {'fields': ('user', 'media_type', 'tmdb_id')}),
        ('Watch information', {'fields': ('watched_at', 'season_number', 'episode_number')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['user', 'media_type', 'tmdb_id', 'score', 'updated_at']
    list_filter = ['media_type', 'score', 'created_at', 'updated_at']
    search_fields = ['user__username', 'user__email', 'tmdb_id']
    ordering = ['-updated_at']
    list_select_related = ['user']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Rating', {'fields': ('user', 'media_type', 'tmdb_id', 'score')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'media_type', 'tmdb_id', 'contains_spoilers', 'created_at']
    list_filter = ['media_type', 'contains_spoilers', 'created_at', 'updated_at']
    search_fields = ['user__username', 'user__email', 'tmdb_id', 'content']
    ordering = ['-updated_at']
    list_select_related = ['user']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Review', {'fields': ('user', 'media_type', 'tmdb_id', 'content', 'contains_spoilers')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(UserMediaStatus)
class UserMediaStatusAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'media_type',
        'tmdb_id',
        'status',
        'watched_episodes',
        'total_episodes',
        'progress_percent',
        'updated_at',
    ]
    list_filter = ['media_type', 'status']
    search_fields = ['user__username', 'user__email', 'tmdb_id']
    ordering = ['-updated_at']
    list_select_related = ['user']
    fieldsets = (
        ('Media', {'fields': ('user', 'media_type', 'tmdb_id', 'status')}),
        ('Progress', {
            'fields': ('watched_episodes', 'total_episodes', 'progress_percent', 'metadata'),
        }),
        ('Status dates', {
            'fields': (
                'started_at', 'completed_at', 'dropped_at', 'plan_to_watch_at',
                'last_watched_at', 'status_changed_at',
            ),
        }),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )
    readonly_fields = [
        'started_at',
        'completed_at',
        'dropped_at',
        'last_watched_at',
        'status_changed_at',
        'created_at',
        'updated_at',
    ]


@admin.register(DataTransferJob)
class DataTransferJobAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user',
        'job_type',
        'source',
        'data_format',
        'status',
        'import_mode',
        'processed_items',
        'total_items',
        'updated_at',
    ]
    list_filter = ['job_type', 'source', 'data_format', 'status', 'import_mode']
    search_fields = ['id', 'user__username', 'user__email', 'error_message']
    ordering = ['-created_at']
    list_select_related = ['user']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Job', {'fields': ('user', 'job_type', 'source', 'data_format', 'status')}),
        ('Import options', {'fields': ('import_mode', 'overwrite_existing')}),
        ('Files and progress', {
            'fields': ('input_file', 'output_file', 'total_items', 'processed_items', 'error_message'),
        }),
        ('Metadata and timestamps', {'fields': ('metadata', 'created_at', 'updated_at')}),
    )


@admin.register(CustomList)
class CustomListAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'privacy', 'item_count', 'collaborator_count', 'updated_at']
    list_filter = ['privacy', 'created_at', 'updated_at']
    search_fields = ['name', 'description', 'user__username', 'user__email']
    ordering = ['-updated_at']
    list_select_related = ['user']
    readonly_fields = ['created_at', 'updated_at', 'item_count', 'collaborator_count']
    fieldsets = (
        ('List', {'fields': ('user', 'name', 'description', 'privacy')}),
        ('Statistics', {'fields': ('item_count', 'collaborator_count')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Items')
    def item_count(self, obj):
        return obj.items.count()

    @admin.display(description='Collaborators')
    def collaborator_count(self, obj):
        return obj.collaboratorships.count()


@admin.register(ListItem)
class ListItemAdmin(admin.ModelAdmin):
    list_display = ['custom_list', 'media_type', 'tmdb_id', 'custom_order', 'added_at']
    list_filter = ['media_type', 'added_at']
    search_fields = ['custom_list__name', 'custom_list__user__username', 'tmdb_id']
    ordering = ['custom_list__name', 'custom_order', 'added_at']
    list_select_related = ['custom_list', 'custom_list__user']
    readonly_fields = ['added_at']
    fieldsets = (
        ('Item', {'fields': ('custom_list', 'media_type', 'tmdb_id', 'custom_order')}),
        ('Timestamps', {'fields': ('added_at',)}),
    )


@admin.register(ListCollaborator)
class ListCollaboratorAdmin(admin.ModelAdmin):
    list_display = ['custom_list', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['custom_list__name', 'custom_list__user__username', 'user__username', 'user__email']
    ordering = ['custom_list']
    list_select_related = ['custom_list', 'custom_list__user', 'user']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Collaboration', {'fields': ('custom_list', 'user')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
