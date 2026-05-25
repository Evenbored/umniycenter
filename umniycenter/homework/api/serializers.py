from rest_framework import serializers

from accounts.api.serializers import UserListSerializer
from ..models import Homework, HomeWorkStudents


class HomeworkSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.__str__", read_only=True)
    course_name = serializers.CharField(source="group.course.name", read_only=True)

    class Meta:
        model = Homework
        fields = [
            "id",
            "task",
            "created",
            "finished",
            "group",
            "group_name",
            "course_name",
        ]


class HomeWorkStudentSerializer(serializers.ModelSerializer):
    homework_details = HomeworkSerializer(source="homework", read_only=True)
    student_details = UserListSerializer(source="student", read_only=True)

    class Meta:
        model = HomeWorkStudents
        fields = [
            "id",
            "student",
            "student_details",
            "homework",
            "homework_details",
        ]
