from rest_framework import serializers

from .models import ParticipantRequest


class ParticipantRequestSerializer(serializers.ModelSerializer):
    courses_display = serializers.SerializerMethodField()
    courses_list = serializers.SerializerMethodField()
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    
    def get_courses_display(self, obj):
        return obj.get_courses_display()
    
    def get_courses_list(self, obj):
        return [{"id": course.id, "name": course.name} for course in obj.courses.all()]
    
    class Meta:
        model = ParticipantRequest
        fields = [
            "id",
            "parent_fio",
            "child_fio",
            "phone",
            "email",
            "age",
            "courses_display",
            "courses_list",
            "source",
            "source_display",
            "created",
            "checked",
        ]
