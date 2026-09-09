from django.contrib import admin

from .models import Follow


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ['follower', 'following', 'created_at']
    list_filter = ['created_at']
    search_fields = [
        'follower__username', 'follower__email', 'following__username', 'following__email',
    ]
    ordering = ['-created_at']
    list_select_related = ['follower', 'following']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Relationship', {'fields': ('follower', 'following')}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
