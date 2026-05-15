
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.db.models import Count
from accounts.views import teacher_required
from accounts.models import UserRole
from django.core.cache import cache
from .models import SchoolGroups


@teacher_required
def grades_view(request):
    grades = SchoolGroups.objects.filter(
    teacher=request.user
    ).annotate(
    students_count=Count("studentgroups"))
    return render(request, "groups/grade.html", {"grades": grades})

@teacher_required
def groups_count(request):
    if request.user.role != UserRole.TEACHER:
        return HttpResponseForbidden()
    key = f"user:{request.user.id}:groups_count"

    count = cache.get(key)

    if count is None:
        count = SchoolGroups.objects.filter(teacher=request.user).count()
        cache.set(key, count, 60)
    
    return JsonResponse({"count": count})