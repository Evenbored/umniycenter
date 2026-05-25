from rest_framework import serializers
from ..models import GroupScheduleTemplate, Schedule


class ScheduleSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="title", read_only=True)
    course_name = serializers.CharField(read_only=True)
    teacher_name = serializers.CharField(source="teacher.__str__", read_only=True)
    student_name = serializers.SerializerMethodField()
    lesson_type_display = serializers.CharField(source="get_lesson_type_display", read_only=True)
    actual_status = serializers.CharField(read_only=True)
    is_past = serializers.BooleanField(read_only=True)

    def get_student_name(self, obj):
        if obj.student:
            return obj.student.get_full_name() or obj.student.username
        return ""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.group and not data.get("course_name"):
            data["course_name"] = instance.group.course.name if instance.group.course else ""
        if instance.course and not data.get("course_name"):
            data["course_name"] = instance.course.name
        return data

    class Meta:
        model = Schedule
        fields = [
            "id",
            "group",
            "group_name",
            "student",
            "student_name",
            "students",
            "course",
            "course_name",
            "teacher",
            "teacher_name",
            "lesson_type",
            "lesson_type_display",
            "is_single",
            "classdateStart",
            "classdateEnd",
            "status",
            "actual_status",
            "is_past",
            "original_classdateStart",
            "original_classdateEnd",
            "cancel_reason",
            "reschedule_reason",
        ]

    def validate(self, attrs):
        lesson_type = attrs.get("lesson_type", getattr(self.instance, "lesson_type", Schedule.LESSON_TYPE_REGULAR))
        group = attrs.get("group", getattr(self.instance, "group", None))
        student = attrs.get("student", getattr(self.instance, "student", None))
        course = attrs.get("course", getattr(self.instance, "course", None))

        if group:
            attrs["course"] = group.course
        else:
            if not student:
                raise serializers.ValidationError({"student": "Выберите ученика"})
            if not course:
                raise serializers.ValidationError({"course": "Выберите курс"})

        return attrs


class GroupScheduleTemplateSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.__str__", read_only=True)
    course_name = serializers.CharField(source="group.course.name", read_only=True)
    teacher = serializers.IntegerField(source="group.teacher_id", read_only=True)
    teacher_name = serializers.CharField(source="group.teacher.__str__", read_only=True)
    weekday_display = serializers.CharField(source="get_weekday_display", read_only=True)
    lessons_count_display = serializers.CharField(source="get_lessons_count_display", read_only=True)

    class Meta:
        model = GroupScheduleTemplate
        fields = [
            "id",
            "group",
            "group_name",
            "course_name",
            "teacher",
            "teacher_name",
            "weekday",
            "weekday_display",
            "start_time",
            "lessons_count",
            "lessons_count_display",
            "is_active",
        ]
