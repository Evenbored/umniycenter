from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.db.models import Prefetch
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.utils.dateparse import parse_date
import re
from groups.models import SchoolGroups
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CustomUser, UserRole, ParentProfile, StudentProfile, LeadSource
from accounts.permissions import IsAdminOrTeacherRole, IsAdminTeacherOrStudentRole, IsAdminRole
from ..models import StudentGroups
from .serializers import StudentListSerializer, StudentUpdateSerializer


class MyStudentsAPIView(ListAPIView):
    serializer_class = StudentListSerializer
    permission_classes = [IsAdminTeacherOrStudentRole]

    def get_queryset(self):
        user = self.request.user
        
        # Для администратора показываем всех учеников
        if user.role == UserRole.ADMIN:
            membership_prefetch = Prefetch(
                "studentgroups_set",
                queryset=StudentGroups.objects.select_related("group", "group__course", "group__teacher").order_by("group__course__name", "group__number"),
                to_attr="student_group_memberships",
            )
            
            queryset = CustomUser.objects.filter(role=UserRole.STUDENT).prefetch_related(membership_prefetch)
            
            # Применяем фильтры
            search = self.request.query_params.get("search")
            status = self.request.query_params.get("status")
            ordering = self.request.query_params.get("ordering")
            
            if search:
                queryset = queryset.filter(
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(username__icontains=search) |
                    Q(phone__icontains=search) |
                    Q(email__icontains=search)
                )
            
            if status == "active":
                queryset = queryset.filter(is_active=True)
            elif status == "archive":
                queryset = queryset.filter(is_active=False)
            
            ordering_map = {
                "name_az": ("last_name", "first_name", "id"),
                "name_za": ("-last_name", "-first_name", "id"),
                "date_new": ("-date_joined", "id"),
                "date_old": ("date_joined", "id"),
            }
            
            return queryset.order_by(*ordering_map.get(ordering, ("last_name", "first_name", "id")))
        
        # Для учителя показываем только его учеников
        memberships = StudentGroups.objects.select_related("group", "group__course", "group__teacher", "student")

        if user.role == UserRole.TEACHER:
            memberships = memberships.filter(group__teacher=user)
        elif user.role == UserRole.STUDENT:
            memberships = memberships.filter(student=user)
        else:
            return CustomUser.objects.none()

        search = self.request.query_params.get("search")
        group = self.request.query_params.get("group")
        status = self.request.query_params.get("status")
        date_from = parse_date(self.request.query_params.get("date_from") or "")
        date_to = parse_date(self.request.query_params.get("date_to") or "")
        period = self.request.query_params.get("period")
        ordering = self.request.query_params.get("ordering")

        if search:
            memberships = memberships.filter(
                Q(student__first_name__icontains=search)
                | Q(student__last_name__icontains=search)
                | Q(student__username__icontains=search)
                | Q(student__email__icontains=search)
                | Q(student__phone__icontains=search)
            )

        if group:
            memberships = memberships.filter(group_id=group)

        if status == "active":
            memberships = memberships.filter(student__is_active=True)
        elif status == "archive":
            memberships = memberships.filter(student__is_active=False)

        today = timezone.localdate()
        if period == "today":
            date_from = today
            date_to = today
        elif period == "week":
            date_from = today - timedelta(days=7)
            date_to = today
        elif period == "month":
            date_from = today - timedelta(days=30)
            date_to = today

        if date_from:
            memberships = memberships.filter(student__date_joined__date__gte=date_from)

        if date_to:
            memberships = memberships.filter(student__date_joined__date__lte=date_to)

        ordering_map = {
            "name_az": ("last_name", "first_name", "id"),
            "name_za": ("-last_name", "-first_name", "id"),
            "date_new": ("-date_joined", "id"),
            "date_old": ("date_joined", "id"),
        }

        student_ids = memberships.values("student_id")
        membership_prefetch = Prefetch(
            "studentgroups_set",
            queryset=memberships.order_by("group__course__name", "group__number"),
            to_attr="student_group_memberships",
        )

        return (
            CustomUser.objects
            .filter(id__in=student_ids)
            .prefetch_related(membership_prefetch)
            .order_by(*ordering_map.get(ordering, ("last_name", "first_name", "id")))
        )


class StudentsCountAPIView(APIView):
    permission_classes = [IsAdminOrTeacherRole]

    def get(self, request):
        if request.user.role == UserRole.ADMIN:
            count = StudentGroups.objects.values("student_id").distinct().count()
            return Response({"count": count})

        if request.user.role != UserRole.TEACHER:
            return Response({"count": 0})

        key = f"user:{request.user.id}:students_count"
        count = cache.get(key)

        if count is None:
            count = (
                StudentGroups.objects
                .filter(group__teacher=request.user)
                .values("student_id")
                .distinct()
                .count()
            )
            cache.set(key, count, 60)

        return Response({"count": count})

def get_student_with_groups(student_id):
    membership_prefetch = Prefetch(
        "studentgroups_set",
        queryset=StudentGroups.objects.select_related("group", "group__course", "group__teacher").order_by("group__course__name", "group__number"),
        to_attr="student_group_memberships",
    )
    return CustomUser.objects.prefetch_related(membership_prefetch).get(id=student_id, role=UserRole.STUDENT)


def normalize_optional(value):
    return (value or "").strip() or None


def validate_optional_phone(phone):
    phone = normalize_optional(phone)
    if phone and not re.fullmatch(r"\+7\d{10}", phone):
        return None, "Телефон должен быть в формате +7XXXXXXXXXX"
    return phone, None


def validate_optional_email(email):
    email = normalize_optional(email)
    if not email:
        return None, None
    try:
        validate_email(email)
    except ValidationError:
        return None, "Введите корректный email"
    return email, None


def validate_source(source):
    source = normalize_optional(source)
    if source and source not in LeadSource.values:
        return None, "Выберите корректный источник"
    return source, None


def generate_parent_username(parent_first_name, parent_last_name, parent_phone=None):
    if parent_phone:
        base = f"parent_{parent_phone.replace('+', '')}"
    else:
        raw_name = f"{parent_last_name}_{parent_first_name}".strip("_") or "parent"
        base = "parent_" + "".join(ch.lower() if ch.isalnum() else "_" for ch in raw_name).strip("_")

    username = base[:140]
    counter = 1
    while CustomUser.objects.filter(username=username).exists():
        suffix = f"_{counter}"
        username = f"{base[:150 - len(suffix)]}{suffix}"
        counter += 1
    return username


def create_student_with_parent(data):
    first_name = (data.get('first_name') or '').strip()
    last_name = (data.get('last_name') or '').strip()
    sex = data.get('sex')
    phone, phone_error = validate_optional_phone(data.get('phone'))
    email, email_error = validate_optional_email(data.get('email'))
    username = (data.get('username') or '').strip()
    city = normalize_optional(data.get('city'))
    country = normalize_optional(data.get('country'))
    password = data.get('password') or "student123"
    source, source_error = validate_source(data.get('source'))

    parent_first_name = (data.get('parent_first_name') or '').strip()
    parent_last_name = (data.get('parent_last_name') or '').strip()
    parent_phone, parent_phone_error = validate_optional_phone(data.get('parent_phone'))
    parent_email, parent_email_error = validate_optional_email(data.get('parent_email'))

    if not first_name or not last_name or not username:
        return None, {"error": "Заполните имя, фамилию и логин ученика"}

    for error in [phone_error, email_error, parent_phone_error, parent_email_error]:
        if error:
            return None, {"error": error}

    if not parent_first_name or not parent_last_name:
        return None, {"error": "Заполните имя и фамилию родителя"}

    if sex not in ['0', '1', 0, 1, False, True]:
        return None, {"error": "Выберите пол ученика"}

    if source_error:
        return None, {"error": source_error}

    if username.startswith('parent_'):
        return None, {"error": "Логин ученика не может начинаться с 'parent_'"}

    if CustomUser.objects.filter(username=username).exists():
        return None, {"error": f"Логин {username} уже занят"}

    if phone and CustomUser.objects.filter(phone=phone).exists():
        return None, {"error": f"Пользователь с телефоном {phone} уже существует"}

    if email and CustomUser.objects.filter(email=email).exists():
        return None, {"error": f"Пользователь с email {email} уже существует"}

    parent = None
    parent_created = False
    if parent_phone:
        parent = CustomUser.objects.filter(phone=parent_phone, role=UserRole.PARENT).first()

    if parent_email:
        parent_email_queryset = CustomUser.objects.filter(email=parent_email)
        if parent:
            parent_email_queryset = parent_email_queryset.exclude(pk=parent.pk)
        if parent_email_queryset.exists():
            return None, {"error": f"Пользователь с email родителя {parent_email} уже существует"}

    with transaction.atomic():
        student = CustomUser.objects.create_user(
            phone=phone,
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            role=UserRole.STUDENT,
            password=password,
            sex=bool(int(sex)),
            city=city,
            country=country,
        )

        student_profile = StudentProfile.objects.create(user=student, source=source)

        if not parent:
            parent = CustomUser.objects.create_user(
                phone=parent_phone,
                username=generate_parent_username(parent_first_name, parent_last_name, parent_phone),
                first_name=parent_first_name,
                last_name=parent_last_name,
                email=parent_email,
                role=UserRole.PARENT,
                password=data.get('parent_password') or password,
                sex=False,
            )
            parent_created = True

        parent_profile, _ = ParentProfile.objects.get_or_create(user=parent)
        parent_profile.students.add(student_profile)

    return {
        "student": student,
        "parent": parent,
        "parent_created": parent_created,
    }, None


@api_view(["POST"])
def create_student(request):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может создавать учеников"}, status=status.HTTP_403_FORBIDDEN)

    result, error = create_student_with_parent(request.data)
    if error:
        return Response(error, status=status.HTTP_400_BAD_REQUEST)

    updated_student = get_student_with_groups(result["student"].id)
    return Response({
        "message": "Ученик успешно создан",
        "student": StudentListSerializer(updated_student).data,
        "parent_created": result["parent_created"],
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def add_student_to_group(request, student_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может изменять группы ученика"}, status=status.HTTP_403_FORBIDDEN)

    group_id = request.data.get("group_id")

    if not group_id:
        return Response({"error": "Выберите группу"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        student = CustomUser.objects.get(id=student_id, role=UserRole.STUDENT)
    except CustomUser.DoesNotExist:
        return Response({"error": "Ученик не найден"}, status=status.HTTP_404_NOT_FOUND)

    try:
        group = SchoolGroups.objects.get(id=group_id)
    except SchoolGroups.DoesNotExist:
        return Response({"error": "Группа не найдена"}, status=status.HTTP_404_NOT_FOUND)

    membership, created = StudentGroups.objects.get_or_create(student=student, group=group)

    if not created:
        return Response({"error": "Ученик уже состоит в этой группе"}, status=status.HTTP_400_BAD_REQUEST)

    updated_student = get_student_with_groups(student.id)
    return Response({
        "message": "Ученик добавлен в группу",
        "membership_id": membership.id,
        "student": StudentListSerializer(updated_student).data,
    }, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
def update_student(request, student_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может редактировать ученика"}, status=status.HTTP_403_FORBIDDEN)

    try:
        student = CustomUser.objects.get(id=student_id, role=UserRole.STUDENT)
    except CustomUser.DoesNotExist:
        return Response({"error": "Ученик не найден"}, status=status.HTTP_404_NOT_FOUND)

    serializer = StudentUpdateSerializer(student, data=request.data, partial=True)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Обработка данных родителей
    parents_data = request.data.get("parents", [])
    source = None
    if "source" in request.data:
        source, source_error = validate_source(request.data.get("source"))
        if source_error:
            return Response({"error": source_error}, status=status.HTTP_400_BAD_REQUEST)
    if len(parents_data) > 2:
        return Response({"error": "У ученика может быть не больше двух родителей"}, status=status.HTTP_400_BAD_REQUEST)
    
    with transaction.atomic():
        serializer.save()
        
        # Получаем или создаем StudentProfile
        try:
            student_profile = student.student_profile
        except StudentProfile.DoesNotExist:
            student_profile = StudentProfile.objects.create(user=student)
        
        if "source" in request.data:
            student_profile.source = source
            student_profile.save(update_fields=["source"])

        if parents_data:
            current_parent_profile_ids = set(student_profile.parents.values_list("id", flat=True))
            target_parent_profiles = []

            for parent_data in parents_data:
                parent_id = parent_data.get("id")
                parent_first_name = (parent_data.get("first_name") or "").strip()
                parent_last_name = (parent_data.get("last_name") or "").strip()
                parent_phone_user, parent_phone_error = validate_optional_phone(parent_data.get("phone"))
                parent_email, parent_email_error = validate_optional_email(parent_data.get("email"))

                if not parent_first_name or not parent_last_name:
                    return Response({"error": "Заполните имя и фамилию родителя"}, status=status.HTTP_400_BAD_REQUEST)

                if parent_phone_error:
                    return Response({"error": parent_phone_error}, status=status.HTTP_400_BAD_REQUEST)

                if parent_email_error:
                    return Response({"error": parent_email_error}, status=status.HTTP_400_BAD_REQUEST)

                if parent_id:
                    try:
                        parent_user = CustomUser.objects.get(id=parent_id, role=UserRole.PARENT)
                        parent_profile = parent_user.parent_profile
                    except (CustomUser.DoesNotExist, ParentProfile.DoesNotExist):
                        return Response({"error": "Родитель не найден"}, status=status.HTTP_404_NOT_FOUND)

                    if parent_profile.id not in current_parent_profile_ids:
                        return Response({"error": "Родитель не привязан к этому ученику"}, status=status.HTTP_400_BAD_REQUEST)
                elif parent_phone_user:
                    parent_user = CustomUser.objects.filter(phone=parent_phone_user, role=UserRole.PARENT).first()
                    if parent_user:
                        parent_profile, _ = ParentProfile.objects.get_or_create(user=parent_user)
                    else:
                        parent_user = CustomUser.objects.create_user(
                            phone=parent_phone_user,
                            username=generate_parent_username(parent_first_name, parent_last_name, parent_phone_user),
                            first_name=parent_first_name,
                            last_name=parent_last_name,
                            email=parent_email,
                            role=UserRole.PARENT,
                            password=request.data.get("parent_password") or "parent123",
                            sex=False,
                        )
                        parent_profile = ParentProfile.objects.create(user=parent_user)
                else:
                    if parent_email and CustomUser.objects.filter(email=parent_email).exists():
                        return Response({"error": "Пользователь с таким email родителя уже существует"}, status=status.HTTP_400_BAD_REQUEST)

                    parent_user = CustomUser.objects.create_user(
                        phone=None,
                        username=generate_parent_username(parent_first_name, parent_last_name),
                        first_name=parent_first_name,
                        last_name=parent_last_name,
                        email=parent_email,
                        role=UserRole.PARENT,
                        password=request.data.get("parent_password") or "parent123",
                        sex=False,
                    )
                    parent_profile = ParentProfile.objects.create(user=parent_user)

                if parent_profile not in target_parent_profiles:
                    target_parent_profiles.append(parent_profile)

                if len(target_parent_profiles) > 2:
                    return Response({"error": "У ученика может быть не больше двух родителей"}, status=status.HTTP_400_BAD_REQUEST)

                # Обновляем данные родителя.
                if parent_phone_user and parent_user.phone != parent_phone_user:
                    if CustomUser.objects.filter(phone=parent_phone_user).exclude(pk=parent_user.pk).exists():
                        return Response({"error": "Пользователь с таким телефоном родителя уже существует"}, status=status.HTTP_400_BAD_REQUEST)
                    parent_user.phone = parent_phone_user
                elif not parent_phone_user:
                    parent_user.phone = None

                if parent_email != parent_user.email:
                    if parent_email and CustomUser.objects.filter(email=parent_email).exclude(pk=parent_user.pk).exists():
                        return Response({"error": "Пользователь с таким email родителя уже существует"}, status=status.HTTP_400_BAD_REQUEST)
                    parent_user.email = parent_email

                parent_user.first_name = parent_first_name
                parent_user.last_name = parent_last_name
                parent_user.save()

            existing_ids = set(current_parent_profile_ids)
            target_ids = {profile.id for profile in target_parent_profiles}
            if len(existing_ids | target_ids) > 2:
                return Response({"error": "У ученика может быть не больше двух родителей"}, status=status.HTTP_400_BAD_REQUEST)

            for parent_profile in target_parent_profiles:
                parent_profile.students.add(student_profile)

    updated_student = get_student_with_groups(student_id)

    return Response({
        "message": "Данные ученика обновлены",
        "student": StudentListSerializer(updated_student).data,
    })


@api_view(["DELETE"])
def remove_student_from_group(request, student_id, membership_id):
    if request.user.role != UserRole.ADMIN:
        return Response({"error": "Только администратор может изменять группы ученика"}, status=status.HTTP_403_FORBIDDEN)

    try:
        membership = StudentGroups.objects.get(id=membership_id, student_id=student_id)
    except StudentGroups.DoesNotExist:
        return Response({"error": "Связь ученика с группой не найдена"}, status=status.HTTP_404_NOT_FOUND)

    membership.delete()
    updated_student = get_student_with_groups(student_id)

    return Response({
        "message": "Ученик удален из группы",
        "student": StudentListSerializer(updated_student).data,
    })
