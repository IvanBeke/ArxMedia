from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'account_visibility', 'created_at']
    base_fieldsets = UserAdmin.fieldsets or ()
    fieldsets = (*base_fieldsets, ('Profile', {'fields': ('bio', 'avatar', 'location', 'website', 'account_visibility')}))
