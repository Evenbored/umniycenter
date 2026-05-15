from django.shortcuts import render

from accounts.views import teacher_required
from .forms import HomeWorkAddForm

# Create your views here.
@teacher_required
def homework_view(request):
    return render(request, "homework/homeworklist.html")

@teacher_required
def homework_create(request):
    form = HomeWorkAddForm
    return render(request, "homework/homework_create.html", {'form': form})

