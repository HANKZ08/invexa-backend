from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import EmailVerification, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "role", "is_active", "email_verified_at")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = (*BaseUserAdmin.fieldsets, ("Invexa", {"fields": ("role",)}))
    add_fieldsets = (*BaseUserAdmin.add_fieldsets, ("Invexa", {"fields": ("email", "role")}))


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "attempts", "used_at")
    list_select_related = ("user",)
    readonly_fields = ("user", "code_hash", "expires_at", "attempts", "used_at", "created_at")

    def has_add_permission(self, request):
        return False
