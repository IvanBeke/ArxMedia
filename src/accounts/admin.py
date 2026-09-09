from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'username', 'email', 'first_name', 'last_name', 'account_visibility',
        'preferred_region', 'is_staff', 'is_active', 'created_at',
    ]
    list_filter = ['account_visibility', 'preferred_region', 'is_staff', 'is_active', 'is_superuser', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'location', 'website']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    base_fieldsets = UserAdmin.fieldsets or ()
    fieldsets = (
        *base_fieldsets,
        ('Profile', {
            'fields': ('bio', 'avatar', 'location', 'website', 'preferred_region', 'account_visibility'),
        }),
        ('Account metadata', {'fields': ('created_at',)}),
    )
