from rest_framework import serializers

from ..models import Courses


class CourseSerializer(serializers.ModelSerializer):
    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Название курса обязательно")
        return value.strip()

    class Meta:
        model = Courses
        fields = ["id", "name"]
