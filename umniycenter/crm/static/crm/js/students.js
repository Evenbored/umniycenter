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

    let currentStudents = [];
    let currentGroups = [];
    let currentCourses = [];
    let currentTariffs = [];
    let selectedStudentId = null;
    const phonePattern = /^\+7\d{10}$/;
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
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

    function getInitials(name) {
        const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
        return (parts[0]?.[0] || "У") + (parts[1]?.[0] || "");
    }

    function getStatusBadge(isActive) {
        if (isActive) {
            return '<span class="crm-status-badge crm-status-badge--active">Активный</span>';
        }

        return '<span class="crm-status-badge crm-status-badge--archive">Архивный</span>';
    }

    function getGroupsHtml(groups, limit) {
        const visibleGroups = groups.slice(0, limit || groups.length);
        const hiddenCount = groups.length - visibleGroups.length;
        const chips = visibleGroups.map((group) => (
            `<span class="crm-group-chip">${escapeHtml(group.course_name)} · ${escapeHtml(group.group_number)}</span>`
        ));

        if (hiddenCount > 0) {
            chips.push(`<span class="crm-group-chip">+${hiddenCount}</span>`);
        }

        return chips.join("") || '<span class="crm-table-meta">Без группы</span>';
    }

    function updateSidebarCount(students) {
        document.querySelectorAll('[data-nav-count="students"]').forEach((item) => {
            item.textContent = students.length;
        });
    }

    function setStudentGroupsAlert(message, isSuccess) {
        const alert = document.getElementById("studentGroupsAlert");
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function setStudentEditAlert(message, isSuccess) {
        const alert = document.getElementById("studentEditAlert");
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function setCreateStudentAlert(message, isSuccess) {
        const alert = document.getElementById("createStudentAlert");
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function getErrorMessage(data) {
        if (data.error) {
            return data.error;
        }

        const messages = [];
        Object.keys(data).forEach((field) => {
            const value = data[field];
            messages.push(Array.isArray(value) ? value.join(" ") : String(value));
        });

        return messages.join(" ") || "Не удалось сохранить ученика";
    }

    function validateOptionalContacts(items) {
        for (const item of items) {
            if (item.phone && !phonePattern.test(item.phone)) {
                return `${item.label}: телефон должен быть в формате +7XXXXXXXXXX`;
            }

            if (item.email && !emailPattern.test(item.email)) {
                return `${item.label}: введите корректный email`;
            }
        }

        return "";
    }

    function updateStudentInState(updatedStudent) {
        const index = currentStudents.findIndex((student) => student.student === updatedStudent.student);

        if (index !== -1) {
            currentStudents[index] = updatedStudent;
        }
    }

    function getStudentById(studentId) {
        return currentStudents.find((item) => item.student === studentId);
    }

    function on(elementId, eventName, handler) {
        const element = document.getElementById(elementId);
        if (element) {
            element.addEventListener(eventName, handler);
        }
    }

    function jsonOrError(response) {
        return response.text().then((text) => {
            const data = text ? JSON.parse(text) : {};
            return { ok: response.ok, data };
        }).catch(() => ({
            ok: false,
            data: { error: "Сервер вернул некорректный ответ" },
        }));
    }

    function setStudentEditMode(isEditing) {
        document.getElementById("studentEditForm").hidden = !isEditing;
        document.getElementById("studentEditCancelBtn").hidden = !isEditing;
        document.getElementById("studentEditSaveBtn").hidden = !isEditing;
        document.getElementById("studentEditToggleBtn").hidden = isEditing;

        if (!isEditing) {
            setStudentEditAlert("");
        }
    }

    function fillStudentEditForm(student) {
        const details = student.student_details || {};
        const parents = student.parents || [];
        
        document.getElementById("studentEditLastName").value = details.last_name || "";
        document.getElementById("studentEditFirstName").value = details.first_name || "";
        document.getElementById("studentEditUsername").value = details.username || "";
        document.getElementById("studentEditPhone").value = student.student_phone || "";
        document.getElementById("studentEditEmail").value = student.student_email || "";
        document.getElementById("studentEditCity").value = student.student_city || "";
        document.getElementById("studentEditCountry").value = student.student_country || details.country || "";
        document.getElementById("studentEditSex").value = String(Number(Boolean(details.sex)));
        document.getElementById("studentEditIsActive").value = student.student_is_active ? "true" : "false";
        document.getElementById("studentEditSource").value = student.source || "";
        
        renderEditParentsList(parents);
    }

    function renderEditParentsList(parents) {
        const container = document.getElementById("studentEditParentsList");
        
        if (!parents || parents.length === 0) {
            container.innerHTML = '<p style="color: var(--crm-muted); font-size: 13px;">У ученика нет привязанных родителей</p>';
            updateAddParentButton();
            return;
        }
        
        container.innerHTML = parents.map((parent, index) => getParentEditCardHtml(parent, index)).join("");
        updateAddParentButton();
    }

    function getParentEditCardHtml(parent, index) {
        return `
            <div class="crm-parent-edit-card" data-parent-id="${escapeHtml(parent.id || '')}">
                <h5 style="margin: 0 0 12px; font-size: 14px;">Родитель ${index + 1}: ${escapeHtml(parent.full_name || 'Новый родитель')}</h5>
                <div class="crm-form-grid">
                    <label class="crm-form-field">
                        <span>Фамилия</span>
                        <input class="parent-last-name" type="text" value="${escapeHtml(parent.last_name || '')}" required>
                    </label>
                    <label class="crm-form-field">
                        <span>Имя</span>
                        <input class="parent-first-name" type="text" value="${escapeHtml(parent.first_name || '')}" required>
                    </label>
                    <label class="crm-form-field">
                        <span>Телефон</span>
                        <input class="parent-phone" type="tel" value="${escapeHtml(parent.phone || '')}">
                    </label>
                    <label class="crm-form-field">
                        <span>Email</span>
                        <input class="parent-email" type="email" value="${escapeHtml(parent.email || '')}">
                    </label>
                </div>
            </div>
        `;
    }

    function updateAddParentButton() {
        const button = document.getElementById("studentAddParentBtn");
        if (!button) {
            return;
        }

        const count = document.querySelectorAll("#studentEditParentsList .crm-parent-edit-card").length;
        button.hidden = count >= 2;
    }

    window.addEditParentCard = function () {
        const container = document.getElementById("studentEditParentsList");
        const count = container.querySelectorAll(".crm-parent-edit-card").length;

        if (count >= 2) {
            setStudentEditAlert("У ученика может быть не больше двух родителей", false);
            return;
        }

        if (count === 0) {
            container.innerHTML = "";
        }

        container.insertAdjacentHTML("beforeend", getParentEditCardHtml({}, count));
        updateAddParentButton();
    }

    function renderParentsList(parents) {
        const container = document.getElementById("studentDrawerParents");
        
        if (!parents || parents.length === 0) {
            container.innerHTML = '<p style="color: var(--crm-muted); font-size: 13px;">У ученика нет привязанных родителей</p>';
            return;
        }
        
        container.innerHTML = parents.map((parent, index) => `
            <div class="crm-parent-card">
                <div class="crm-parent-card__header">
                    <strong>Родитель ${index + 1}</strong>
                    <span>${escapeHtml(parent.full_name)}</span>
                </div>
                <div class="crm-info-grid" style="margin-top: 8px;">
                    <div class="crm-info-item">
                        <span class="crm-info-label">Телефон</span>
                        <strong>${escapeHtml(parent.phone || '-')}</strong>
                    </div>
                    <div class="crm-info-item">
                        <span class="crm-info-label">Email</span>
                        <strong>${escapeHtml(parent.email || '-')}</strong>
                    </div>
                </div>
            </div>
        `).join("");
    }

    function renderSubscriptionsList(subscriptions) {
        const container = document.getElementById("studentDrawerSubscriptions");
        
        if (!subscriptions || subscriptions.length === 0) {
            container.innerHTML = '<p style="color: var(--crm-muted); font-size: 13px;">У ученика нет активных подписок</p>';
            return;
        }
        
        container.innerHTML = subscriptions.map((sub) => {
            const progress = (sub.lessons_used / sub.lessons_total) * 100;
            const isExpiringSoon = new Date(sub.end_date) - new Date() < 7 * 24 * 60 * 60 * 1000;
            
            return `
                <div class="crm-subscription-card">
                    <div class="crm-subscription-card__header">
                        <div>
                            <div class="crm-subscription-card__title">${escapeHtml(sub.tariff_name)}</div>
                            <div class="crm-subscription-card__course">${escapeHtml(sub.course_name)}</div>
                        </div>
                        <span class="crm-status-badge crm-status-badge--${sub.is_valid ? 'active' : 'archive'}">
                            ${sub.is_valid ? 'Активна' : 'Неактивна'}
                        </span>
                    </div>
                    <div class="crm-subscription-card__progress">
                        <div class="crm-subscription-progress-bar">
                            <div class="crm-subscription-progress-bar__fill" style="width: ${progress}%"></div>
                        </div>
                        <div class="crm-subscription-progress-text">
                            Использовано: ${sub.lessons_used} из ${sub.lessons_total} занятий 
                            (осталось: <strong>${sub.lessons_remaining}</strong>)
                        </div>
                    </div>
                    <div class="crm-subscription-card__dates">
                        <span>Начало: ${formatDate(sub.start_date)}</span>
                        <span ${isExpiringSoon ? 'style="color: var(--crm-red); font-weight: 600;"' : ''}>
                            Окончание: ${formatDate(sub.end_date)}
                        </span>
                    </div>
                </div>
            `;
        }).join("");
    }

    function renderStudentGroups(student) {
        const target = document.getElementById("studentDrawerGroups");
        const groups = student.groups || [];

        if (!groups.length) {
            target.innerHTML = '<div class="crm-table-empty">Ученик пока не состоит в группах</div>';
        } else {
            target.innerHTML = groups.map((group) => `
                <div class="crm-student-group-item">
                    <div class="crm-student-group-item__info">
                        <strong>${escapeHtml(group.group_name)}</strong>
                        <span>${escapeHtml(group.course_name)} • ${escapeHtml(group.teacher_name)}</span>
                    </div>
                    <button class="crm-icon-btn" type="button" onclick="removeStudentFromGroup(${group.membership_id})" title="Удалить из группы">
                        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                            <path d="M18 6L6 18M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
            `).join("");
        }

        // Обновляем список доступных групп с учетом подписок
        updateAvailableGroups(student);
    }

    function updateAvailableGroups(student) {
        const select = document.getElementById("studentAddGroupSelect");
        const subscriptions = student.subscriptions || [];
        
        // Получаем ID курсов, на которые есть активные подписки
        const subscribedCourseIds = subscriptions
            .filter(sub => sub.is_valid)
            .map(sub => {
                // Находим курс по названию
                const course = currentCourses.find(c => c.name === sub.course_name);
                return course ? course.id : null;
            })
            .filter(id => id !== null);
        
        // Получаем ID групп, в которых уже состоит ученик
        const currentGroupIds = (student.groups || []).map(g => g.group);
        
        // Фильтруем группы
        let availableGroups = currentGroups.filter((group) => {
            // Не показываем группы, в которых уже состоит
            if (currentGroupIds.includes(group.id)) {
                return false;
            }
            
            // Если есть подписки, показываем только группы с соответствующими курсами
            if (subscribedCourseIds.length > 0) {
                return subscribedCourseIds.includes(group.course);
            }
            
            // Если нет подписок, показываем все группы
            return true;
        });
        
        if (availableGroups.length === 0) {
            select.innerHTML = '<option value="">Нет доступных групп</option>';
            select.disabled = true;
        } else {
            select.innerHTML = '<option value="">Выберите группу</option>' +
                availableGroups.map((group) => {
                    const courseName = currentCourses.find(c => c.id === group.course)?.name || '';
                    const hasSubscription = subscribedCourseIds.includes(group.course);
                    const badge = hasSubscription ? ' ✓' : '';
                    return `<option value="${group.id}">${escapeHtml(group.number)} - ${escapeHtml(courseName)}${badge}</option>`;
                }).join("");
            select.disabled = false;
        }
        
        // Показываем подсказку о подписках
        updateGroupSelectHint(subscribedCourseIds.length > 0, subscriptions);
    }

    function updateGroupSelectHint(hasSubscriptions, subscriptions) {
        const form = document.getElementById("studentAddGroupForm");
        let hint = form.querySelector('.crm-subscription-hint');
        
        if (!hint) {
            hint = document.createElement('div');
            hint.className = 'crm-subscription-hint';
            form.insertBefore(hint, form.firstChild);
        }
        
        if (hasSubscriptions) {
            const subsList = subscriptions
                .filter(sub => sub.is_valid)
                .map(sub => `${sub.course_name} (${sub.lessons_remaining} занятий)`)
                .join(', ');
            
            hint.innerHTML = `<svg width="14" height="14" fill="currentColor" viewBox="0 0 16 16" style="vertical-align: middle;">
                <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
                <path d="m8.93 6.588-2.29.287-.082.38.45.083c.294.07.352.176.288.469l-.738 3.468c-.194.897.105 1.319.808 1.319.545 0 1.178-.252 1.465-.598l.088-.416c-.2.176-.492.246-.686.246-.275 0-.375-.193-.304-.533L8.93 6.588zM9 4.5a1 1 0 1 1-2 0 1 1 0 0 1 2 0z"/>
            </svg> Активные подписки: ${subsList}. Группы с ✓ соответствуют подпискам.`;
            hint.style.display = 'block';
        } else {
            hint.innerHTML = `<svg width="14" height="14" fill="currentColor" viewBox="0 0 16 16" style="vertical-align: middle;">
                <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
            </svg> У ученика нет активных подписок. Рекомендуется сначала купить тариф.`;
            hint.style.display = 'block';
            hint.style.color = 'var(--crm-orange)';
        }
    }

    function renderAvailableGroups(student) {
        const select = document.getElementById("studentAddGroupSelect");
        const assignedGroupIds = new Set((student.groups || []).map((group) => Number(group.group)));
        const availableGroups = currentGroups.filter((group) => group.is_active && !assignedGroupIds.has(Number(group.id)));

        select.innerHTML = '<option value="">Выберите группу</option>' + availableGroups.map((group) => (
            `<option value="${group.id}">${escapeHtml(group.course_name)} · ${escapeHtml(group.number)} · ${escapeHtml(group.teacher_name || "Без преподавателя")}</option>`
        )).join("");
    }

    function renderStudents(students) {
        const tbody = document.getElementById("studentsTableBody");
        document.getElementById("studentsCount").textContent = students.length;
        updateSidebarCount(students);

        if (!students.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="crm-table-empty">Ученики не найдены. Попробуйте изменить фильтры.</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = students.map((student) => `
            <tr onclick="openStudentDetailsDrawer(${student.student})">
                <td>
                    <div class="crm-table-name">${escapeHtml(student.student_full_name)}</div>
                    <span class="crm-table-meta">${escapeHtml(student.student_details?.username || '')}</span>
                </td>
                <td>
                    <div>${escapeHtml(student.student_phone || '-')}</div>
                    ${student.student_email ? `<span class="crm-table-meta">${escapeHtml(student.student_email)}</span>` : ''}
                </td>
                <td>${escapeHtml(student.student_city || '-')}</td>
                <td>${getGroupsHtml(student.groups || [], 2)}</td>
                <td>${formatDate(student.student_date_joined)}</td>
                <td>${getStatusBadge(student.student_is_active)}</td>
                <td>
                    <button class="crm-table-action-btn" type="button" onclick="event.stopPropagation(); openStudentDetailsDrawer(${student.student})" title="Открыть карточку">
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
        const search = document.getElementById("studentsSearch").value.trim().toLowerCase();
        const courseId = document.getElementById("studentsCourseFilter").value;
        const groupId = document.getElementById("studentsGroupFilter").value;
        const status = document.getElementById("studentsStatusFilter").value;
        const withoutGroup = document.getElementById("studentsWithoutGroupFilter").checked;
        const sort = document.getElementById("studentsSortFilter").value;

        let filtered = [...currentStudents];

        if (search) {
            filtered = filtered.filter((student) => {
                const haystack = [
                    student.student_full_name,
                    student.student_phone,
                    student.student_email,
                    student.student_city,
                    student.student_details?.username,
                    ...(student.groups || []).map((group) => `${group.course_name} ${group.group_number}`),
                ].join(" ").toLowerCase();

                return haystack.includes(search);
            });
        }

        if (withoutGroup) {
            filtered = filtered.filter((student) => !student.groups || student.groups.length === 0);
        }

        if (courseId) {
            filtered = filtered.filter((student) => (
                (student.groups || []).some((group) => String(group.course) === courseId)
            ));
        }

        if (groupId) {
            filtered = filtered.filter((student) => (
                (student.groups || []).some((group) => String(group.group) === groupId)
            ));
        }

        if (status === "active") {
            filtered = filtered.filter((student) => student.student_is_active);
        } else if (status === "archive") {
            filtered = filtered.filter((student) => !student.student_is_active);
        }

        filtered.sort((a, b) => {
            if (sort === "name_za") {
                return b.student_full_name.localeCompare(a.student_full_name);
            }

            if (sort === "date_new") {
                return new Date(b.student_date_joined) - new Date(a.student_date_joined);
            }

            if (sort === "date_old") {
                return new Date(a.student_date_joined) - new Date(b.student_date_joined);
            }

            return a.student_full_name.localeCompare(b.student_full_name);
        });

        renderStudents(filtered);
    }

    function renderGroupFilter(groups) {
        const select = document.getElementById("studentsGroupFilter");
        select.innerHTML = '<option value="">Все группы</option>' + groups.map((group) => (
            `<option value="${group.id}">${escapeHtml(group.course_name)} · ${escapeHtml(group.number)}</option>`
        )).join("");
    }

    function renderCourseFilter(courses) {
        const select = document.getElementById("studentsCourseFilter");
        select.innerHTML = '<option value="">Все курсы</option>' + courses.map((course) => (
            `<option value="${course.id}">${escapeHtml(course.name)}</option>`
        )).join("");
    }

    function loadStudents() {
        const tbody = document.getElementById("studentsTableBody");
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="crm-table-loading">
                    <div class="crm-spinner"></div>
                    <span>Загрузка учеников...</span>
                </td>
            </tr>
        `;

        fetch("/api/v1/students/my/?status=", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load students");
                }
                return response.json();
            })
            .then((data) => {
                currentStudents = data;
                applyFilters();
            })
            .catch(() => {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="crm-table-empty">Не удалось загрузить учеников. Попробуйте обновить страницу.</td>
                    </tr>
                `;
            });
    }

    function loadGroups() {
        fetch("/api/v1/groups/my/?status=", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load groups");
                }
                return response.json();
            })
            .then((data) => {
                currentGroups = data;
                renderGroupFilter(currentGroups);
            })
            .catch(() => {
                currentGroups = [];
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
            })
            .catch(() => {
                currentCourses = [];
            });
    }

    window.openStudentDetailsDrawer = function (studentId) {
        const student = getStudentById(studentId);

        if (!student) {
            return;
        }

        selectedStudentId = studentId;
        setStudentGroupsAlert("");

        document.getElementById("studentDrawerTitle").textContent = `Ученик #${student.student}`;
        document.getElementById("studentDrawerSubtitle").textContent = student.student_details?.username || "";
        document.getElementById("studentDrawerInitials").textContent = getInitials(student.student_full_name).toUpperCase();
        document.getElementById("studentDrawerName").textContent = student.student_full_name;
        document.getElementById("studentDrawerStatus").innerHTML = getStatusBadge(student.student_is_active);
        document.getElementById("studentDrawerPhone").textContent = student.student_phone || "-";
        document.getElementById("studentDrawerEmail").textContent = student.student_email || "-";
        document.getElementById("studentDrawerCity").textContent = student.student_city || "-";
        document.getElementById("studentDrawerDate").textContent = formatDate(student.student_date_joined);
        document.getElementById("studentDrawerSource").textContent = student.source_display || "-";
        renderParentsList(student.parents || []);
        renderSubscriptionsList(student.subscriptions || []);
        fillStudentEditForm(student);
        setStudentEditMode(false);
        renderStudentGroups(student);
        loadStudentPayments(studentId);

        document.getElementById("studentDetailsDrawer").classList.add("is-open");
    };

    window.closeStudentDetailsDrawer = function () {
        document.getElementById("studentDetailsDrawer").classList.remove("is-open");
        selectedStudentId = null;
        setStudentGroupsAlert("");
        setStudentEditMode(false);
    };

    window.showStudentEditForm = function () {
        const student = getStudentById(selectedStudentId);

        if (!student) {
            return;
        }

        fillStudentEditForm(student);
        setStudentEditMode(true);
    };

    window.cancelStudentEdit = function () {
        const student = getStudentById(selectedStudentId);

        if (student) {
            fillStudentEditForm(student);
        }

        setStudentEditMode(false);
    };

    window.removeStudentGroup = function (studentId, membershipId) {
        setStudentGroupsAlert("");

        fetch(`/api/v1/students/${studentId}/groups/${membershipId}/`, {
            method: "DELETE",
            headers: headersWithCsrf,
        })
            .then((response) => {
                if (!response.ok) {
                    return response.json().then((data) => {
                        throw new Error(data.error || "Не удалось удалить ученика из группы");
                    });
                }
                return response.json();
            })
            .then((data) => {
                updateStudentInState(data.student);
                applyFilters();
                renderStudentGroups(data.student);
                setStudentGroupsAlert("Ученик удален из группы", true);
            })
            .catch((error) => {
                setStudentGroupsAlert(error.message, false);
            });
    };

    function addStudentToGroup(event) {
        event.preventDefault();

        if (!selectedStudentId) {
            return;
        }

        const select = document.getElementById("studentAddGroupSelect");
        const groupId = select.value;

        if (!groupId) {
            setStudentGroupsAlert("Выберите группу", false);
            return;
        }

        setStudentGroupsAlert("");

        fetch(`/api/v1/students/${selectedStudentId}/groups/`, {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify({ group_id: groupId }),
        })
            .then((response) => {
                if (!response.ok) {
                    return response.json().then((data) => {
                        throw new Error(data.error || "Не удалось добавить ученика в группу");
                    });
                }
                return response.json();
            })
            .then((data) => {
                updateStudentInState(data.student);
                applyFilters();
                renderStudentGroups(data.student);
                setStudentGroupsAlert("Ученик добавлен в группу", true);
            })
            .catch((error) => {
                setStudentGroupsAlert(error.message, false);
            });
    }

    window.removeStudentFromGroup = function (membershipId) {
        if (!selectedStudentId) {
            return;
        }

        setStudentGroupsAlert("");

        fetch(`/api/v1/students/${selectedStudentId}/groups/${membershipId}/`, {
            method: "DELETE",
            headers: headersWithCsrf,
        })
            .then((response) => {
                if (!response.ok) {
                    return response.json().then((data) => {
                        throw new Error(data.error || "Не удалось удалить ученика из группы");
                    });
                }
                return response.json();
            })
            .then((data) => {
                updateStudentInState(data.student);
                applyFilters();
                renderStudentGroups(data.student);
                setStudentGroupsAlert("Ученик удален из группы", true);
            })
            .catch((error) => {
                setStudentGroupsAlert(error.message, false);
            });
    };

    function saveStudentEdit(event) {
        event.preventDefault();

        if (!selectedStudentId) {
            return;
        }

        // Собираем данные родителей из формы
        const parentsData = [];
        document.querySelectorAll('.crm-parent-edit-card').forEach((card) => {
            const parentId = card.getAttribute('data-parent-id');
            parentsData.push({
                id: parentId ? parseInt(parentId, 10) : null,
                first_name: card.querySelector('.parent-first-name').value.trim(),
                last_name: card.querySelector('.parent-last-name').value.trim(),
                phone: card.querySelector('.parent-phone').value.trim() || null,
                email: card.querySelector('.parent-email').value.trim() || null,
            });
        });

        const payload = {
            last_name: document.getElementById("studentEditLastName").value.trim(),
            first_name: document.getElementById("studentEditFirstName").value.trim(),
            username: document.getElementById("studentEditUsername").value.trim(),
            phone: document.getElementById("studentEditPhone").value.trim() || null,
            email: document.getElementById("studentEditEmail").value.trim() || null,
            city: document.getElementById("studentEditCity").value.trim() || null,
            country: document.getElementById("studentEditCountry").value.trim() || null,
            sex: document.getElementById("studentEditSex").value === "1",
            is_active: document.getElementById("studentEditIsActive").value === "true",
            source: document.getElementById("studentEditSource").value || null,
            parents: parentsData
        };

        const contactError = validateOptionalContacts([
            { label: "Ученик", phone: payload.phone, email: payload.email },
            ...parentsData.map((parent, index) => ({ label: `Родитель ${index + 1}`, phone: parent.phone, email: parent.email })),
        ]);

        if (contactError) {
            setStudentEditAlert(contactError, false);
            return;
        }

        setStudentEditAlert("");
        document.getElementById("studentEditSaveBtn").disabled = true;

        console.log("Отправка данных ученика:", payload);

        fetch(`/api/v1/students/${selectedStudentId}/`, {
            method: "PATCH",
            headers: headersWithCsrf,
            body: JSON.stringify(payload),
        })
            .then((response) => {
                if (!response.ok) {
                    return response.json().then((data) => {
                        console.error("Ошибка от сервера:", data);
                        throw new Error(getErrorMessage(data));
                    });
                }
                return response.json();
            })
            .then((data) => {
                console.log("Ответ от сервера:", data);
                updateStudentInState(data.student);
                applyFilters();
                selectedStudentId = data.student.student;
                openStudentDetailsDrawer(data.student.student);
                setStudentEditAlert("Данные ученика сохранены", true);
                setStudentEditMode(true);
            })
            .catch((error) => {
                console.error("Ошибка при сохранении:", error);
                setStudentEditAlert(error.message, false);
            })
            .finally(() => {
                document.getElementById("studentEditSaveBtn").disabled = false;
            });
    }

    window.refreshStudents = function () {
        loadCourses();
        loadGroups();
        loadStudents();
    };

    function loadStudentPayments(studentId) {
        const container = document.getElementById("studentDrawerPayments");
        
        if (!container) {
            return;
        }
        
        container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--crm-muted);">Загрузка платежей...</div>';
        
        fetch(`/api/v1/subscriptions/students/${studentId}/payments/`, { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load payments");
                }
                return response.json();
            })
            .then((payments) => {
                renderPaymentsList(payments);
            })
            .catch((error) => {
                console.error("Ошибка загрузки платежей:", error);
                container.innerHTML = '<p style="color: var(--crm-muted); font-size: 13px;">Не удалось загрузить историю платежей</p>';
            });
    }

    function renderPaymentsList(payments) {
        const container = document.getElementById("studentDrawerPayments");
        
        if (!payments || payments.length === 0) {
            container.innerHTML = '<p style="color: var(--crm-muted); font-size: 13px;">История платежей пуста</p>';
            return;
        }
        
        container.innerHTML = payments.map((payment) => {
            const statusClass = payment.status === 'completed' ? 'active' : 
                               payment.status === 'pending' ? 'archive' : 'archive';
            const statusText = payment.status === 'completed' ? 'Оплачено' :
                              payment.status === 'pending' ? 'Ожидает оплаты' :
                              payment.status === 'failed' ? 'Ошибка' :
                              payment.status === 'canceled' ? 'Отменен' : payment.status;
            
            const methodText = payment.payment_method === 'online' ? 'Онлайн' :
                              payment.payment_method === 'cash' ? 'Наличные' :
                              payment.payment_method === 'card' ? 'Карта' :
                              payment.payment_method === 'transfer' ? 'Перевод' : payment.payment_method;

            const canConfirm = payment.status === 'pending' && payment.payment_method !== 'online';
            const canCancel = (payment.status === 'pending' && payment.payment_method !== 'online') || payment.status === 'failed';
            const actions = canConfirm || canCancel ? `
                <div class="crm-payment-card__actions">
                    ${canConfirm ? `<button class="crm-btn crm-btn--primary crm-btn--sm" type="button" onclick="confirmPayment(${payment.id})">Подтвердить оплату</button>` : ''}
                    ${canCancel ? `<button class="crm-btn crm-btn--secondary crm-btn--sm" type="button" onclick="cancelPayment(${payment.id})">Отменить</button>` : ''}
                </div>
            ` : '';
             
            return `
                <div class="crm-payment-card">
                    <div class="crm-payment-card__header">
                        <div>
                            <div class="crm-payment-card__title">Платеж #${payment.id}</div>
                            <div class="crm-payment-card__date">${formatDate(payment.created_at)}</div>
                        </div>
                        <span class="crm-status-badge crm-status-badge--${statusClass}">
                            ${statusText}
                        </span>
                    </div>
                    <div class="crm-payment-card__details">
                        <div class="crm-payment-detail">
                            <span class="crm-payment-detail__label">Сумма:</span>
                            <span class="crm-payment-detail__value">${payment.amount} ₽</span>
                        </div>
                        <div class="crm-payment-detail">
                            <span class="crm-payment-detail__label">Способ оплаты:</span>
                            <span class="crm-payment-detail__value">${methodText}</span>
                        </div>
                        ${payment.paid_at ? `
                        <div class="crm-payment-detail">
                            <span class="crm-payment-detail__label">Дата оплаты:</span>
                            <span class="crm-payment-detail__value">${formatDate(payment.paid_at)}</span>
                        </div>
                        ` : ''}
                        ${payment.error_message ? `
                        <div class="crm-payment-detail">
                            <span class="crm-payment-detail__label">Ошибка:</span>
                            <span class="crm-payment-detail__value">${escapeHtml(payment.error_message)}</span>
                        </div>
                        ` : ''}
                    </div>
                    ${actions}
                </div>
            `;
        }).join("");
    }

    window.confirmPayment = function (paymentId) {
        if (!confirm("Подтвердить получение оплаты и активировать тариф?")) {
            return;
        }

        fetch(`/api/v1/subscriptions/payments/${paymentId}/confirm/`, {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify({})
        })
            .then((response) => response.json().then((data) => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(data.error || "Не удалось подтвердить оплату");
                }
                refreshStudents();
                if (selectedStudentId) {
                    loadStudentPayments(selectedStudentId);
                }
            })
            .catch((error) => {
                alert(error.message);
            });
    };

    window.cancelPayment = function (paymentId) {
        const reason = prompt("Причина отмены платежа", "Оплата не поступила");
        if (reason === null) {
            return;
        }

        fetch(`/api/v1/subscriptions/payments/${paymentId}/cancel/`, {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify({ reason })
        })
            .then((response) => response.json().then((data) => ({ ok: response.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(data.error || "Не удалось отменить платеж");
                }
                refreshStudents();
                if (selectedStudentId) {
                    loadStudentPayments(selectedStudentId);
                }
            })
            .catch((error) => {
                alert(error.message);
            });
    };

    window.exportStudents = function () {
        alert("Экспорт учеников будет реализован позже.");
    };

    function makeUsername(value) {
        return String(value || "")
            .trim()
            .toLowerCase()
            .replace(/[^a-zа-яё0-9]+/gi, "_")
            .replace(/^_+|_+$/g, "") || "student";
    }

    window.openCreateStudentDrawer = function () {
        document.getElementById("createStudentForm").reset();
        document.getElementById("createStudentCountry").value = "Россия";
        document.getElementById("createStudentPassword").value = `student${Date.now().toString().slice(-5)}`;
        document.getElementById("createStudentUsername").dataset.touched = "";
        setCreateStudentAlert("");
        document.getElementById("createStudentDrawer").classList.add("is-open");
    };

    window.closeCreateStudentDrawer = function () {
        document.getElementById("createStudentDrawer").classList.remove("is-open");
        setCreateStudentAlert("");
    };

    function submitCreateStudentForm(event) {
        event.preventDefault();

        const lastName = document.getElementById("createStudentLastName").value.trim();
        const firstName = document.getElementById("createStudentFirstName").value.trim();
        const usernameInput = document.getElementById("createStudentUsername");

        if (!usernameInput.value.trim()) {
            usernameInput.value = makeUsername(`${lastName}_${firstName}`);
        }

        const payload = {
            last_name: lastName,
            first_name: firstName,
            sex: document.getElementById("createStudentSex").value,
            phone: document.getElementById("createStudentPhone").value.trim() || null,
            email: document.getElementById("createStudentEmail").value.trim() || null,
            city: document.getElementById("createStudentCity").value.trim() || null,
            country: document.getElementById("createStudentCountry").value.trim() || null,
            source: document.getElementById("createStudentSource").value || null,
            parent_last_name: document.getElementById("createParentLastName").value.trim(),
            parent_first_name: document.getElementById("createParentFirstName").value.trim(),
            parent_phone: document.getElementById("createParentPhone").value.trim() || null,
            parent_email: document.getElementById("createParentEmail").value.trim() || null,
            username: usernameInput.value.trim(),
            password: document.getElementById("createStudentPassword").value.trim(),
        };

        const contactError = validateOptionalContacts([
            { label: "Ученик", phone: payload.phone, email: payload.email },
            { label: "Родитель", phone: payload.parent_phone, email: payload.parent_email },
        ]);

        if (contactError) {
            setCreateStudentAlert(contactError, false);
            return;
        }

        if (!payload.last_name || !payload.first_name || !payload.sex || !payload.parent_last_name || !payload.parent_first_name || !payload.username || !payload.password) {
            setCreateStudentAlert("Заполните обязательные поля ученика, родителя и доступа", false);
            return;
        }

        const submitBtn = document.getElementById("createStudentSubmitBtn");
        submitBtn.disabled = true;
        submitBtn.textContent = "Сохранение...";
        setCreateStudentAlert("");

        fetch("/api/v1/students/", {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify(payload),
        })
            .then(jsonOrError)
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(getErrorMessage(data));
                }

                currentStudents.push(data.student);
                applyFilters();
                closeCreateStudentDrawer();
                openStudentDetailsDrawer(data.student.student);
            })
            .catch((error) => {
                setCreateStudentAlert(error.message, false);
            })
            .finally(() => {
                submitBtn.disabled = false;
                submitBtn.textContent = "Сохранить ученика";
            });
    }

    window.openBuyTariffModal = function () {
        if (!selectedStudentId) {
            return;
        }
        
        document.getElementById("buyTariffModal").classList.add("is-open");
        loadCoursesForTariff();
    };

    window.closeBuyTariffModal = function () {
        document.getElementById("buyTariffModal").classList.remove("is-open");
        document.getElementById("buyTariffForm").reset();
        document.getElementById("tariffSelect").disabled = true;
        document.getElementById("tariffInfo").hidden = true;
        document.getElementById("groupSelectContainer").style.display = 'none';
        document.getElementById("addToGroupCheckbox").checked = false;
        setBuyTariffAlert("");
    };

    function setBuyTariffAlert(message, isSuccess) {
        const alert = document.getElementById("buyTariffAlert");
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function loadCoursesForTariff() {
        fetch("/api/v1/courses/", { headers })
            .then((response) => response.json())
            .then((data) => {
                currentCourses = data;
                const select = document.getElementById("tariffCourseSelect");
                select.innerHTML = '<option value="">Выберите курс</option>' +
                    data.map((course) => `<option value="${course.id}">${escapeHtml(course.name)}</option>`).join("");
            })
            .catch((error) => {
                console.error("Ошибка загрузки курсов:", error);
            });
    }

    function loadTariffsForCourse(courseId) {
        fetch(`/api/v1/subscriptions/tariffs/?course=${courseId}`, { headers })
            .then((response) => response.json())
            .then((data) => {
                currentTariffs = data;
                const select = document.getElementById("tariffSelect");
                
                if (data.length === 0) {
                    select.innerHTML = '<option value="">Нет доступных тарифов</option>';
                    select.disabled = true;
                    return;
                }
                
                select.innerHTML = '<option value="">Выберите тариф</option>' +
                    data.map((tariff) => {
                        const trial = tariff.is_trial ? " (Пробный)" : "";
                        const subType = tariff.subscription_type_display || (tariff.subscription_type === 'individual' ? 'Индивидуальный' : 'Групповой');
                        return `<option value="${tariff.id}">${escapeHtml(tariff.name)} · ${escapeHtml(subType)}${trial} - ${tariff.price} руб.</option>`;
                    }).join("");
                select.disabled = false;
                
                // Загружаем группы для выбранного курса
                loadGroupsForCourse(courseId);
            })
            .catch((error) => {
                console.error("Ошибка загрузки тарифов:", error);
            });
    }

    function loadGroupsForCourse(courseId) {
        // Фильтруем группы по курсу из уже загруженных
        const groupsForCourse = currentGroups.filter((group) => group.course === parseInt(courseId));
        const select = document.getElementById("groupSelect");
        
        if (groupsForCourse.length === 0) {
            select.innerHTML = '<option value="">Нет доступных групп для этого курса</option>';
            select.disabled = true;
            return;
        }
        
        select.innerHTML = '<option value="">Выберите группу</option>' +
            groupsForCourse.map((group) => {
                return `<option value="${group.id}">${escapeHtml(group.number)} - ${escapeHtml(group.teacher_name || 'Без преподавателя')}</option>`;
            }).join("");
        select.disabled = false;
    }

    function showTariffInfo(tariffId) {
        const tariff = currentTariffs.find((t) => t.id === parseInt(tariffId));
        
        if (!tariff) {
            document.getElementById("tariffInfo").hidden = true;
            return;
        }
        
        const info = document.getElementById("tariffInfo");
        info.innerHTML = `
            <div class="crm-tariff-info__row">
                <span class="crm-tariff-info__label">Тип:</span>
                <span class="crm-tariff-info__value">${escapeHtml(tariff.subscription_type_display || tariff.subscription_type || 'Групповой')}</span>
            </div>
            <div class="crm-tariff-info__row">
                <span class="crm-tariff-info__label">Занятий:</span>
                <span class="crm-tariff-info__value">${tariff.lessons_count}</span>
            </div>
            <div class="crm-tariff-info__row">
                <span class="crm-tariff-info__label">Срок действия:</span>
                <span class="crm-tariff-info__value">${tariff.validity_days} дней</span>
            </div>
            <div class="crm-tariff-info__row">
                <span class="crm-tariff-info__label">Цена:</span>
                <span class="crm-tariff-info__value">${tariff.price} руб.</span>
            </div>
            ${tariff.description ? `<div style="margin-top: 12px; font-size: 13px; color: var(--crm-muted);">${escapeHtml(tariff.description)}</div>` : ''}
        `;
        info.hidden = false;
    }

    function buyTariff(event) {
        event.preventDefault();
        
        if (!selectedStudentId) {
            return;
        }
        
        const tariffId = document.getElementById("tariffSelect").value;
        const paymentMethod = document.getElementById("paymentMethodSelect").value;
        const tariff = currentTariffs.find((item) => Number(item.id) === Number(tariffId));
        
        if (!tariffId) {
            setBuyTariffAlert("Выберите тариф", false);
            return;
        }
        
        const isGroupSubscription = tariff?.subscription_type !== 'individual';
        const addToGroup = isGroupSubscription && document.getElementById("addToGroupCheckbox").checked;
        const groupId = document.getElementById("groupSelect").value;
        
        if (addToGroup && !groupId) {
            setBuyTariffAlert("Выберите группу или снимите галочку", false);
            return;
        }
        
        setBuyTariffAlert("");
        document.getElementById("buyTariffBtn").disabled = true;
        document.getElementById("buyTariffBtn").textContent = "Создание подписки...";
        
        const payload = {
            student_id: selectedStudentId,
            tariff_id: parseInt(tariffId),
            payment_method: paymentMethod
        };
        
        if (addToGroup && groupId) {
            payload.group_id = parseInt(groupId);
        }
        
        // Создаем подписку и платеж одним безопасным запросом.
        fetch("/api/v1/subscriptions/quick-create/", {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify(payload)
        })
            .then((response) => {
                if (!response.ok) {
                    return response.json().then((data) => {
                        throw new Error(data.error || "Не удалось создать подписку");
                    });
                }
                return response.json();
            })
            .then((subscriptionData) => {
                const paymentData = subscriptionData.payment_result || subscriptionData.payment || {};
                // Обработка результата
                if (paymentMethod === 'online' && subscriptionData.payment_url) {
                    // Онлайн-оплата: перенаправляем на ЮKassa
                    setBuyTariffAlert("Перенаправление на страницу оплаты...", true);
                    setTimeout(() => {
                        window.open(subscriptionData.payment_url, '_blank');
                        closeBuyTariffModal();
                        refreshStudents();
                    }, 1000);
                } else {
                    // Офлайн-оплата: показываем успех
                    const message = subscriptionData.group_added 
                        ? "Подписка создана, ученик добавлен в группу! Платеж ожидает подтверждения." 
                        : "Подписка создана! Платеж ожидает подтверждения.";
                    
                    setBuyTariffAlert(message, true);
                    setTimeout(() => {
                        closeBuyTariffModal();
                        refreshStudents();
                    }, 2000);
                }
            })
            .catch((error) => {
                setBuyTariffAlert(error.message, false);
            })
            .finally(() => {
                document.getElementById("buyTariffBtn").disabled = false;
                document.getElementById("buyTariffBtn").textContent = "Купить тариф";
            });
    }

    document.addEventListener("DOMContentLoaded", () => {
        loadCourses();
        loadGroups();
        loadStudents();

        on("studentsSearch", "input", applyFilters);
        on("studentsCourseFilter", "change", applyFilters);
        on("studentsGroupFilter", "change", applyFilters);
        on("studentsStatusFilter", "change", applyFilters);
        on("studentsWithoutGroupFilter", "change", applyFilters);
        on("studentsSortFilter", "change", applyFilters);
        on("studentAddGroupForm", "submit", addStudentToGroup);
        on("studentEditForm", "submit", saveStudentEdit);
        on("createStudentForm", "submit", submitCreateStudentForm);
        on("buyTariffForm", "submit", buyTariff);
        on("openCreateStudentBtn", "click", window.openCreateStudentDrawer);
        on("studentAddParentBtn", "click", window.addEditParentCard);

        document.addEventListener("click", (event) => {
            const actionElement = event.target.closest("[data-action]");
            if (!actionElement) {
                return;
            }

            if (actionElement.dataset.action === "open-create-student") {
                event.preventDefault();
                window.openCreateStudentDrawer();
            }

            if (actionElement.dataset.action === "add-edit-parent") {
                event.preventDefault();
                window.addEditParentCard();
            }
        });

        ["createStudentLastName", "createStudentFirstName"].forEach((id) => {
            const nameInput = document.getElementById(id);
            if (!nameInput) {
                return;
            }
            nameInput.addEventListener("input", () => {
                const usernameInput = document.getElementById("createStudentUsername");
                if (!usernameInput.dataset.touched) {
                    usernameInput.value = makeUsername(`${document.getElementById("createStudentLastName").value}_${document.getElementById("createStudentFirstName").value}`);
                }
            });
        });
        on("createStudentUsername", "input", (event) => {
            event.target.dataset.touched = "true";
        });
        
        on("tariffCourseSelect", "change", (e) => {
            const courseId = e.target.value;
            if (courseId) {
                loadTariffsForCourse(courseId);
                loadGroupsForCourse(courseId);
            } else {
                document.getElementById("tariffSelect").disabled = true;
                document.getElementById("tariffSelect").innerHTML = '<option value="">Сначала выберите курс</option>';
                document.getElementById("tariffInfo").hidden = true;
                document.getElementById("groupSelect").innerHTML = '<option value="">Сначала выберите курс</option>';
                document.getElementById("groupSelect").disabled = true;
            }
        });
        
        on("tariffSelect", "change", (e) => {
            const tariffId = e.target.value;
            if (tariffId) {
                showTariffInfo(tariffId);
                const tariff = currentTariffs.find((item) => Number(item.id) === Number(tariffId));
                const isIndividual = tariff?.subscription_type === 'individual';
                const groupCheckbox = document.getElementById("addToGroupCheckbox");
                const groupContainer = document.getElementById("groupSelectContainer");
                groupCheckbox.disabled = isIndividual;
                if (isIndividual) {
                    groupCheckbox.checked = false;
                    groupContainer.style.display = 'none';
                }
            } else {
                document.getElementById("tariffInfo").hidden = true;
            }
        });
        
        on("addToGroupCheckbox", "change", (e) => {
            const groupContainer = document.getElementById("groupSelectContainer");
            if (e.target.checked) {
                groupContainer.style.display = 'block';
            } else {
                groupContainer.style.display = 'none';
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeStudentDetailsDrawer();
            }
        });
    });
})();
