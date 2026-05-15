from django.contrib import admin

from accounts.models import CustomUser, UserRole

from .models import Schedule

# Register your models here.
@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['group', 'classdateStart','classdateEnd', 'teacher']
    list_editable = ['classdateStart', 'classdateEnd', 'teacher']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = CustomUser.objects.filter(role=UserRole.TEACHER)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)