from rest_framework import serializers

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import re

from accounts.models import CustomUser
from accounts.serializers import UserListSerializer
from .models import StudentGroups


class StudentGroupSerializer(serializers.ModelSerializer):
    student_details = UserListSerializer(source="student", read_only=True)
    student_full_name = serializers.SerializerMethodField()
    student_phone = serializers.CharField(source="student.phone", read_only=True)
    student_email = serializers.EmailField(source="student.email", read_only=True)
    student_city = serializers.CharField(source="student.city", read_only=True)
    student_is_active = serializers.BooleanField(source="student.is_active", read_only=True)
    student_date_joined = serializers.DateTimeField(source="student.date_joined", read_only=True)
    group_number = serializers.CharField(source="group.number", read_only=True)
    group_name = serializers.CharField(source="group.__str__", read_only=True)
    course_name = serializers.CharField(source="group.course.name", read_only=True)
    teacher_name = serializers.CharField(source="group.teacher.__str__", read_only=True)

    def get_student_full_name(self, obj):
        return obj.student.get_full_name() or obj.student.username

    class Meta:
        model = StudentGroups
        fields = [
            "id",
            "group",
            "group_number",
            "group_name",
            "course_name",
            "teacher_name",
            "student",
            "student_details",
            "student_full_name",
            "student_phone",
            "student_email",
            "student_city",
            "student_is_active",
            "student_date_joined",
        ]


class StudentListSerializer(serializers.ModelSerializer):
    student = serializers.IntegerField(source="id", read_only=True)
    student_details = UserListSerializer(source="*", read_only=True)
    student_full_name = serializers.SerializerMethodField()
    student_phone = serializers.CharField(source="phone", read_only=True)
    student_email = serializers.EmailField(source="email", allow_null=True, read_only=True)
    student_city = serializers.CharField(source="city", read_only=True)
    student_country = serializers.CharField(source="country", read_only=True)
    student_is_active = serializers.BooleanField(source="is_active", read_only=True)
    student_date_joined = serializers.DateTimeField(source="date_joined", read_only=True)
    groups = serializers.SerializerMethodField()
    parents = serializers.SerializerMethodField()
    subscriptions = serializers.SerializerMethodField()
    source = serializers.SerializerMethodField()
    source_display = serializers.SerializerMethodField()

    def get_student_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_groups(self, obj):
        memberships = getattr(obj, "student_group_memberships", [])

        return [
            {
                "membership_id": membership.id,
                "group": membership.group_id,
                "group_number": membership.group.number,
                "group_name": str(membership.group),
                "course": membership.group.course_id,
                "course_name": membership.group.course.name,
                "teacher": membership.group.teacher_id,
                "teacher_name": str(membership.group.teacher),
            }
            for membership in memberships
        ]

    def get_parents(self, obj):
        try:
            student_profile = obj.student_profile
            parent_profiles = student_profile.parents.all()
            
            if not parent_profiles:
                return []
            
            return [
                {
                    "id": parent_profile.user.id,
                    "first_name": parent_profile.user.first_name,
                    "last_name": parent_profile.user.last_name,
                    "phone": parent_profile.user.phone,
                    "email": parent_profile.user.email or "",
                    "username": parent_profile.user.username,
                    "full_name": parent_profile.user.get_full_name() or parent_profile.user.username,
                }
                for parent_profile in parent_profiles
            ]
        except Exception:
            return []

    def get_subscriptions(self, obj):
        try:
            from subscriptions.models import Subscription
            from django.utils import timezone
            
            subscriptions = Subscription.objects.filter(
                student=obj,
                status='active'
            ).select_related('tariff', 'tariff__course').order_by('-created_at')
            
            return [
                {
                    "id": sub.id,
                    "tariff_name": sub.tariff.name,
                    "course_name": sub.tariff.course.name,
                    "lessons_total": sub.lessons_total,
                    "lessons_used": sub.lessons_used,
                    "lessons_remaining": sub.lessons_remaining,
                    "start_date": sub.start_date,
                    "end_date": sub.end_date,
                    "is_valid": sub.is_valid,
                    "status": sub.status,
                }
                for sub in subscriptions
            ]
        except Exception:
            return []

    def get_source(self, obj):
        try:
            return obj.student_profile.source or ""
        except Exception:
            return ""

    def get_source_display(self, obj):
        try:
            return obj.student_profile.get_source_display() if obj.student_profile.source else ""
        except Exception:
            return ""

    class Meta:
        model = CustomUser
        fields = [
            "student",
            "student_details",
            "student_full_name",
            "student_phone",
            "student_email",
            "student_city",
            "student_country",
            "student_is_active",
            "student_date_joined",
            "groups",
            "parents",
            "subscriptions",
            "source",
            "source_display",
        ]


class StudentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "first_name",
            "last_name",
            "username",
            "phone",
            "email",
            "city",
            "country",
            "sex",
            "is_active",
        ]

    def validate_username(self, value):
        value = (value or "").strip()

        if not value:
            raise serializers.ValidationError("Укажите логин ученика")

        if value.startswith("parent_"):
            raise serializers.ValidationError("Логин ученика не может начинаться с 'parent_'")

        # Если значение не изменилось, пропускаем проверку уникальности
        if self.instance and self.instance.username == value:
            return value

        queryset = CustomUser.objects.filter(username=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError("Этот логин уже занят")

        return value

    def validate_email(self, value):
        value = (value or "").strip() or None

        if not value:
            return None

        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError("Введите корректный email")

        # Если значение не изменилось, пропускаем проверку уникальности
        if self.instance and self.instance.email == value:
            return value

        queryset = CustomUser.objects.filter(email=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует")

        return value

    def validate_phone(self, value):
        value = (value or "").strip() or None

        # Телефон теперь необязателен
        if not value:
            return None

        if not re.fullmatch(r"\+7\d{10}", value):
            raise serializers.ValidationError("Телефон должен быть в формате +7XXXXXXXXXX")

        # Если значение не изменилось, пропускаем проверку уникальности
        if self.instance and self.instance.phone == value:
            return value

        queryset = CustomUser.objects.filter(phone=value)

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError("Пользователь с таким телефоном уже существует")

        return value


