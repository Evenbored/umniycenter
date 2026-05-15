from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.core.cache import cache
from groups.models import SchoolGroups
from accounts.views import teacher_required
from accounts.models import UserRole
from .models import StudentGroups
from .forms import CustomUserSearchForm

# Create your views here.
@teacher_required
def students_view(request):
    queryset = SchoolGroups.objects.filter(teacher=request.user)
    form = CustomUserSearchForm(queryset=queryset)
    if request.method == "POST":
        form = CustomUserSearchForm(request.POST, queryset=queryset)
        if form.is_valid():
            course = form.cleaned_data["course"]
            teacerStudents = StudentGroups.objects.filter(group=course)
        return render(request, 'students/students.html', {'user': request.user, 'form': form, 'teacherStudents': teacerStudents})
    return render(request, 'students/students.html', {'user': request.user, 'form': form})

@teacher_required
def students_count(request):
    if request.user.role != UserRole.TEACHER:
        return HttpResponseForbidden()
    key = f"user:{request.user.id}:students_count"

    count = cache.get(key)

    if count is None:
        count = (
            StudentGroups.objects
            .filter(group__teacher=request.user)
            .values("student_id")
            .distinct()
            .count())
        cache.set(key, count, 60)
    
    return JsonResponse({"count": count})
