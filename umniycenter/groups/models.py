from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import CustomUser, UserRole
from courses.models import Courses


class SchoolGroups(models.Model):
    number = models.CharField(max_length=150, unique=True, verbose_name="Номер")
    course = models.ForeignKey(Courses,
                               on_delete=models.CASCADE, verbose_name="Курс")
    teacher = models.ForeignKey(CustomUser,
                                 on_delete=models.CASCADE, verbose_name="Руководитель")
    is_active = models.BooleanField(default=True, verbose_name="Активная")
    
    class Meta:
        verbose_name = ("Группу")
        verbose_name_plural = ("Группы")

    def clean(self):
        if self.teacher and self.teacher.role != UserRole.TEACHER:
            raise ValidationError("Руководителем группы может быть только преподаватель")
    
    def __str__(self):
        return f'{self.course} - {self.number}'
