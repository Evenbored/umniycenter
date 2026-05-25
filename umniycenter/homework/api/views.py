from rest_framework.generics import ListAPIView

from accounts.models import UserRole
from accounts.permissions import IsAdminTeacherOrStudentRole
from ..models import Homework, HomeWorkStudents
from .serializers import HomeworkSerializer, HomeWorkStudentSerializer


class HomeworkListAPIView(ListAPIView):
    serializer_class = HomeworkSerializer
    permission_classes = [IsAdminTeacherOrStudentRole]

    def get_queryset(self):
        user = self.request.user
        queryset = Homework.objects.select_related("group", "group__course", "group__teacher")

        if user.role == UserRole.TEACHER:
            return queryset.filter(group__teacher=user)

        if user.role == UserRole.ADMIN:
            return queryset.all()

        if user.role == UserRole.STUDENT:
            return queryset.filter(homeworkstudents__student=user).distinct()

        return queryset.none()


class MyHomeworkAPIView(ListAPIView):
    serializer_class = HomeWorkStudentSerializer
    permission_classes = [IsAdminTeacherOrStudentRole]

    def get_queryset(self):
        user = self.request.user
        queryset = HomeWorkStudents.objects.select_related(
            "student",
            "homework",
            "homework__group",
            "homework__group__course",
        )

        if user.role == UserRole.STUDENT:
            return queryset.filter(student=user)

        if user.role == UserRole.TEACHER:
            return queryset.filter(homework__group__teacher=user)

        if user.role == UserRole.ADMIN:
            return queryset.all()

        return queryset.none()
