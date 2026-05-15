from rest_framework import serializers
from accounts.models import UserRole
from .models import SchoolGroups


class SchoolGroupSerializer(serializers.ModelSerializer):
    course_name = serializers.CharField(source="course.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.__str__", read_only=True)
    students_count = serializers.IntegerField(read_only=True)

    def validate_teacher(self, value):
        if value.role != UserRole.TEACHER:
            raise serializers.ValidationError("Руководителем группы может быть только преподаватель")

        return value

    class Meta:
        model = SchoolGroups
        fields = [
            "id",
            "number",
            "course",
            "course_name",
            "teacher",
            "teacher_name",
            "students_count",
            "is_active",
        ]
