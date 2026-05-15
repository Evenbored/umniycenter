import re

from rest_framework import serializers
from .models import CustomUser
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

class CurrentUserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    sex_display = serializers.CharField(source="get_sex_display", read_only=True)

    def get_display_name(self, obj):
        return obj.get_full_name().strip() or obj.username

    def get_initials(self, obj):
        parts = [obj.first_name, obj.last_name]
        initials = "".join(part[:1] for part in parts if part).upper()
        return initials or obj.username[:2].upper()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "display_name",
            "initials",
            "username",
            "email",
            "first_name",
            "last_name",
            "city",
            "country",
            "phone",
            "sex",
            "sex_display",
            "role",
            "role_display",
            "is_active",
        ]

class UserListSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    sex_display = serializers.CharField(source="get_sex_display", read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
            "sex",
            "sex_display",
            "role",
            "role_display",
            "is_active",
        ]

class ParentListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_children(self, obj):
        try:
            student_profiles = obj.parent_profile.students.select_related("user").all()
        except Exception:
            return []

        return [
            {
                "id": profile.user.id,
                "full_name": profile.user.get_full_name() or profile.user.username,
                "username": profile.user.username,
                "phone": profile.user.phone or "",
                "email": profile.user.email or "",
                "is_active": profile.user.is_active,
            }
            for profile in student_profiles
        ]

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "full_name",
            "first_name",
            "last_name",
            "username",
            "phone",
            "email",
            "is_active",
            "children",
        ]

class ParentUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "first_name",
            "last_name",
            "username",
            "phone",
            "email",
            "is_active",
            "password",
        ]

    def validate_first_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Укажите имя родителя")
        return value

    def validate_last_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Укажите фамилию родителя")
        return value

    def validate_username(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Укажите логин родителя")

        queryset = CustomUser.objects.filter(username=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Этот логин уже занят")
        return value

    def validate_phone(self, value):
        value = (value or "").strip() or None
        if not value:
            return None
        if not re.fullmatch(r"\+7\d{10}", value):
            raise serializers.ValidationError("Телефон должен быть в формате +7XXXXXXXXXX")
        queryset = CustomUser.objects.filter(phone=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Пользователь с таким телефоном уже существует")
        return value

    def validate_email(self, value):
        value = (value or "").strip() or None
        if not value:
            return None
        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError("Введите корректный email")
        queryset = CustomUser.objects.filter(email=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует")
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def validate_first_name(self, value):
        value = (value or "").strip()

        if not value:
            raise serializers.ValidationError("Укажите имя ученика")

        return value

    def validate_last_name(self, value):
        value = (value or "").strip()

        if not value:
            raise serializers.ValidationError("Укажите фамилию ученика")

        return value
