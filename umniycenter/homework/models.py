from django.db import models

from accounts.models import CustomUser
from groups.models import SchoolGroups

class Homework(models.Model):
    task = models.CharField(verbose_name="Задание")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Дата задачи")
    finished = models.DateTimeField(auto_now_add=True, verbose_name="Дата сдачи")
    group = models.ForeignKey(SchoolGroups,
                              on_delete=models.CASCADE,
                              verbose_name='Группа')
    class Meta:
        verbose_name = ("Домашнее задание")
        verbose_name_plural = ("Домашнее задание")

    def __str__(self):
        return f'Задание на {self.finished.date}'

class HomeWorkStudents(models.Model):
    student = models.ForeignKey(CustomUser,
                                on_delete=models.CASCADE, verbose_name="Ученик")
    homework = models.ForeignKey(Homework,
                                 on_delete=models.CASCADE, verbose_name="Домашнее задание")
    
    class Meta:
        verbose_name = ("Домашнее задание для учеников")
        verbose_name_plural = ("Домашнее задание для учеников")
    
    def __str__(self):
        return f'Задание {self.homework} для {self.student}'
