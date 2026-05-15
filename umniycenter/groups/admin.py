from django.contrib import admin

from accounts.models import CustomUser, UserRole

from .models import SchoolGroups

# Register your models here.
@admin.register(SchoolGroups)
class GroupsAdmin(admin.ModelAdmin):
    list_display = ['number', 'course', 'teacher']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = CustomUser.objects.filter(role=UserRole.TEACHER)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)