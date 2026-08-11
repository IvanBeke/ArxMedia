from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'is_private', 'created_at']
    base_fieldsets = UserAdmin.fieldsets or ()
    fieldsets = (*base_fieldsets, ('Profile', {'fields': ('bio', 'avatar', 'location', 'website', 'is_private')}))
