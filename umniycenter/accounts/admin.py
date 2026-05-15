from django.contrib import admin

from .models import CustomUser, ParentProfile, StudentProfile, TeacherProfile


class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    can_delete = False
    verbose_name = 'Профиль учителя'
    verbose_name_plural = 'Профиль учителя'
    extra = 0


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    verbose_name = 'Профиль ученика'
    verbose_name_plural = 'Профиль ученика'
    extra = 0


class ParentProfileInline(admin.StackedInline):
    model = ParentProfile
    can_delete = False
    verbose_name = 'Профиль родителя'
    verbose_name_plural = 'Профиль родителя'
    filter_horizontal = ['students']
    extra = 0


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['email', 'first_name', 'last_name', 'username', 'address', 'city', 'country', 'phone', 'sex', 'role', 'is_active']
    list_editable = ['sex', 'role', 'is_active']
    list_filter = ['role', 'is_active', 'sex']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone']
    fields = (
        'username', 'email', 'password', 
        'first_name', 'last_name', 
        'address', 'city', 'country', 'phone', 
        'sex', 'role', 
        'is_active', 'is_staff'
    )
    
    def get_inline_instances(self, request, obj=None):
        """Показываем только нужный inline в зависимости от роли пользователя"""
        if not obj:
            return []
        
        inlines = []
        if obj.role == 0:  # TEACHER
            inlines.append(TeacherProfileInline(self.model, self.admin_site))
        elif obj.role == 1:  # STUDENT
            inlines.append(StudentProfileInline(self.model, self.admin_site))
        elif obj.role == 3:  # PARENT
            inlines.append(ParentProfileInline(self.model, self.admin_site))
        
        return inlines


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_user_email', 'get_user_phone']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    
    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'Email'
    
    def get_user_phone(self, obj):
        return obj.user.phone
    get_user_phone.short_description = 'Телефон'


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_user_email', 'get_user_phone', 'get_parents']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    fields = ['user']
    
    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'Email'
    
    def get_user_phone(self, obj):
        return obj.user.phone
    get_user_phone.short_description = 'Телефон ученика'
    
    def get_parents(self, obj):
        parents = obj.parents.all()
        if not parents:
            return "-"
        return ", ".join([f"{p.user.get_full_name()} ({p.user.phone})" for p in parents])
    get_parents.short_description = 'Родители'


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'get_user_email', 'get_user_phone', 'get_students_count']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    filter_horizontal = ['students']
    
    def get_user_email(self, obj):
        return obj.user.email
    get_user_email.short_description = 'Email'
    
    def get_user_phone(self, obj):
        return obj.user.phone
    get_user_phone.short_description = 'Телефон'
    
    def get_students_count(self, obj):
        return obj.students.count()
    get_students_count.short_description = 'Количество детей'