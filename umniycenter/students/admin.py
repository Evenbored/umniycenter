from django.contrib import admin

from accounts.models import CustomUser, UserRole

from .models import StudentGroups

# Register your models here.
@admin.register(StudentGroups)
class StudentGroupsAdmin(admin.ModelAdmin):
    list_display = ['group', 'student']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "student":
            kwargs["queryset"] = CustomUser.objects.filter(role=UserRole.STUDENT)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)