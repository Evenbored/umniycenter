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

    const headers = { "Accept": "application/json", "X-Requested-With": "XMLHttpRequest" };
    const headersWithCsrf = { ...headers, "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() };

    let currentGroups = [];
    let currentLessons = [];
    let currentTemplates = [];
    let currentTeachers = [];
    let currentStudents = [];
    let currentCourses = [];
    let selectedTemplateId = null;
    let selectedLessonId = null;

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function toDateInput(date) {
        return date.toISOString().slice(0, 10);
    }

    window.setDateRangeToday = function () {
        const today = new Date();
        document.getElementById("scheduleDateFrom").value = toDateInput(today);
        document.getElementById("scheduleDateTo").value = toDateInput(today);
        loadSchedule();
    };

    window.setDateRangeWeek = function () {
        const today = new Date();
        const weekLater = new Date();
        weekLater.setDate(today.getDate() + 7);
        document.getElementById("scheduleDateFrom").value = toDateInput(today);
        document.getElementById("scheduleDateTo").value = toDateInput(weekLater);
        loadSchedule();
    };

    window.setDateRangeMonth = function () {
        const today = new Date();
        const monthLater = new Date();
        monthLater.setDate(today.getDate() + 30);
        document.getElementById("scheduleDateFrom").value = toDateInput(today);
        document.getElementById("scheduleDateTo").value = toDateInput(monthLater);
        loadSchedule();
    };

    function formatDateTime(value) {
        if (!value) return "-";
        return new Date(value).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
    }

    function formatDateOnly(value) {
        if (!value) return "-";
        return new Date(value).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
    }

    function formatTime(value) {
        if (!value) return "-";
        // Если это строка времени в формате HH:MM:SS, берем только HH:MM
        if (typeof value === 'string' && value.includes(':')) {
            return value.slice(0, 5);
        }
        return value;
    }

    function statusLabel(status) {
        const labels = { 
            scheduled: "Запланировано", 
            completed: "Прошло",
            cancelled: "Отменено", 
            rescheduled: "Перенесено" 
        };
        return labels[status] || status;
    }

    function setAlert(id, message, isSuccess) {
        const alert = document.getElementById(id);
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function fillGroupOptions() {
        const options = currentGroups.map((group) => `<option value="${group.id}">${escapeHtml(group.course_name)} · ${escapeHtml(group.number)}</option>`).join("");
        document.getElementById("scheduleGroupFilter").innerHTML = '<option value="">Все группы</option>' + options;
        document.getElementById("generateGroup").innerHTML = '<option value="">Все группы</option>' + options;
        document.getElementById("templateGroup").innerHTML = '<option value="">Выберите группу</option>' + options;
        updateCreateLessonGroupOptions();
        
        // Инициализируем кастомный searchable select
        initSearchableSelect('scheduleGroupFilter');
        initSearchableSelect('generateGroup');
        initSearchableSelect('templateGroup');
        initSearchableSelect('createLessonGroup');
        toggleCreateLessonFields();
    }

    function updateCreateLessonGroupOptions() {
        const groupSelect = document.getElementById("createLessonGroup");
        const courseSelect = document.getElementById("createLessonCourse");
        if (!groupSelect || !courseSelect) return;

        const courseId = Number(courseSelect.value || 0);
        const previousValue = groupSelect.value;
        const groups = courseId
            ? currentGroups.filter((group) => Number(group.course) === courseId)
            : [];

        groupSelect.disabled = !courseId;
        groupSelect.innerHTML = !courseId
            ? '<option value="">Сначала выберите курс</option>'
            : '<option value="">Выберите группу</option>' + groups.map((group) => `<option value="${group.id}">${escapeHtml(group.number)} · ${escapeHtml(group.teacher_name || '')}</option>`).join("");

        if (previousValue && groups.some((group) => String(group.id) === String(previousValue))) {
            groupSelect.value = previousValue;
        }
    }

    function updateCreateLessonStudentOptions() {
        const studentSelect = document.getElementById("createLessonStudent");
        const courseSelect = document.getElementById("createLessonCourse");
        if (!studentSelect || !courseSelect) return;

        const courseId = Number(courseSelect.value || 0);
        const previousValue = studentSelect.value;
        studentSelect.disabled = !courseId;
        studentSelect.innerHTML = !courseId
            ? '<option value="">Сначала выберите курс</option>'
            : '<option value="">Выберите ученика</option>' + currentStudents.map((student) => `<option value="${student.id}">${escapeHtml(student.first_name || '')} ${escapeHtml(student.last_name || '')}</option>`).join("");

        if (previousValue && currentStudents.some((student) => String(student.id) === String(previousValue))) {
            studentSelect.value = previousValue;
        }
    }

    function updateCreateLessonGroupStudentsOptions() {
        const select = document.getElementById("createLessonStudents");
        const courseSelect = document.getElementById("createLessonCourse");
        if (!select || !courseSelect) return;

        const courseId = Number(courseSelect.value || 0);
        const previousValues = new Set(Array.from(select.selectedOptions).map((option) => String(option.value)));
        select.disabled = !courseId;
        select.innerHTML = !courseId
            ? '<option value="">Сначала выберите курс</option>'
            : currentStudents.map((student) => `<option value="${student.id}">${escapeHtml(student.first_name || '')} ${escapeHtml(student.last_name || '')}</option>`).join("");

        Array.from(select.options).forEach((option) => {
            option.selected = previousValues.has(String(option.value));
        });
    }

    function getCreateLessonType() {
        return document.querySelector('input[name="createLessonType"]:checked')?.value || "regular";
    }

    function toggleCreateLessonFields() {
        const groupField = document.getElementById("createLessonGroupField");
        const studentField = document.getElementById("createLessonStudentField");
        const studentsField = document.getElementById("createLessonStudentsField");
        const groupSelect = document.getElementById("createLessonGroup");
        const studentSelect = document.getElementById("createLessonStudent");
        const studentsSelect = document.getElementById("createLessonStudents");
        const courseSelect = document.getElementById("createLessonCourse");
        const hint = document.getElementById("createLessonModeHint");

        const hasGroup = Boolean(groupSelect?.value);
        const hasStudent = Boolean(studentSelect?.value);
        if (groupField) groupField.hidden = false;
        if (studentField) studentField.hidden = hasGroup;
        if (studentsField) studentsField.hidden = !hasGroup;

        if (groupSelect) groupSelect.required = !hasStudent;
        if (studentSelect) studentSelect.required = !hasGroup;
        if (studentsSelect) studentsSelect.required = hasGroup;
        if (courseSelect) courseSelect.required = true;
        updateCreateLessonGroupOptions();
        updateCreateLessonStudentOptions();
        updateCreateLessonGroupStudentsOptions();

        if (hint) {
            const format = getCreateLessonType() === "single" ? "Разовое" : "Постоянное";
            const audience = hasGroup ? "групповое" : hasStudent ? "индивидуальное" : "групповое или индивидуальное";
            hint.textContent = `${format} ${audience} занятие`;
        }
    }

    function fillTeacherOptions() {
        const select = document.getElementById("createLessonTeacher");
        if (!select) return;
        select.innerHTML = '<option value="">Выберите преподавателя</option>' + currentTeachers.map((teacher) => `<option value="${teacher.id}">${escapeHtml(teacher.first_name || '')} ${escapeHtml(teacher.last_name || '')}</option>`).join("");
    }

    function fillStudentOptions() {
        updateCreateLessonStudentOptions();
        updateCreateLessonGroupStudentsOptions();
    }

    function fillCourseOptions() {
        const select = document.getElementById("createLessonCourse");
        if (!select) return;
        select.innerHTML = '<option value="">Выберите курс</option>' + currentCourses.map((course) => `<option value="${course.id}">${escapeHtml(course.name)}</option>`).join("");
        updateCreateLessonGroupOptions();
        updateCreateLessonStudentOptions();
        updateCreateLessonGroupStudentsOptions();
    }

    function loadTeachers() {
        fetch("/api/v1/schedule/teachers/", { headers })
            .then((response) => response.json())
            .then((data) => {
                currentTeachers = data;
                fillTeacherOptions();
            })
            .catch(() => {
                currentTeachers = [];
                fillTeacherOptions();
            });
    }

    function loadStudents() {
        const courseId = document.getElementById("createLessonCourse")?.value || "";
        const groupId = document.getElementById("createLessonGroup")?.value || "";
        const subscriptionType = groupId ? "group" : "individual";
        const groupParam = groupId ? `&group=${groupId}` : "";
        const url = courseId
            ? `/api/v1/schedule/students/?course=${courseId}&subscription_type=${subscriptionType}${groupParam}`
            : "/api/v1/schedule/students/";

        fetch(url, { headers })
            .then((response) => response.json())
            .then((data) => {
                currentStudents = data;
                fillStudentOptions();
            })
            .catch(() => {
                currentStudents = [];
                fillStudentOptions();
            });
    }

    function loadCourses() {
        fetch("/api/v1/courses/", { headers })
            .then((response) => response.json())
            .then((data) => {
                currentCourses = data;
                fillCourseOptions();
            })
            .catch(() => {
                currentCourses = [];
                fillCourseOptions();
            });
    }

    function initSearchableSelect(selectId) {
        const select = document.getElementById(selectId);
        if (!select || select.dataset.searchableInit) return;
        
        select.dataset.searchableInit = 'true';
        
        // Создаем wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'crm-searchable-select';
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);
        
        // Создаем кастомный display
        const display = document.createElement('div');
        display.className = 'crm-searchable-select__display';
        display.textContent = select.options[select.selectedIndex].text;
        wrapper.appendChild(display);
        
        // Создаем dropdown
        const dropdown = document.createElement('div');
        dropdown.className = 'crm-searchable-select__dropdown';
        
        // Поле поиска
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'crm-searchable-select__search';
        searchInput.placeholder = 'Поиск...';
        dropdown.appendChild(searchInput);
        
        // Список опций
        const optionsList = document.createElement('div');
        optionsList.className = 'crm-searchable-select__options';
        dropdown.appendChild(optionsList);
        
        wrapper.appendChild(dropdown);
        
        // Скрываем оригинальный select
        select.style.display = 'none';
        
        // Функция обновления списка опций
        function updateOptions(searchTerm = '') {
            optionsList.innerHTML = '';
            const term = searchTerm.toLowerCase();
            
            Array.from(select.options).forEach((option) => {
                if (!term || option.text.toLowerCase().includes(term)) {
                    const optionDiv = document.createElement('div');
                    optionDiv.className = 'crm-searchable-select__option';
                    if (option.value === select.value) {
                        optionDiv.classList.add('is-selected');
                    }
                    optionDiv.textContent = option.text;
                    optionDiv.dataset.value = option.value;
                    
                    optionDiv.addEventListener('click', () => {
                        select.value = option.value;
                        display.textContent = option.text;
                        wrapper.classList.remove('is-open');
                        searchInput.value = '';
                        updateOptions();
                        
                        // Триггерим change event
                        select.dispatchEvent(new Event('change'));
                    });
                    
                    optionsList.appendChild(optionDiv);
                }
            });
        }
        
        // Открытие/закрытие
        display.addEventListener('click', (e) => {
            e.stopPropagation();
            const wasOpen = wrapper.classList.contains('is-open');
            
            // Закрываем все другие
            document.querySelectorAll('.crm-searchable-select.is-open').forEach(el => {
                el.classList.remove('is-open');
            });
            
            if (!wasOpen) {
                wrapper.classList.add('is-open');
                searchInput.focus();
                updateOptions();
            }
        });
        
        // Поиск
        searchInput.addEventListener('input', (e) => {
            updateOptions(e.target.value);
        });
        
        // Закрытие при клике вне
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target)) {
                wrapper.classList.remove('is-open');
                searchInput.value = '';
            }
        });
        
        // Инициализация
        updateOptions();
    }

    function renderSchedule(lessons) {
        const target = document.getElementById("scheduleList");
        document.getElementById("scheduleCount").textContent = lessons.length;

        if (!lessons.length) {
            target.innerHTML = '<div class="crm-table-empty">Занятия не найдены. Сгенерируйте расписание или измените фильтры.</div>';
            return;
        }

        target.innerHTML = lessons.map((lesson) => {
            const displayStatus = lesson.actual_status || lesson.status;
            return `
            <article class="crm-lesson-card" onclick="openLessonDrawer(${lesson.id})">
                <div class="crm-lesson-card__top">
                    <div>
                        <h4 class="crm-lesson-card__title">${escapeHtml(lesson.group_name)}</h4>
                        <div class="crm-lesson-card__meta">${escapeHtml(lesson.course_name)} · ${escapeHtml(lesson.teacher_name)}</div>
                    </div>
                    <span class="crm-status-badge crm-status-badge--${displayStatus}">${statusLabel(displayStatus)}</span>
                </div>
                <div class="crm-lesson-card__time">
                    <span>${formatDateTime(lesson.classdateStart)}</span>
                    <span>до ${formatTime(lesson.classdateEnd)}</span>
                </div>
                ${lesson.cancel_reason ? `<div class="crm-table-meta">Причина отмены: ${escapeHtml(lesson.cancel_reason)}</div>` : ''}
                ${lesson.reschedule_reason ? `<div class="crm-table-meta">Причина переноса: ${escapeHtml(lesson.reschedule_reason)}</div>` : ''}
            </article>
        `;
        }).join("");
    }

    function renderTemplates(templates) {
        const target = document.getElementById("templateList");
        document.getElementById("templatesCount").textContent = templates.length;

        if (!templates.length) {
            target.innerHTML = '<div class="crm-table-empty">Шаблоны стандартного времени не настроены.</div>';
            return;
        }

        target.innerHTML = templates.map((template) => `
            <article class="crm-template-card" onclick="openTemplateDrawer(${template.id})">
                <div class="crm-template-card__top">
                    <div>
                        <h4 class="crm-template-card__title">${escapeHtml(template.group_name)}</h4>
                        <div class="crm-template-card__meta">${escapeHtml(template.weekday_display)} · ${escapeHtml(template.start_time)} · ${escapeHtml(template.lessons_count_display)}</div>
                    </div>
                    ${template.is_active ? '<span class="crm-status-badge crm-status-badge--active">Активен</span>' : '<span class="crm-status-badge crm-status-badge--archive">Архив</span>'}
                </div>
                <div class="crm-table-meta">${escapeHtml(template.teacher_name)}</div>
            </article>
        `).join("");
    }

    window.loadSchedule = function () {
        const params = new URLSearchParams();
        const dateFrom = document.getElementById("scheduleDateFrom").value;
        const dateTo = document.getElementById("scheduleDateTo").value;
        const group = document.getElementById("scheduleGroupFilter").value;
        const statusFilter = document.getElementById("scheduleStatusFilter").value;

        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        if (group) params.set("group", group);
        if (statusFilter) params.set("status", statusFilter);

        if (window.htmx) {
            htmx.ajax('GET', `/crm/schedule/lessons/?${params.toString()}`, {
                target: '#scheduleListHost',
                swap: 'outerHTML',
            });
            return;
        }

        fetch(`/api/v1/schedule/?${params.toString()}`, { headers })
            .then((response) => {
                if (!response.ok) throw new Error("Failed to load schedule");
                return response.json();
            })
            .then((data) => {
                currentLessons = data;
                renderSchedule(currentLessons);
            })
            .catch(() => {
                document.getElementById("scheduleList").innerHTML = '<div class="crm-table-empty">Не удалось загрузить расписание.</div>';
            });
    };

    function loadTemplates() {
        fetch("/api/v1/schedule/templates/", { headers })
            .then((response) => {
                if (!response.ok) throw new Error("Failed to load templates");
                return response.json();
            })
            .then((data) => {
                currentTemplates = data;
                renderTemplates(currentTemplates);
            })
            .catch(() => {
                document.getElementById("templateList").innerHTML = '<div class="crm-table-empty">Не удалось загрузить шаблоны.</div>';
            });
    }

    function loadGroups() {
        fetch("/api/v1/groups/my/?status=active", { headers })
            .then((response) => {
                if (!response.ok) throw new Error("Failed to load groups");
                return response.json();
            })
            .then((data) => {
                currentGroups = data;
                fillGroupOptions();
            });
    }

    function fillTemplateForm(template) {
        document.getElementById("templateGroup").value = template?.group || "";
        document.getElementById("templateWeekday").value = template?.weekday ?? "0";
        document.getElementById("templateStartTime").value = template?.start_time ? template.start_time.slice(0, 5) : "";
        document.getElementById("templateLessonsCount").value = template?.lessons_count || "2";
        document.getElementById("templateIsActive").checked = template ? Boolean(template.is_active) : true;
    }

    window.openTemplateDrawer = function (templateId) {
        selectedTemplateId = templateId || null;
        const template = selectedTemplateId ? currentTemplates.find((item) => item.id === selectedTemplateId) : null;
        document.getElementById("templateDrawerTitle").textContent = template ? "Редактировать стандартное время" : "Стандартное время группы";
        document.getElementById("templateSubmitBtn").textContent = template ? "Сохранить" : "Создать";
        setAlert("templateAlert", "");
        fillTemplateForm(template);
        document.getElementById("templateDrawer").classList.add("is-open");
    };

    window.closeTemplateDrawer = function () {
        document.getElementById("templateDrawer").classList.remove("is-open");
        selectedTemplateId = null;
        document.getElementById("templateForm").reset();
        setAlert("templateAlert", "");
    };

    function saveTemplate(event) {
        event.preventDefault();
        const payload = {
            group: Number(document.getElementById("templateGroup").value),
            weekday: Number(document.getElementById("templateWeekday").value),
            start_time: document.getElementById("templateStartTime").value,
            lessons_count: Number(document.getElementById("templateLessonsCount").value),
            is_active: document.getElementById("templateIsActive").checked,
        };
        const url = selectedTemplateId ? `/api/v1/schedule/templates/${selectedTemplateId}/` : "/api/v1/schedule/templates/create/";
        const method = selectedTemplateId ? "PATCH" : "POST";

        fetch(url, { method, headers: headersWithCsrf, body: JSON.stringify(payload) })
            .then((response) => {
                if (!response.ok) return response.json().then((data) => { throw new Error(data.error || "Не удалось сохранить шаблон"); });
                return response.json();
            })
            .then(() => {
                setAlert("templateAlert", "Шаблон сохранен", true);
                loadTemplates();
                setTimeout(closeTemplateDrawer, 500);
            })
            .catch((error) => setAlert("templateAlert", error.message, false));
    }

    window.openGenerateDrawer = function () {
        setAlert("generateAlert", "");
        
        // Устанавливаем даты каждый раз при открытии
        const today = new Date();
        const nextMonth = new Date();
        nextMonth.setDate(today.getDate() + 30);
        document.getElementById("generateDateFrom").value = toDateInput(today);
        document.getElementById("generateDateTo").value = toDateInput(nextMonth);
        
        document.getElementById("generateDrawer").classList.add("is-open");
    };

    window.openCreateLessonDrawer = function () {
        const drawer = document.getElementById("createLessonDrawer");
        if (!drawer) return;
        setAlert("createLessonAlert", "");
        const regularRadio = document.querySelector('input[name="createLessonType"][value="regular"]');
        if (regularRadio) regularRadio.checked = true;
        document.getElementById("createLessonCount").value = "2";
        document.getElementById("createLessonStart").value = "";
        document.getElementById("createLessonTeacher").value = "";
        document.getElementById("createLessonCourse").value = "";
        document.getElementById("createLessonGroup").value = "";
        document.getElementById("createLessonStudent").value = "";
        document.getElementById("createLessonStudents").innerHTML = "";
        toggleCreateLessonFields();
        drawer.classList.add("is-open");
    };

    window.closeCreateLessonDrawer = function () {
        const drawer = document.getElementById("createLessonDrawer");
        if (drawer) drawer.classList.remove("is-open");
    };

    function submitCreateLesson(event) {
        event.preventDefault();
        const type = getCreateLessonType();
        const groupId = document.getElementById("createLessonGroup").value;
        const studentId = document.getElementById("createLessonStudent").value;
        const selectedStudentIds = Array.from(document.getElementById("createLessonStudents").selectedOptions).map((option) => Number(option.value));

        if (!groupId && !studentId) {
            setAlert("createLessonAlert", "Выберите группу или ученика", false);
            return;
        }

        if (groupId && !selectedStudentIds.length) {
            setAlert("createLessonAlert", "Выберите учеников для группового занятия", false);
            return;
        }

        const payload = {
            lesson_type: type,
            classdateStart: document.getElementById("createLessonStart").value,
            lessons_count: Number(document.getElementById("createLessonCount").value),
            teacher: Number(document.getElementById("createLessonTeacher").value),
        };

        if (groupId) {
            payload.group = Number(groupId);
            payload.course = Number(document.getElementById("createLessonCourse").value);
            payload.students = selectedStudentIds;
        } else {
            payload.student = Number(studentId);
            payload.course = Number(document.getElementById("createLessonCourse").value);
        }

        fetch("/api/v1/schedule/create/", { method: "POST", headers: headersWithCsrf, body: JSON.stringify(payload) })
            .then((response) => {
                if (!response.ok) return response.json().then((data) => { throw new Error(data.error || "Не удалось создать занятие"); });
                return response.json();
            })
            .then(() => {
                setAlert("createLessonAlert", "Занятие создано", true);
                loadSchedule();
                setTimeout(closeCreateLessonDrawer, 600);
            })
            .catch((error) => setAlert("createLessonAlert", error.message, false));
    }

    window.closeGenerateDrawer = function () {
        document.getElementById("generateDrawer").classList.remove("is-open");
        
        // Сбрасываем форму
        document.getElementById("generateForm").reset();
        
        // Обновляем display для searchable select
        const generateGroupSelect = document.getElementById("generateGroup");
        const wrapper = generateGroupSelect.closest('.crm-searchable-select');
        if (wrapper) {
            const display = wrapper.querySelector('.crm-searchable-select__display');
            if (display) {
                display.textContent = generateGroupSelect.options[generateGroupSelect.selectedIndex].text;
            }
        }
        
        setAlert("generateAlert", "");
    };

    function generateSchedule(event) {
        event.preventDefault();
        const payload = {
            date_from: document.getElementById("generateDateFrom").value,
            date_to: document.getElementById("generateDateTo").value,
            group_id: document.getElementById("generateGroup").value || null,
        };

        fetch("/api/v1/schedule/generate/", { method: "POST", headers: headersWithCsrf, body: JSON.stringify(payload) })
            .then((response) => {
                if (!response.ok) return response.json().then((data) => { throw new Error(data.error || "Не удалось сгенерировать расписание"); });
                return response.json();
            })
            .then((data) => {
                setAlert("generateAlert", data.message, true);
                loadSchedule();
                setTimeout(closeGenerateDrawer, 700);
            })
            .catch((error) => setAlert("generateAlert", error.message, false));
    }

    window.openLessonDrawer = function (lessonId) {
        selectedLessonId = lessonId;
        const lesson = currentLessons.find((item) => item.id === lessonId);
        if (!lesson) return;
        document.getElementById("lessonDrawerTitle").textContent = `Занятие #${lesson.id}`;
        document.getElementById("lessonDrawerSubtitle").textContent = statusLabel(lesson.actual_status || lesson.status);
        document.getElementById("lessonGroup").textContent = lesson.group_name;
        document.getElementById("lessonType").textContent = lesson.lesson_type_display || lesson.lesson_type || "-";
        document.getElementById("lessonCourse").textContent = lesson.course_name || "-";
        document.getElementById("lessonStudent").textContent = lesson.student_name || "-";
        document.getElementById("lessonTeacher").textContent = lesson.teacher_name;
        document.getElementById("lessonStart").textContent = formatDateTime(lesson.classdateStart);
        document.getElementById("lessonEnd").textContent = formatTime(lesson.classdateEnd);
        document.getElementById("rescheduleStart").value = lesson.classdateStart.slice(0, 16);
        document.getElementById("rescheduleLessonType").value = lesson.lesson_type || "regular";
        document.getElementById("rescheduleReason").value = "";
        document.getElementById("cancelReason").value = lesson.cancel_reason || "";
        setAlert("lessonAlert", "");
        document.getElementById("lessonDrawer").classList.add("is-open");
        loadLessonAttendance(lessonId);
    };

    function renderLessonAttendance(students) {
        const target = document.getElementById("lessonAttendanceList");

        if (!students.length) {
            target.innerHTML = '<div class="crm-table-empty">В группе пока нет учеников</div>';
            return;
        }

        target.innerHTML = students.map((student) => {
            const attendance = student.attendance;
            const statusBadge = attendance
                ? `<span class="crm-status-badge crm-status-badge--${attendance.status === 'present' ? 'scheduled' : 'archive'}">${escapeHtml(attendance.status_display)}</span>`
                : '<span class="crm-status-badge crm-status-badge--archive">Не отмечен</span>';

            return `
                <div class="crm-attendance-item" data-student-id="${student.id}" data-attendance-id="${attendance ? attendance.id : ''}">
                    <div class="crm-attendance-item__top">
                        <div>
                            <div class="crm-attendance-item__name">${escapeHtml(student.name)}</div>
                            <div class="crm-table-meta">${escapeHtml(student.phone || '')}</div>
                        </div>
                        ${statusBadge}
                    </div>
                    <div class="crm-attendance-actions">
                        <select class="attendance-status" ${attendance ? 'disabled' : ''}>
                            <option value="present" ${attendance && attendance.status === 'present' ? 'selected' : ''}>Присутствовал</option>
                            <option value="absent" ${attendance && attendance.status === 'absent' ? 'selected' : ''}>Отсутствовал</option>
                            <option value="excused" ${attendance && attendance.status === 'excused' ? 'selected' : ''}>Уважительная причина</option>
                        </select>
                        <select class="attendance-lessons" ${attendance ? 'disabled' : ''}>
                            <option value="1" ${attendance && attendance.lessons_count === 1 ? 'selected' : ''}>1 занятие</option>
                            <option value="2" ${!attendance || attendance.lessons_count === 2 ? 'selected' : ''}>2 занятия</option>
                        </select>
                        ${attendance
                            ? `<button class="crm-btn crm-btn--secondary" type="button" onclick="cancelAttendance(${attendance.id})">Отменить отметку</button>`
                            : `<button class="crm-btn crm-btn--primary" type="button" onclick="markAttendance(${student.id})">Отметить</button>`
                        }
                    </div>
                    ${attendance && attendance.lesson_deducted ? `<div class="crm-table-meta">Списано занятий: ${attendance.lessons_count}</div>` : ''}
                </div>
            `;
        }).join("");
    }

    function loadLessonAttendance(lessonId) {
        document.getElementById("lessonAttendanceList").innerHTML = `
            <div class="crm-table-loading">
                <div class="crm-spinner"></div>
                <span>Загрузка учеников...</span>
            </div>
        `;

        fetch(`/api/v1/schedule/${lessonId}/attendance/`, { headers })
            .then((response) => {
                if (!response.ok) throw new Error("Failed to load lesson attendance");
                return response.json();
            })
            .then((data) => renderLessonAttendance(data.students || []))
            .catch(() => {
                document.getElementById("lessonAttendanceList").innerHTML = '<div class="crm-table-empty">Не удалось загрузить учеников занятия.</div>';
            });
    }

    window.markAttendance = function (studentId) {
        if (!selectedLessonId) return;
        const item = document.querySelector(`.crm-attendance-item[data-student-id="${studentId}"]`);
        if (!item) return;
        
        const statusValue = item.querySelector(".attendance-status").value;
        const lessonsValue = Number(item.querySelector(".attendance-lessons").value);

        fetch("/api/v1/subscriptions/attendance/mark/", {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify({
                schedule_id: selectedLessonId,
                student_id: studentId,
                status: statusValue,
                lessons_count: lessonsValue,
            }),
        })
            .then((response) => {
                if (!response.ok) return response.json().then((data) => { throw new Error(data.error || data.warning || "Не удалось отметить посещение"); });
                return response.json();
            })
            .then((data) => {
                setAlert("lessonAlert", data.message || data.warning || "Посещение отмечено", true);
                
                // Сохраняем текущие значения дропбоксов перед перезагрузкой
                const savedSelections = {};
                document.querySelectorAll('.crm-attendance-item').forEach(item => {
                    const sid = item.dataset.studentId;
                    const statusSelect = item.querySelector('.attendance-status');
                    const lessonsSelect = item.querySelector('.attendance-lessons');
                    if (statusSelect && lessonsSelect && !statusSelect.disabled) {
                        savedSelections[sid] = {
                            status: statusSelect.value,
                            lessons: lessonsSelect.value
                        };
                    }
                });
                
                // Перезагружаем список
                fetch(`/api/v1/schedule/${selectedLessonId}/attendance/`, { headers })
                    .then((response) => {
                        if (!response.ok) throw new Error("Failed to load lesson attendance");
                        return response.json();
                    })
                    .then((data) => {
                        renderLessonAttendance(data.students || []);
                        
                        // Восстанавливаем сохраненные значения для неотмеченных учеников
                        Object.entries(savedSelections).forEach(([sid, values]) => {
                            const restoredItem = document.querySelector(`.crm-attendance-item[data-student-id="${sid}"]`);
                            if (restoredItem) {
                                const statusSelect = restoredItem.querySelector('.attendance-status');
                                const lessonsSelect = restoredItem.querySelector('.attendance-lessons');
                                if (statusSelect && !statusSelect.disabled) {
                                    statusSelect.value = values.status;
                                }
                                if (lessonsSelect && !lessonsSelect.disabled) {
                                    lessonsSelect.value = values.lessons;
                                }
                            }
                        });
                    });
            })
            .catch((error) => setAlert("lessonAlert", error.message, false));
    };

    window.cancelAttendance = function (attendanceId) {
        if (!selectedLessonId) return;

        fetch(`/api/v1/subscriptions/attendance/${attendanceId}/cancel/`, {
            method: "DELETE",
            headers: headersWithCsrf,
        })
            .then((response) => {
                if (!response.ok) return response.json().then((data) => { throw new Error(data.error || "Не удалось отменить отметку"); });
                return response.json();
            })
            .then((data) => {
                setAlert("lessonAlert", data.message || "Отметка отменена", true);
                
                // Сохраняем текущие значения дропбоксов перед перезагрузкой
                const savedSelections = {};
                document.querySelectorAll('.crm-attendance-item').forEach(item => {
                    const sid = item.dataset.studentId;
                    const statusSelect = item.querySelector('.attendance-status');
                    const lessonsSelect = item.querySelector('.attendance-lessons');
                    if (statusSelect && lessonsSelect && !statusSelect.disabled) {
                        savedSelections[sid] = {
                            status: statusSelect.value,
                            lessons: lessonsSelect.value
                        };
                    }
                });
                
                // Перезагружаем список
                fetch(`/api/v1/schedule/${selectedLessonId}/attendance/`, { headers })
                    .then((response) => {
                        if (!response.ok) throw new Error("Failed to load lesson attendance");
                        return response.json();
                    })
                    .then((data) => {
                        renderLessonAttendance(data.students || []);
                        
                        // Восстанавливаем сохраненные значения для неотмеченных учеников
                        Object.entries(savedSelections).forEach(([sid, values]) => {
                            const restoredItem = document.querySelector(`.crm-attendance-item[data-student-id="${sid}"]`);
                            if (restoredItem) {
                                const statusSelect = restoredItem.querySelector('.attendance-status');
                                const lessonsSelect = restoredItem.querySelector('.attendance-lessons');
                                if (statusSelect && !statusSelect.disabled) {
                                    statusSelect.value = values.status;
                                }
                                if (lessonsSelect && !lessonsSelect.disabled) {
                                    lessonsSelect.value = values.lessons;
                                }
                            }
                        });
                    });
            })
            .catch((error) => setAlert("lessonAlert", error.message, false));
    };

    window.closeLessonDrawer = function () {
        document.getElementById("lessonDrawer").classList.remove("is-open");
        selectedLessonId = null;
        setAlert("lessonAlert", "");
    };

    window.cancelLesson = function () {
        if (!selectedLessonId) return;
        fetch(`/api/v1/schedule/${selectedLessonId}/cancel/`, {
            method: "PATCH",
            headers: headersWithCsrf,
            body: JSON.stringify({ reason: document.getElementById("cancelReason").value.trim() }),
        })
            .then((response) => {
                if (!response.ok) return response.json().then((data) => { throw new Error(data.error || "Не удалось отменить занятие"); });
                return response.json();
            })
            .then(() => {
                setAlert("lessonAlert", "Занятие отменено", true);
                loadSchedule();
                setTimeout(closeLessonDrawer, 500);
            })
            .catch((error) => setAlert("lessonAlert", error.message, false));
    };

    window.rescheduleLesson = function () {
        if (!selectedLessonId) return;
        fetch(`/api/v1/schedule/${selectedLessonId}/reschedule/`, {
            method: "PATCH",
            headers: headersWithCsrf,
            body: JSON.stringify({
                classdateStart: document.getElementById("rescheduleStart").value,
                lessons_count: Number(document.getElementById("rescheduleLessonsCount").value),
                lesson_type: document.getElementById("rescheduleLessonType").value,
                reason: document.getElementById("rescheduleReason").value.trim(),
            }),
        })
            .then((response) => {
                if (!response.ok) return response.json().then((data) => { throw new Error(data.error || "Не удалось перенести занятие"); });
                return response.json();
            })
            .then(() => {
                setAlert("lessonAlert", "Занятие перенесено", true);
                loadSchedule();
                setTimeout(closeLessonDrawer, 500);
            })
            .catch((error) => setAlert("lessonAlert", error.message, false));
    };

    document.addEventListener("DOMContentLoaded", () => {
        const today = new Date();
        const nextMonth = new Date();
        nextMonth.setDate(today.getDate() + 30);
        document.getElementById("scheduleDateFrom").value = toDateInput(today);
        document.getElementById("scheduleDateTo").value = toDateInput(nextMonth);
        document.getElementById("generateDateFrom").value = toDateInput(today);
        document.getElementById("generateDateTo").value = toDateInput(nextMonth);

        loadGroups();
        loadTeachers();
        loadStudents();
        loadCourses();
        if (!window.htmx) loadSchedule();
        if (!window.htmx) loadTemplates();

        document.getElementById("scheduleDateFrom").addEventListener("change", loadSchedule);
        document.getElementById("scheduleDateTo").addEventListener("change", loadSchedule);
        document.getElementById("scheduleGroupFilter").addEventListener("change", loadSchedule);
        document.getElementById("scheduleStatusFilter").addEventListener("change", loadSchedule);
        document.getElementById("templateForm")?.addEventListener("submit", saveTemplate);
        if (!window.htmx) document.getElementById("generateForm")?.addEventListener("submit", generateSchedule);
        if (!window.htmx) document.getElementById("createLessonForm")?.addEventListener("submit", submitCreateLesson);
        document.querySelectorAll('input[name="createLessonType"]').forEach((input) => input.addEventListener("change", toggleCreateLessonFields));
        document.getElementById("createLessonCourse")?.addEventListener("change", () => {
            updateCreateLessonGroupOptions();
            loadStudents();
        });
        document.getElementById("createLessonGroup")?.addEventListener("change", () => {
            loadStudents();
            const studentSelect = document.getElementById("createLessonStudent");
            if (document.getElementById("createLessonGroup").value && studentSelect) {
                studentSelect.value = "";
            }
            toggleCreateLessonFields();
        });
        document.getElementById("createLessonStudent")?.addEventListener("change", () => {
            const groupSelect = document.getElementById("createLessonGroup");
            if (document.getElementById("createLessonStudent").value && groupSelect) {
                groupSelect.value = "";
            }
            toggleCreateLessonFields();
        });
    });
})();
