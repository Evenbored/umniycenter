from django.db import models

# Create your models here.
class Courses(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Наименование")
    
    class Meta:
        verbose_name = ("Курс")
        verbose_name_plural = ("Курсы")


    def __str__(self):
        return self.name
