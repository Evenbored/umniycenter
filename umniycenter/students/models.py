from django.db import models
from accounts.models import CustomUser
from django.core.exceptions import ValidationError
from groups.models import SchoolGroups


class StudentGroups(models.Model):
    group = models.ForeignKey(SchoolGroups,
                              on_delete=models.CASCADE, verbose_name="Группа")
    student = models.ForeignKey(CustomUser,
                                on_delete=models.CASCADE, verbose_name="Ученик")
    
    class Meta:
        verbose_name = ("Ученика в группу")
        verbose_name_plural = ("Ученики в группах")
        constraints = [
            models.UniqueConstraint(
                fields=["group", "student"],
                name="unique_student_in_group",
            ),
        ]

    def clean(self):
        duplicate_queryset = StudentGroups.objects.filter(group=self.group, student=self.student)

        if self.pk:
            duplicate_queryset = duplicate_queryset.exclude(pk=self.pk)

        if duplicate_queryset.exists():
            raise ValidationError("Этот ученик уже есть в этой группе")

    def __str__(self):
        return f'{self.group} | {self.student}'
