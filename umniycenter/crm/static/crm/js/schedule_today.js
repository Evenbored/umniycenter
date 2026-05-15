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
        ...headers,
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
    };

    let todayLessons = [];
    let selectedLessonId = null;
    let selectedStudentId = null;
    let selectedDetailTab = "visits";
    let studentHistoryRenderToken = 0;
    let currentStudents = [];
    const currentStudentsById = new Map();
    const attendanceContextByLesson = new Map();
    const studentHistoryCache = new Map();

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

    function formatTime(value) {
        if (!value) return "-";
        if (typeof value === "string" && value.includes("T")) {
            return new Date(value).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
        }
        if (typeof value === "string" && value.includes(":")) {
            return value.slice(0, 5);
        }
        return value;
    }

    function formatTodayLabel() {
        return new Date().toLocaleDateString("ru-RU", {
            day: "numeric",
            month: "long",
            year: "numeric",
        });
    }

    function formatDate(value) {
        if (!value) return "—";
        return new Date(value).toLocaleDateString("ru-RU", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        });
    }

    function formatMoney(value) {
        return `${Number(value || 0).toLocaleString("ru-RU")} ₽`;
    }

    function getLessonDurationCount(lesson) {
        if (!lesson?.classdateStart || !lesson?.classdateEnd) return 2;

        const start = new Date(lesson.classdateStart);
        const [endHours, endMinutes] = String(lesson.classdateEnd).split(":").map(Number);
        const end = new Date(start);
        end.setHours(endHours || 0, endMinutes || 0, 0, 0);

        let durationMinutes = Math.round((end - start) / 60000);
        if (durationMinutes < 0) durationMinutes += 24 * 60;

        return durationMinutes <= 60 ? 1 : 2;
    }

    function statusLabel(status) {
        const labels = {
            scheduled: "Запланировано",
            completed: "Прошло",
            cancelled: "Отменено",
            rescheduled: "Перенесено",
        };
        return labels[status] || status;
    }

    function attendanceLabel(status) {
        const labels = {
            present: "Был",
            absent: "Отсутствовал",
            excused: "Уважительная причина",
        };
        return labels[status] || "Не отмечен";
    }

    function tabLabel(tab) {
        const labels = {
            visits: "Посещения",
            services: "Услуги",
            products: "Товары",
            enrollment: "Запись",
        };
        return labels[tab] || tab;
    }

    function showNotification(title, message, type = "info") {
        if (window.CRM && window.CRM.showNotification) {
            window.CRM.showNotification(title, message, type);
            return;
        }

        console[type === "error" ? "error" : "log"](`${title}: ${message}`);
    }

    function getAttendanceSummary(context) {
        const students = context?.students || [];
        const total = students.length;
        const present = students.filter((student) => student.attendance?.status === "present").length;
        const absent = students.filter((student) => ["absent", "excused"].includes(student.attendance?.status)).length;

        return { total, present, absent };
    }

    function getCurrentLesson() {
        return todayLessons.find((lesson) => Number(lesson.id) === Number(selectedLessonId));
    }

    function getStudentById(studentId) {
        return currentStudentsById.get(Number(studentId)) || null;
    }

    function getActiveStudent() {
        return currentStudentsById.get(Number(selectedStudentId)) || currentStudents[0] || null;
    }

    function updateLessonCardSummary(lessonId) {
        const card = document.querySelector(`.crm-today-lesson-card[data-lesson-id="${lessonId}"]`);
        const context = attendanceContextByLesson.get(Number(lessonId));
        if (!card || !context) return;

        const summary = getAttendanceSummary(context);
        card.querySelector("[data-total]").textContent = summary.total;
        const stats = card.querySelector(".crm-today-lesson-card__stats span");
        if (stats) {
            stats.textContent = `${summary.present} / ${summary.absent}`;
        }
    }

    async function loadStudentsDirectory() {
        try {
            const response = await fetch('/api/v1/students/my/', { headers });
            if (!response.ok) throw new Error('Failed to load students');

            currentStudents = await response.json();
            currentStudentsById.clear();
            currentStudents.forEach((student) => currentStudentsById.set(Number(student.student || student.id), student));
        } catch (error) {
            console.error('Error loading students directory:', error);
            currentStudents = [];
            currentStudentsById.clear();
        }
    }

    async function loadAttendanceContext(lessonId, force = false) {
        const normalizedId = Number(lessonId);
        if (!force && attendanceContextByLesson.has(normalizedId)) {
            return attendanceContextByLesson.get(normalizedId);
        }

        const response = await fetch(`${window.CRM_TODAY_SCHEDULE_CONFIG.scheduleApiUrl}${normalizedId}/attendance/`, {
            headers,
        });

        if (!response.ok) {
            throw new Error("Failed to load attendance context");
        }

        const data = await response.json();
        attendanceContextByLesson.set(normalizedId, data);
        updateLessonCardSummary(normalizedId);
        return data;
    }

    async function loadTodaySchedule() {
        const today = toDateInput(new Date());
        const list = document.getElementById("todayLessonsList");

        document.getElementById("todayDateLabel").textContent = formatTodayLabel();
        list.innerHTML = `
            <div class="crm-table-loading">
                <div class="crm-spinner"></div>
                <span>Загрузка занятий...</span>
            </div>
        `;

        try {
            const response = await fetch(`${window.CRM_TODAY_SCHEDULE_CONFIG.scheduleApiUrl}?date_from=${today}&date_to=${today}`, { headers });
            if (!response.ok) throw new Error("Failed to load schedule");

            todayLessons = await response.json();
            todayLessons.sort((a, b) => new Date(a.classdateStart) - new Date(b.classdateStart));
            attendanceContextByLesson.clear();
            renderTodayLessons();

            await Promise.allSettled(todayLessons.map((lesson) => loadAttendanceContext(lesson.id)));

            if (todayLessons.length && !selectedLessonId) {
                selectLesson(todayLessons[0].id);
            }
        } catch (error) {
            console.error("Error loading today's schedule:", error);
            list.innerHTML = '<div class="crm-table-empty">Не удалось загрузить сегодняшнее расписание</div>';
        }
    }

    function renderTodayLessons() {
        const list = document.getElementById("todayLessonsList");
        document.getElementById("todayLessonsCount").textContent = todayLessons.length;

        if (!todayLessons.length) {
            selectedLessonId = null;
            list.innerHTML = '<div class="crm-table-empty">На сегодня занятий нет</div>';
            document.getElementById("selectedLessonTitle").textContent = "Нет занятий";
            document.getElementById("selectedLessonMeta").textContent = "На выбранную дату расписание пустое";
            document.getElementById("todayAttendanceList").innerHTML = '<div class="crm-table-empty">Ученики не выбраны</div>';
            return;
        }

        list.innerHTML = todayLessons.map((lesson) => {
            const status = lesson.actual_status || lesson.status;
            const start = formatTime(lesson.classdateStart);
            const end = formatTime(lesson.classdateEnd);

            return `
                <article class="crm-today-lesson-card" data-lesson-id="${lesson.id}" onclick="selectTodayLesson(${lesson.id})">
                    <div class="crm-today-lesson-card__time">
                        <strong>${start}</strong>
                        <span>${end}</span>
                    </div>
                    <div class="crm-today-lesson-card__main">
                        <h4>${escapeHtml(lesson.group_name)}</h4>
                        <p>${escapeHtml(lesson.teacher_name)}</p>
                        <span class="crm-status-badge crm-status-badge--${status}">${statusLabel(status)}</span>
                    </div>
                    <div class="crm-today-lesson-card__stats">
                        <strong data-total>—</strong>
                        <span></span>
                    </div>
                </article>
            `;
        }).join("");
    }

    async function selectLesson(lessonId) {
        selectedLessonId = Number(lessonId);
        document.querySelectorAll(".crm-today-lesson-card").forEach((card) => {
            card.classList.toggle("is-active", Number(card.dataset.lessonId) === selectedLessonId);
        });

        const attendanceList = document.getElementById("todayAttendanceList");
        attendanceList.innerHTML = `
            <div class="crm-table-loading">
                <div class="crm-spinner"></div>
                <span>Загрузка учеников...</span>
            </div>
        `;

        try {
            const context = await loadAttendanceContext(selectedLessonId, true);
            renderSelectedLesson(context);
        } catch (error) {
            console.error("Error loading lesson attendance:", error);
            attendanceList.innerHTML = '<div class="crm-table-empty">Не удалось загрузить учеников занятия</div>';
        }
    }

    function renderSelectedLesson(context) {
        const lesson = context.lesson;
        const students = context.students || [];

        document.getElementById("selectedLessonTitle").textContent = lesson.group_name;
        document.getElementById("selectedLessonMeta").textContent = `${formatTime(lesson.classdateStart)} — ${formatTime(lesson.classdateEnd)} · ${lesson.teacher_name}`;

        const attendanceList = document.getElementById("todayAttendanceList");
        if (!students.length) {
            attendanceList.innerHTML = '<div class="crm-table-empty">В этой группе пока нет учеников</div>';
            renderEmptyStudentDetail();
            return;
        }

        attendanceList.innerHTML = students.map((student) => {
            const status = student.attendance?.status || "";
            const attendanceId = student.attendance?.id || "";

            return `
                <article class="crm-today-student-card" data-student-id="${student.id}" data-attendance-id="${attendanceId}" onclick="openTodayStudent(${student.id})">
                    <div class="crm-today-student-card__info">
                        <strong>${escapeHtml(student.name)}</strong>
                    </div>
                    <div class="crm-today-student-card__actions">
                        ${getLessonDurationCount(lesson) === 2 ? `
                            <button class="crm-attendance-toggle ${status === 'present' && student.attendance?.lessons_count === 1 ? 'is-active' : ''}" type="button" onclick="event.stopPropagation(); markTodayAttendance(${student.id}, 'present', 1)">Половина</button>
                            <button class="crm-attendance-toggle ${status === 'present' && student.attendance?.lessons_count === 2 ? 'is-active' : ''}" type="button" onclick="event.stopPropagation(); markTodayAttendance(${student.id}, 'present', 2)">Полный</button>
                        ` : `
                            <button class="crm-attendance-toggle ${status === 'present' ? 'is-active' : ''}" type="button" onclick="event.stopPropagation(); markTodayAttendance(${student.id}, 'present', 1)">Был</button>
                        `}
                        <button class="crm-attendance-toggle ${status === 'absent' ? 'is-active' : ''}" type="button" onclick="event.stopPropagation(); markTodayAttendance(${student.id}, 'absent', ${getLessonDurationCount(lesson) === 1 ? 1 : 2})">Не был</button>
                        <button class="crm-attendance-toggle ${status === 'excused' ? 'is-active' : ''}" type="button" onclick="event.stopPropagation(); markTodayAttendance(${student.id}, 'excused', 1)">Уважительная</button>
                    </div>
                </article>
            `;
        }).join("");

        const selectedStudent = students.find((student) => Number(student.id) === Number(selectedStudentId)) || students[0];
        if (selectedStudent) {
            openStudentDetail(selectedStudent.id);
        } else {
            renderEmptyStudentDetail();
        }
    }

    function renderEmptyStudentDetail() {
        const detail = document.getElementById("todayStudentDetail");
        document.getElementById("selectedStudentTitle").textContent = "Ученик";
        document.getElementById("selectedStudentMeta").textContent = "Нажмите на ученика в списке слева";
        detail.innerHTML = '<div class="crm-table-empty">Выберите ученика</div>';
    }

    async function loadStudentHistory(studentId) {
        const normalizedId = Number(studentId);
        if (studentHistoryCache.has(normalizedId)) {
            return studentHistoryCache.get(normalizedId);
        }

        const response = await fetch(`${window.CRM_TODAY_SCHEDULE_CONFIG.studentHistoryApiUrl}${normalizedId}/history/`, { headers });
        if (!response.ok) {
            throw new Error("Не удалось загрузить историю ученика");
        }

        const data = await response.json();
        studentHistoryCache.set(normalizedId, data);
        return data;
    }

    function renderHistoryLoading() {
        return `
            <div class="crm-table-loading">
                <div class="crm-spinner"></div>
                <span>Загрузка истории...</span>
            </div>
        `;
    }

    function renderVisitsTab(history) {
        const visits = history?.visits || [];
        if (!visits.length) {
            return '<div class="crm-table-empty">За весь период посещений нет</div>';
        }

        return `
            <div class="crm-history-list">
                ${visits.map((visit) => `
                    <div class="crm-history-item">
                        <div>
                            <strong>${escapeHtml(visit.schedule_info?.group || 'Занятие')}</strong>
                            <span>${formatDate(visit.schedule_info?.date)} · ${escapeHtml(visit.schedule_info?.course || '')}</span>
                        </div>
                        <span class="crm-status-badge crm-status-badge--${visit.status === 'present' ? 'scheduled' : 'cancelled'}">${escapeHtml(attendanceLabel(visit.status))}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function renderServicesTab(history) {
        const services = history?.services || [];
        if (!services.length) {
            return '<div class="crm-table-empty">За весь период услуг нет</div>';
        }

        return `
            <div class="crm-history-list">
                ${services.map((service) => `
                    <div class="crm-history-item">
                        <div>
                            <strong>${escapeHtml(service.tariff_name || 'Абонемент')}</strong>
                            <span>${escapeHtml(service.course_name || '')} · ${formatDate(service.start_date)} — ${formatDate(service.end_date)}</span>
                        </div>
                        <div class="crm-history-item__value">${service.lessons_remaining}/${service.lessons_total}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function renderProductsTab(history) {
        const products = history?.products || [];
        if (!products.length) {
            return '<div class="crm-table-empty">За весь период товаров и оплат нет</div>';
        }

        return `
            <div class="crm-history-list">
                ${products.map((payment) => `
                    <div class="crm-history-item">
                        <div>
                            <strong>${escapeHtml(payment.subscription_info?.tariff_name || `Платеж #${payment.id}`)}</strong>
                            <span>${formatDate(payment.created_at)} · ${escapeHtml(payment.payment_method_display || payment.payment_method || '')}</span>
                        </div>
                        <div class="crm-history-item__value">${formatMoney(payment.amount)}</div>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function renderEnrollmentTab(history) {
        const enrollment = history?.enrollment || [];
        if (!enrollment.length) {
            return '<div class="crm-table-empty">За весь период записей/заявок нет</div>';
        }

        return `
            <div class="crm-history-list">
                ${enrollment.map((item) => `
                    <div class="crm-history-item">
                        <div>
                            <strong>${escapeHtml(item.child_fio || history.student?.name || 'Заявка')}</strong>
                            <span>${formatDate(item.created)} · ${escapeHtml((item.courses || []).join(', ') || 'Курс не указан')}</span>
                        </div>
                        <span class="crm-status-badge crm-status-badge--${item.checked ? 'scheduled' : 'archive'}">${item.checked ? 'Обработана' : 'Новая'}</span>
                    </div>
                `).join('')}
            </div>
        `;
    }

    function renderStudentTabContent(history) {
        const content = document.getElementById("todayStudentTabContent");
        if (!content) return;

        const renderers = {
            visits: renderVisitsTab,
            services: renderServicesTab,
            products: renderProductsTab,
            enrollment: renderEnrollmentTab,
        };

        content.innerHTML = (renderers[selectedDetailTab] || renderVisitsTab)(history);
    }

    function openStudentDetail(studentId) {
        const context = attendanceContextByLesson.get(selectedLessonId);
        const student = context?.students?.find((item) => Number(item.id) === Number(studentId));
        if (!student) return;

        selectedStudentId = Number(studentId);
        selectedDetailTab = selectedDetailTab || "visits";

        document.querySelectorAll(".crm-today-student-card").forEach((card) => {
            card.classList.toggle("is-selected", Number(card.dataset.studentId) === Number(studentId));
        });

        const fullStudent = getStudentById(studentId) || {};
        document.getElementById("selectedStudentTitle").textContent = fullStudent.student_full_name || student.name;
        document.getElementById("selectedStudentMeta").textContent = fullStudent.student_phone || student.phone || "История за весь период";

        const detail = document.getElementById("todayStudentDetail");
        const activeSubscription = (fullStudent.subscriptions || [])[0] || null;
        const daysRemaining = activeSubscription?.end_date
            ? Math.max(0, Math.ceil((new Date(activeSubscription.end_date) - new Date()) / (1000 * 60 * 60 * 24)))
            : null;

        detail.innerHTML = `
            <div class="crm-student-detail-card">
                <div class="crm-student-detail-card__header">
                    <div>
                        <h4 class="crm-student-detail-card__name">${escapeHtml(fullStudent.student_full_name || student.name)}</h4>
                        <div class="crm-student-detail-card__meta">${escapeHtml(fullStudent.student_phone || '')}</div>
                    </div>
                    <span class="crm-status-badge crm-status-badge--${fullStudent.student_is_active ? 'scheduled' : 'cancelled'}">${fullStudent.student_is_active ? 'Активен' : 'Архив'}</span>
                </div>

                <div class="crm-student-detail-info">
                    <div class="crm-student-detail-info__row"><span>Абонемент</span><strong>${activeSubscription ? escapeHtml(activeSubscription.tariff_name) : 'Нет активного абонемента'}</strong></div>
                    <div class="crm-student-detail-info__row"><span>Осталось занятий</span><strong>${activeSubscription ? activeSubscription.lessons_remaining : '—'}</strong></div>
                    <div class="crm-student-detail-info__row"><span>Всего занятий</span><strong>${activeSubscription ? activeSubscription.lessons_total : '—'}</strong></div>
                    <div class="crm-student-detail-info__row"><span>Осталось дней</span><strong>${daysRemaining ?? '—'}</strong></div>
                </div>

            </div>

            <div class="crm-student-tabs">
                <div class="crm-student-tabs__nav">
                    ${['visits', 'services', 'products', 'enrollment'].map((tab) => `
                        <button type="button" class="crm-student-tabs__tab ${selectedDetailTab === tab ? 'is-active' : ''}" onclick="switchTodayStudentTab('${tab}')">${tabLabel(tab)}</button>
                    `).join('')}
                </div>
                <div class="crm-student-tabs__content" id="todayStudentTabContent">
                    ${renderHistoryLoading()}
                </div>
            </div>
        `;

        const historyStudentId = Number(student.id);
        const renderToken = ++studentHistoryRenderToken;

        loadStudentHistory(historyStudentId)
            .then((history) => {
                if (renderToken !== studentHistoryRenderToken || Number(selectedStudentId) !== historyStudentId) return;
                renderStudentTabContent(history);
            })
            .catch((error) => {
                console.error("Error loading student history:", error);
                const content = document.getElementById("todayStudentTabContent");
                if (content) content.innerHTML = '<div class="crm-table-empty">Не удалось загрузить историю ученика</div>';
            });
    }

    function switchTodayStudentTab(tab) {
        selectedDetailTab = tab;
        if (selectedStudentId) {
            openStudentDetail(selectedStudentId);
        }
    }

    async function cancelExistingAttendance(attendanceId) {
        if (!attendanceId) return;

        const response = await fetch(`${window.CRM_TODAY_SCHEDULE_CONFIG.cancelAttendanceApiUrl}${attendanceId}/cancel/`, {
            method: "DELETE",
            headers: headersWithCsrf,
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || "Не удалось изменить отметку");
        }
    }

    async function markAttendance(studentId, status, lessonsCount = 2) {
        if (!selectedLessonId) return;

        const context = attendanceContextByLesson.get(selectedLessonId);
        const student = context?.students?.find((item) => Number(item.id) === Number(studentId));
        const existingAttendanceId = student?.attendance?.id;
        const lessonDuration = Number(context?.lesson?.lessons_count || 2);
        const actualLessonsCount = lessonDuration === 1 ? 1 : Number(lessonsCount || 2);

        if (lessonDuration === 1 && actualLessonsCount !== 1) {
            showNotification("Ошибка", "Для урока длительностью 45 минут можно выбрать только полное посещение", "error");
            return;
        }

        try {
            if (existingAttendanceId) {
                await cancelExistingAttendance(existingAttendanceId);
            }

            const response = await fetch(window.CRM_TODAY_SCHEDULE_CONFIG.attendanceApiUrl, {
                method: "POST",
                headers: headersWithCsrf,
                body: JSON.stringify({
                    schedule_id: selectedLessonId,
                    student_id: studentId,
                    status,
                    lessons_count: actualLessonsCount,
                }),
            });

            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.error || "Не удалось отметить посещаемость");
            }

            const updatedContext = await loadAttendanceContext(selectedLessonId, true);
            studentHistoryCache.delete(Number(studentId));
            renderSelectedLesson(updatedContext);
            openStudentDetail(studentId);
            showNotification("Посещаемость", "Отметка сохранена", "success");
        } catch (error) {
            console.error("Error marking attendance:", error);
            showNotification("Ошибка", error.message || "Не удалось отметить посещаемость", "error");
            const restoredContext = await loadAttendanceContext(selectedLessonId, true).catch(() => null);
            if (restoredContext) renderSelectedLesson(restoredContext);
        }
    }

    window.selectTodayLesson = selectLesson;
    window.openTodayStudent = openStudentDetail;
    window.switchTodayStudentTab = switchTodayStudentTab;
    window.markTodayAttendance = markAttendance;
    window.refreshTodaySchedule = loadTodaySchedule;

    document.addEventListener("DOMContentLoaded", async () => {
        await loadStudentsDirectory();
        await loadTodaySchedule();
    });
})();
