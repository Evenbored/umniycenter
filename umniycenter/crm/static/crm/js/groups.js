(function () {
    function getCsrfToken() {
        const name = "csrftoken";
        let cookieValue = null;

        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");

            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();

                if (cookie.substring(0, name.length + 1) === (name + "=")) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }

        return cookieValue;
    }

    const headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    };

    const headersWithCsrf = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
    };

    let currentGroups = [];
    let currentStudents = [];
    let currentCourses = [];
    let currentTeachers = [];
    let currentScheduleTemplates = [];
    let selectedGroupId = null;

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function getInitials(name) {
        const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
        return ((parts[0]?.[0] || "У") + (parts[1]?.[0] || "")).toUpperCase();
    }

    function getStatusBadge(isActive) {
        if (isActive) {
            return '<span class="crm-status-badge crm-status-badge--active">Активная</span>';
        }

        return '<span class="crm-status-badge crm-status-badge--archive">Архивная</span>';
    }

    function updateSidebarCount(groups) {
        document.querySelectorAll('[data-nav-count="groups"]').forEach((item) => {
            item.textContent = groups.length;
        });
    }

    function getGroupById(groupId) {
        return currentGroups.find((group) => group.id === groupId);
    }

    function getGroupStudents(groupId) {
        return currentStudents.filter((student) => {
            return (student.groups || []).some((group) => group.group === groupId);
        });
    }

    function renderGroups(groups) {
        const tbody = document.getElementById("groupsTableBody");
        document.getElementById("groupsCount").textContent = groups.length;
        updateSidebarCount(groups);

        if (!groups.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="crm-table-empty">Группы не найдены. Попробуйте изменить фильтры.</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = groups.map((group) => `
            <tr onclick="openGroupDetailsDrawer(${group.id})">
                <td>
                    <div class="crm-table-name">${escapeHtml(group.course_name)} · ${escapeHtml(group.number)}</div>
                    <span class="crm-table-meta">ID ${group.id}</span>
                </td>
                <td><span class="crm-group-chip">${escapeHtml(group.course_name)}</span></td>
                <td>${escapeHtml(group.teacher_name || '-')}</td>
                <td><strong>${group.students_count || 0}</strong></td>
                <td>${getStatusBadge(group.is_active)}</td>
                <td>
                    <button class="crm-table-action-btn" type="button" onclick="event.stopPropagation(); openGroupDetailsDrawer(${group.id})" title="Открыть группу">
                        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                        </svg>
                    </button>
                </td>
            </tr>
        `).join("");
    }

    function applyFilters() {
        const search = document.getElementById("groupsSearch").value.trim().toLowerCase();
        const courseId = document.getElementById("groupsCourseFilter").value;
        const teacherId = document.getElementById("groupsTeacherFilter").value;
        const status = document.getElementById("groupsStatusFilter").value;
        const sort = document.getElementById("groupsSortFilter").value;
        const onlyEmpty = document.getElementById("groupsEmptyFilter").checked;

        let filtered = [...currentGroups];

        if (search) {
            filtered = filtered.filter((group) => (
                [group.number, group.course_name, group.teacher_name].join(" ").toLowerCase().includes(search)
            ));
        }

        if (courseId) {
            filtered = filtered.filter((group) => String(group.course) === courseId);
        }

        if (teacherId) {
            filtered = filtered.filter((group) => String(group.teacher) === teacherId);
        }

        if (status === "active") {
            filtered = filtered.filter((group) => group.is_active);
        } else if (status === "archive") {
            filtered = filtered.filter((group) => !group.is_active);
        }

        if (onlyEmpty) {
            filtered = filtered.filter((group) => Number(group.students_count || 0) === 0);
        }

        filtered.sort((a, b) => {
            if (sort === "students_desc") {
                return Number(b.students_count || 0) - Number(a.students_count || 0);
            }

            if (sort === "students_asc") {
                return Number(a.students_count || 0) - Number(b.students_count || 0);
            }

            return `${a.course_name} ${a.number}`.localeCompare(`${b.course_name} ${b.number}`);
        });

        renderGroups(filtered);
    }

    function renderCourseFilter(courses) {
        const select = document.getElementById("groupsCourseFilter");
        select.innerHTML = '<option value="">Все курсы</option>' + courses.map((course) => (
            `<option value="${course.id}">${escapeHtml(course.name)}</option>`
        )).join("");
    }

    function renderTeacherFilter(groups) {
        const teachers = new Map();
        groups.forEach((group) => {
            if (group.teacher && group.teacher_name) {
                teachers.set(String(group.teacher), group.teacher_name);
            }
        });

        const select = document.getElementById("groupsTeacherFilter");
        select.innerHTML = '<option value="">Все преподаватели</option>' + Array.from(teachers.entries()).map(([id, name]) => (
            `<option value="${id}">${escapeHtml(name)}</option>`
        )).join("");
    }

    function renderEditCourseOptions(courses) {
        const select = document.getElementById("groupEditCourse");
        select.innerHTML = '<option value="">Выберите курс</option>' + courses.map((course) => (
            `<option value="${course.id}">${escapeHtml(course.name)}</option>`
        )).join("");
    }

    function renderEditTeacherOptions(teachers) {
        const select = document.getElementById("groupEditTeacher");
        select.innerHTML = '<option value="">Выберите преподавателя</option>' + teachers.map((teacher) => (
            `<option value="${teacher.id}">${escapeHtml([teacher.last_name, teacher.first_name].filter(Boolean).join(" ") || teacher.username)}</option>`
        )).join("");
    }

    function setGroupEditAlert(message, isSuccess) {
        const alert = document.getElementById("groupEditAlert");
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function setScheduleTemplateAlert(message, isSuccess) {
        const alert = document.getElementById("scheduleTemplateAlert");
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function getErrorMessage(data) {
        if (data.error) {
            return data.error;
        }

        return Object.keys(data).map((field) => {
            const value = data[field];
            return Array.isArray(value) ? value.join(" ") : String(value);
        }).join(" ") || "Не удалось сохранить группу";
    }

    function updateGroupInState(updatedGroup) {
        const index = currentGroups.findIndex((group) => group.id === updatedGroup.id);

        if (index !== -1) {
            currentGroups[index] = updatedGroup;
        }
    }

    function setGroupEditMode(isEditing) {
        document.getElementById("groupEditForm").hidden = !isEditing;
        document.getElementById("groupEditCancelBtn").hidden = !isEditing;
        document.getElementById("groupEditSaveBtn").hidden = !isEditing;
        document.getElementById("groupEditToggleBtn").hidden = isEditing;

        if (!isEditing) {
            setGroupEditAlert("");
        }
    }

    function fillGroupEditForm(group) {
        document.getElementById("groupEditNumber").value = group.number || "";
        document.getElementById("groupEditCourse").value = group.course || "";
        document.getElementById("groupEditTeacher").value = group.teacher || "";
        document.getElementById("groupEditIsActive").value = group.is_active ? "true" : "false";
    }

    function loadGroups() {
        const tbody = document.getElementById("groupsTableBody");
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="crm-table-loading">
                    <div class="crm-spinner"></div>
                    <span>Загрузка групп...</span>
                </td>
            </tr>
        `;

        fetch("/api/v1/groups/my/?status=", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load groups");
                }
                return response.json();
            })
            .then((data) => {
                currentGroups = data;
                renderTeacherFilter(currentGroups);
                applyFilters();
            })
            .catch(() => {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6" class="crm-table-empty">Не удалось загрузить группы. Попробуйте обновить страницу.</td>
                    </tr>
                `;
            });
    }

    function loadStudents() {
        return fetch("/api/v1/students/my/?status=", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load students");
                }
                return response.json();
            })
            .then((data) => {
                currentStudents = data;
            })
            .catch(() => {
                currentStudents = [];
            });
    }

    function loadCourses() {
        fetch("/api/v1/courses/", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load courses");
                }
                return response.json();
            })
            .then((data) => {
                currentCourses = data;
                renderCourseFilter(currentCourses);
                renderEditCourseOptions(currentCourses);
            })
            .catch(() => {
                currentCourses = [];
            });
    }

    function loadTeachers() {
        fetch("/api/v1/users/?role=0", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load teachers");
                }
                return response.json();
            })
            .then((data) => {
                currentTeachers = data;
                renderEditTeacherOptions(currentTeachers);
            })
            .catch(() => {
                currentTeachers = [];
            });
    }

    function getGroupStudents(groupId) {
        return currentStudents.filter((student) => (
            (student.groups || []).some((group) => Number(group.group) === Number(groupId))
        ));
    }

    function renderGroupStudents(students) {
        const target = document.getElementById("groupDrawerStudents");

        if (!students.length) {
            target.innerHTML = '<div class="crm-table-empty">В группе пока нет учеников</div>';
            return;
        }

        target.innerHTML = students.map((student) => `
            <div class="crm-group-student" onclick="openStudentFromGroup(${student.student})">
                <div class="crm-group-student__main">
                    <div class="crm-group-student__avatar">${escapeHtml(getInitials(student.student_full_name))}</div>
                    <div>
                        <strong>${escapeHtml(student.student_full_name)}</strong>
                        <span>${escapeHtml(student.student_details?.username || '')}</span>
                    </div>
                </div>
                <div class="crm-group-student__contacts">
                    ${escapeHtml(student.student_phone || '-')}<br>
                    ${escapeHtml(student.student_email || '')}
                </div>
            </div>
        `).join("");
    }

    window.openStudentFromGroup = function (studentId) {
        window.location.href = `/crm/students/?student=${studentId}`;
    };

    function renderScheduleTemplates(templates) {
        const target = document.getElementById("groupScheduleTemplates");

        if (!templates.length) {
            target.innerHTML = '<div class="crm-table-empty">Стандартное время не настроено</div>';
            return;
        }

        target.innerHTML = templates.map((template) => `
            <div class="crm-schedule-template-card">
                <div class="crm-schedule-template-card__info">
                    <div class="crm-schedule-template-card__day">${escapeHtml(template.weekday_display)}</div>
                    <div class="crm-schedule-template-card__time">${escapeHtml(template.start_time)} · ${escapeHtml(template.lessons_count_display)}</div>
                </div>
                <button class="crm-icon-btn" type="button" onclick="deleteScheduleTemplate(${template.id})" title="Удалить">
                    <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
        `).join("");
    }

    function loadScheduleTemplates(groupId) {
        if (!groupId) return;

        fetch(`/api/v1/schedule/templates/?group=${groupId}`, { headers })
            .then((response) => {
                if (!response.ok) throw new Error("Failed to load templates");
                return response.json();
            })
            .then((data) => {
                currentScheduleTemplates = data;
                renderScheduleTemplates(currentScheduleTemplates);
            })
            .catch(() => {
                document.getElementById("groupScheduleTemplates").innerHTML = '<div class="crm-table-empty">Не удалось загрузить расписание</div>';
            });
    }

    window.openGroupDetailsDrawer = function (groupId) {
        const group = getGroupById(groupId);

        if (!group) {
            return;
        }

        const students = getGroupStudents(group.id);
        selectedGroupId = group.id;

        document.getElementById("groupDrawerTitle").textContent = `Группа #${group.id}`;
        document.getElementById("groupDrawerSubtitle").textContent = group.course_name;
        document.getElementById("groupDrawerName").textContent = group.number;
        document.getElementById("groupDrawerIcon").textContent = getInitials(group.number);
        document.getElementById("groupDrawerStatus").innerHTML = getStatusBadge(group.is_active);
        document.getElementById("groupDrawerCourse").textContent = group.course_name;
        document.getElementById("groupDrawerTeacher").textContent = group.teacher_name;
        document.getElementById("groupDrawerStudentsCount").textContent = students.length;
        document.getElementById("groupDrawerId").textContent = group.id;
        fillGroupEditForm(group);
        setGroupEditMode(false);
        renderGroupStudents(students);
        loadScheduleTemplates(group.id);

        document.getElementById("groupDetailsDrawer").classList.add("is-open");
    };

    window.openAddScheduleTemplateModal = function () {
        if (!selectedGroupId) return;
        setScheduleTemplateAlert("");
        document.getElementById("scheduleTemplateModal").classList.add("is-open");
    };

    window.closeScheduleTemplateModal = function () {
        document.getElementById("scheduleTemplateModal").classList.remove("is-open");
        document.getElementById("scheduleTemplateForm").reset();
        setScheduleTemplateAlert("");
    };

    function createScheduleTemplate(event) {
        event.preventDefault();

        if (!selectedGroupId) return;

        const payload = {
            group: selectedGroupId,
            weekday: Number(document.getElementById("templateWeekday").value),
            start_time: document.getElementById("templateStartTime").value,
            lessons_count: Number(document.getElementById("templateLessonsCount").value),
            is_active: true,
        };

        setScheduleTemplateAlert("");
        document.getElementById("scheduleTemplateSubmitBtn").disabled = true;

        fetch("/api/v1/schedule/templates/create/", {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify(payload),
        })
            .then((response) => {
                if (!response.ok) {
                    return response.json().then((data) => {
                        throw new Error(data.error || getErrorMessage(data));
                    });
                }
                return response.json();
            })
            .then(() => {
                setScheduleTemplateAlert("Время добавлено", true);
                loadScheduleTemplates(selectedGroupId);
                setTimeout(closeScheduleTemplateModal, 500);
            })
            .catch((error) => {
                setScheduleTemplateAlert(error.message, false);
            })
            .finally(() => {
                document.getElementById("scheduleTemplateSubmitBtn").disabled = false;
            });
    }

    window.deleteScheduleTemplate = function (templateId) {
        if (!selectedGroupId) return;

        fetch(`/api/v1/schedule/templates/${templateId}/`, {
            method: "DELETE",
            headers: headersWithCsrf,
        })
            .then((response) => {
                if (!response.ok) {
                    return response.json().then((data) => {
                        throw new Error(data.error || "Не удалось удалить время");
                    });
                }
                loadScheduleTemplates(selectedGroupId);
            })
            .catch((error) => {
                alert(error.message);
            });
    };

    window.closeGroupDetailsDrawer = function () {
        document.getElementById("groupDetailsDrawer").classList.remove("is-open");
        selectedGroupId = null;
        setGroupEditMode(false);
    };

    window.refreshGroups = function () {
        loadCourses();
        loadTeachers();
        loadStudents().then(loadGroups);
    };

    window.exportGroups = function () {
        alert("Экспорт групп будет реализован позже.");
    };

    window.showGroupEditForm = function () {
        const group = currentGroups.find((item) => item.id === selectedGroupId);

        if (!group) {
            return;
        }

        fillGroupEditForm(group);
        setGroupEditMode(true);
    };

    window.cancelGroupEdit = function () {
        const group = currentGroups.find((item) => item.id === selectedGroupId);

        if (group) {
            fillGroupEditForm(group);
        }

        setGroupEditMode(false);
    };

    function saveGroupEdit(event) {
        event.preventDefault();

        if (!selectedGroupId) {
            return;
        }

        const payload = {
            number: document.getElementById("groupEditNumber").value.trim(),
            course: Number(document.getElementById("groupEditCourse").value),
            teacher: Number(document.getElementById("groupEditTeacher").value),
            is_active: document.getElementById("groupEditIsActive").value === "true",
        };

        setGroupEditAlert("");
        document.getElementById("groupEditSaveBtn").disabled = true;

        fetch(`/api/v1/groups/${selectedGroupId}/`, {
            method: "PATCH",
            headers: headersWithCsrf,
            body: JSON.stringify(payload),
        })
            .then((response) => {
                if (!response.ok) {
                    return response.json().then((data) => {
                        throw new Error(getErrorMessage(data));
                    });
                }
                return response.json();
            })
            .then((data) => {
                updateGroupInState(data.group);
                renderTeacherFilter(currentGroups);
                applyFilters();
                selectedGroupId = data.group.id;
                openGroupDetailsDrawer(data.group.id);
                setGroupEditMode(true);
                setGroupEditAlert("Группа сохранена", true);
            })
            .catch((error) => {
                setGroupEditAlert(error.message, false);
            })
            .finally(() => {
                document.getElementById("groupEditSaveBtn").disabled = false;
            });
    }

    function formatDate(isoString) {
        if (!isoString) {
            return "-";
        }

        const date = new Date(isoString);
        return date.toLocaleDateString("ru-RU", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        });
    }

    window.openStudentFromGroup = function (studentId) {
        const student = currentStudents.find((item) => item.student === studentId);

        if (!student) {
            return;
        }

        document.getElementById("studentDrawerTitle").textContent = `Ученик #${student.student}`;
        document.getElementById("studentDrawerSubtitle").textContent = student.student_details?.username || "";
        document.getElementById("studentDrawerInitials").textContent = getInitials(student.student_full_name).toUpperCase();
        document.getElementById("studentDrawerName").textContent = student.student_full_name;
        document.getElementById("studentDrawerStatus").innerHTML = getStatusBadge(student.student_is_active);
        document.getElementById("studentDrawerPhone").textContent = student.student_phone || "-";
        document.getElementById("studentDrawerEmail").textContent = student.student_email || "-";
        document.getElementById("studentDrawerCity").textContent = student.student_city || "-";
        document.getElementById("studentDrawerDate").textContent = formatDate(student.student_date_joined);
        document.getElementById("studentDrawerGroups").innerHTML = (student.groups || []).map((group) => `
            <span class="crm-tag">${escapeHtml(group.course_name)} · ${escapeHtml(group.group_number)} · ${escapeHtml(group.teacher_name)}</span>
        `).join("") || '<span class="crm-tag">Без группы</span>';

        document.getElementById("studentDetailsDrawer").classList.add("is-open");
    };

    window.closeStudentDetailsDrawer = function () {
        document.getElementById("studentDetailsDrawer").classList.remove("is-open");
    };

    window.openCreateGroupDrawer = function () {
        setCreateGroupAlert("");
        document.getElementById("createGroupForm").reset();
        renderCreateCourseOptions(currentCourses);
        renderCreateTeacherOptions(currentTeachers);
        document.getElementById("createGroupDrawer").classList.add("is-open");
    };

    window.closeCreateGroupDrawer = function () {
        document.getElementById("createGroupDrawer").classList.remove("is-open");
        document.getElementById("createGroupForm").reset();
        setCreateGroupAlert("");
    };

    function renderCreateCourseOptions(courses) {
        const select = document.getElementById("createGroupCourse");
        select.innerHTML = '<option value="">Выберите курс</option>' + courses.map((course) => (
            `<option value="${course.id}">${escapeHtml(course.name)}</option>`
        )).join("");
    }

    function renderCreateTeacherOptions(teachers) {
        const select = document.getElementById("createGroupTeacher");
        select.innerHTML = '<option value="">Выберите преподавателя</option>' + teachers.map((teacher) => (
            `<option value="${teacher.id}">${escapeHtml([teacher.last_name, teacher.first_name].filter(Boolean).join(" ") || teacher.username)}</option>`
        )).join("");
    }

    function setCreateGroupAlert(message, isSuccess) {
        const alert = document.getElementById("createGroupAlert");
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function createGroup(event) {
        event.preventDefault();

        const number = document.getElementById("createGroupNumber").value.trim();
        const course = document.getElementById("createGroupCourse").value;
        const teacher = document.getElementById("createGroupTeacher").value;
        const defaultTime = document.getElementById("createGroupDefaultTime").value;
        const duration = document.getElementById("createGroupDuration").value;

        if (!number) {
            setCreateGroupAlert("Номер группы обязателен");
            return;
        }

        if (!course) {
            setCreateGroupAlert("Выберите курс");
            return;
        }

        if (!teacher) {
            setCreateGroupAlert("Выберите преподавателя");
            return;
        }

        const submitBtn = document.getElementById("createGroupSubmitBtn");
        submitBtn.disabled = true;
        submitBtn.textContent = "Сохранение...";

        const payload = {
            number: number,
            course: parseInt(course),
            teacher: parseInt(teacher),
        };

        if (defaultTime) {
            payload.default_lesson_time = defaultTime;
            payload.default_lesson_duration = parseInt(duration);
        }

        fetch("/api/v1/groups/create/", {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify(payload),
        })
            .then((response) => response.text().then((text) => {
                const data = text ? JSON.parse(text) : {};
                return { ok: response.ok, data };
            }))
            .then(({ ok, data }) => {
                if (ok) {
                    setCreateGroupAlert("Группа успешно создана", true);
                    setTimeout(() => {
                        closeCreateGroupDrawer();
                        loadGroups();
                    }, 1000);
                } else {
                    setCreateGroupAlert(getErrorMessage(data));
                }
            })
            .catch(() => {
                setCreateGroupAlert("Не удалось создать группу. Попробуйте позже.");
            })
            .finally(() => {
                submitBtn.disabled = false;
                submitBtn.textContent = "Сохранить группу";
            });
    }

    document.addEventListener("DOMContentLoaded", () => {
        loadCourses();
        loadTeachers();
        loadStudents().then(loadGroups);

        document.getElementById("groupsSearch").addEventListener("input", applyFilters);
        document.getElementById("groupsCourseFilter").addEventListener("change", applyFilters);
        document.getElementById("groupsTeacherFilter").addEventListener("change", applyFilters);
        document.getElementById("groupsStatusFilter").addEventListener("change", applyFilters);
        document.getElementById("groupsSortFilter").addEventListener("change", applyFilters);
        document.getElementById("groupsEmptyFilter").addEventListener("change", applyFilters);
        document.getElementById("groupEditForm").addEventListener("submit", saveGroupEdit);
        document.getElementById("scheduleTemplateForm").addEventListener("submit", createScheduleTemplate);
        document.getElementById("createGroupForm").addEventListener("submit", createGroup);
        
        const openCreateBtn = document.getElementById("openCreateGroupBtn");
        if (openCreateBtn) {
            openCreateBtn.addEventListener("click", openCreateGroupDrawer);
        }
    });
})();
