"""Generate demo CRM data including subscriptions, payments and single-lesson sales.

Run from project directory:
    python generate_crm_demo_data.py

The script is intentionally idempotent-ish for core reference data, but it creates
fresh sales/orders each run to provide visible dashboard history.
"""
import os
import random
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "umniycenter.settings")

import django
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import ParentProfile, StudentProfile, TeacherProfile, UserRole
from courses.models import Courses
from groups.models import SchoolGroups
from schedule.models import Lesson
from schedule.services import LessonService, get_lesson_end_time
from sales.services import OrderService
from students.models import StudentGroups
from subscriptions.models import Payment, SubscriptionLog, Tariff
from subscriptions.payment_service import PaymentService


User = get_user_model()


def user(username, role, **kwargs):
    obj, created = User.objects.get_or_create(username=username, defaults={"role": role, **kwargs})
    if created:
        obj.set_password("demo12345")
        obj.save(update_fields=["password"])
    return obj


def main():
    today = timezone.localdate()
    admin = user("crm_admin", UserRole.ADMIN, first_name="CRM", last_name="Admin", is_staff=True)
    teacher = user("teacher_demo", UserRole.TEACHER, first_name="Анна", last_name="Учитель")
    TeacherProfile.objects.get_or_create(user=teacher)

    course, _ = Courses.objects.get_or_create(name="Ментальная арифметика")
    group, _ = SchoolGroups.objects.get_or_create(number="A1", course=course, defaults={"teacher": teacher, "is_active": True})

    group_tariff, _ = Tariff.objects.get_or_create(
        name="Групповой 8 занятий",
        course=course,
        subscription_type=Tariff.SUBSCRIPTION_TYPE_GROUP,
        defaults={"lessons_count": 8, "validity_days": 30, "price": Decimal("6000.00"), "is_active": True},
    )
    individual_tariff, _ = Tariff.objects.get_or_create(
        name="Индивидуальный 4 занятия",
        course=course,
        subscription_type=Tariff.SUBSCRIPTION_TYPE_INDIVIDUAL,
        defaults={"lessons_count": 4, "validity_days": 30, "price": Decimal("9000.00"), "is_active": True},
    )

    students = []
    for index in range(1, 8):
        parent = user(f"parent_demo_{index}", UserRole.PARENT, first_name=f"Родитель{index}", last_name="Демо")
        parent_profile, _ = ParentProfile.objects.get_or_create(user=parent)
        student = user(f"student_demo_{index}", UserRole.STUDENT, first_name=f"Ученик{index}", last_name="Демо")
        student_profile, _ = StudentProfile.objects.get_or_create(user=student)
        parent_profile.students.add(student_profile)
        StudentGroups.objects.get_or_create(student=student, group=group)
        students.append((student, parent))

    for day_offset in range(-20, 5):
        sale_date = today + timedelta(days=day_offset)
        student, parent = random.choice(students)
        tariff = group_tariff if random.random() > 0.35 else individual_tariff
        order, sub = OrderService.create_subscription_order_new(
            student=student,
            parent=parent,
            tariff=tariff,
            group=group if tariff.subscription_type == Tariff.SUBSCRIPTION_TYPE_GROUP else None,
            created_by=admin,
            comment="Демо оформление абонемента",
        )
        sub.start_date = sale_date
        sub.end_date = sale_date + timedelta(days=tariff.validity_days)
        sub.lessons_used = random.randint(0, max(tariff.lessons_count - 1, 0))
        sub.save(update_fields=["start_date", "end_date", "lessons_used", "updated_at"])
        SubscriptionLog.log(sub, "created", comment="Демо-генерация", created_by=admin)
        paid_at = timezone.make_aware(timezone.datetime.combine(sale_date, timezone.datetime.min.time())) + timedelta(hours=random.randint(9, 20))
        payment_result = PaymentService.create_payment_for_order(order.id, parent.id, payment_method=random.choice(["cash", "card", "transfer"]))
        payment = Payment.objects.get(id=payment_result["payment_id"])
        payment.paid_at = paid_at
        payment.notes = "Демо оплата абонемента"
        payment.save(update_fields=["paid_at", "notes", "updated_at"])
        PaymentService.confirm_offline_payment(payment.id, confirmed_by=admin)

    for day_offset in range(-14, 5):
        lesson_date = today + timedelta(days=day_offset)
        start_at = timezone.make_aware(timezone.datetime.combine(lesson_date, timezone.datetime.min.time())) + timedelta(hours=random.randint(10, 18))
        is_group = random.random() > 0.45
        student, parent = random.choice(students)
        lesson_type = Lesson.LessonType.SINGLE_GROUP if is_group else Lesson.LessonType.SINGLE_INDIVIDUAL
        end_time = get_lesson_end_time(start_at.time(), 2)
        ends_at = timezone.make_aware(timezone.datetime.combine(start_at.date(), end_time))
        participants = [pair[0] for pair in random.sample(students, k=min(3, len(students)))] if is_group else [student]
        lesson = LessonService.create_lesson(
            lesson_type=lesson_type,
            group=group if is_group else None,
            course=course,
            teacher=teacher,
            starts_at=start_at,
            ends_at=ends_at,
            participants=participants,
            created_by=admin,
        )
        order = OrderService.create_single_lesson_order(
            lesson=lesson,
            student=None if is_group else student,
            parent=parent if not is_group else None,
            amount=Decimal("1200.00") if is_group else Decimal("2500.00"),
            payment_method=random.choice(["cash", "card", "transfer"]),
            paid=True,
            created_by=admin,
            comment="Демо продажа разового занятия",
        )
        order.paid_at = start_at - timedelta(days=random.randint(0, 2), hours=random.randint(0, 5))
        order.save(update_fields=["paid_at", "updated_at"])

    print("CRM demo data generated: subscriptions, payments and single-lesson orders are ready for dashboard.")


if __name__ == "__main__":
    main()
