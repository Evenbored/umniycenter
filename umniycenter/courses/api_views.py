from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from accounts.models import UserRole
from accounts.permissions import IsAdminOrTeacherRole, IsAdminRole
from .models import Courses
from .serializers import CourseSerializer


class CourseListAPIView(ListAPIView):
    serializer_class = CourseSerializer
    permission_classes = [IsAdminOrTeacherRole]
    queryset = Courses.objects.all().order_by("name")


@api_view(["POST"])
def create_course(request):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может создавать курсы"}, status=status.HTTP_403_FORBIDDEN)

    serializer = CourseSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    course = serializer.save()

    return Response({
        "message": "Курс создан",
        "course": CourseSerializer(course).data,
    }, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
def update_course(request, course_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может редактировать курсы"}, status=status.HTTP_403_FORBIDDEN)

    try:
        course = Courses.objects.get(id=course_id)
    except Courses.DoesNotExist:
        return Response({"error": "Курс не найден"}, status=status.HTTP_404_NOT_FOUND)

    serializer = CourseSerializer(course, data=request.data, partial=True)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()

    return Response({
        "message": "Курс обновлен",
        "course": CourseSerializer(course).data,
    })


@api_view(["DELETE"])
def delete_course(request, course_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может удалять курсы"}, status=status.HTTP_403_FORBIDDEN)

    try:
        course = Courses.objects.get(id=course_id)
    except Courses.DoesNotExist:
        return Response({"error": "Курс не найден"}, status=status.HTTP_404_NOT_FOUND)

    course.delete()

    return Response({"message": "Курс удален"}, status=status.HTTP_204_NO_CONTENT)
