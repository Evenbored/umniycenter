from django.contrib import admin

from accounts.models import CustomUser, UserRole

from .models import Lesson, LessonParticipant, Schedule

# Register your models here.
@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['group', 'classdateStart','classdateEnd', 'teacher']
    list_editable = ['classdateStart', 'classdateEnd', 'teacher']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "teacher":
            kwargs["queryset"] = CustomUser.objects.filter(role=UserRole.TEACHER)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class LessonParticipantInline(admin.TabularInline):
    model = LessonParticipant
    extra = 0


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['id', 'starts_at', 'ends_at', 'lesson_type', 'status', 'group', 'course', 'teacher']
    list_filter = ['status', 'lesson_type', 'starts_at', 'course']
    search_fields = ['group__number', 'course__name', 'teacher__first_name', 'teacher__last_name']
    inlines = [LessonParticipantInline]


@admin.register(LessonParticipant)
class LessonParticipantAdmin(admin.ModelAdmin):
    list_display = ['id', 'lesson', 'student', 'attendance_status', 'lessons_to_charge', 'lessons_charged', 'subscription']
    list_filter = ['attendance_status', 'lessons_charged', 'created_at']
    search_fields = ['student__first_name', 'student__last_name', 'lesson__course__name']
