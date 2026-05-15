(function () {
    const phonePattern = /^\+7\d{10}$/;

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

    let currentTeachers = [];
    let selectedTeacherId = null;

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
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
        }).catch(() => ({ ok: false, data: { error: "Сервер вернул некорректный ответ" } }));
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

        return messages.join(" ") || "Не удалось сохранить учителя";
    }

    function getInitials(name) {
        const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
        return ((parts[0]?.[0] || "У") + (parts[1]?.[0] || "")).toUpperCase();
    }

    function getStatusBadge(isActive) {
        return isActive
            ? '<span class="crm-status-badge crm-status-badge--active">Активный</span>'
            : '<span class="crm-status-badge crm-status-badge--archive">Архивный</span>';
    }

    function setTeacherEditAlert(message, isSuccess) {
        const alert = document.getElementById("teacherEditAlert");
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function validateContacts(phone, email) {
        if (phone && !phonePattern.test(phone)) {
            return "Телефон должен быть в формате +7XXXXXXXXXX";
        }

        if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            return "Введите корректный email";
        }

        return "";
    }

    function getTeacherById(teacherId) {
        return currentTeachers.find((teacher) => teacher.id === teacherId);
    }

    function updateTeacherInState(updatedTeacher) {
        const index = currentTeachers.findIndex((teacher) => teacher.id === updatedTeacher.id);
        if (index !== -1) {
            currentTeachers[index] = updatedTeacher;
        }
    }

    function renderGroups(groups) {
        const container = document.getElementById("teacherDrawerGroups");
        if (!groups || groups.length === 0) {
            container.innerHTML = '<p style="color: var(--crm-muted); font-size: 13px;">Учитель не назначен ни в одну группу</p>';
            return;
        }

        container.innerHTML = groups.map((group) => `
            <div class="crm-group-badge">
                <strong>${escapeHtml(group.name)}</strong>
                <span>${escapeHtml(group.course)}</span>
            </div>
        `).join("");
    }

    function renderSchedule(schedule) {
        const container = document.getElementById("teacherDrawerSchedule");
        if (!schedule || schedule.length === 0) {
            container.innerHTML = '<p style="color: var(--crm-muted); font-size: 13px;">Нет запланированных занятий</p>';
            return;
        }

        container.innerHTML = schedule.map((lesson) => `
            <div class="crm-list-item">
                <div>
                    <strong>${escapeHtml(lesson.group)}</strong>
                    <span>${escapeHtml(lesson.date)} · ${escapeHtml(lesson.start_time)}-${escapeHtml(lesson.end_time)}</span>
                </div>
            </div>
        `).join("");
    }

    function renderTeachers(teachers) {
        const tbody = document.getElementById("teachersTableBody");
        document.getElementById("teachersCount").textContent = teachers.length;
        
        // Обновляем счетчик в навигации
        document.querySelectorAll('[data-nav-count="teachers"]').forEach((item) => {
            item.textContent = currentTeachers.length;
        });

        if (!teachers.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="crm-table-empty">Учителя не найдены. Попробуйте изменить поиск.</td></tr>';
            return;
        }

        tbody.innerHTML = teachers.map((teacher) => `
            <tr onclick="openTeacherDetailsDrawer(${teacher.id})">
                <td>
                    <div class="crm-table-name">${escapeHtml(teacher.full_name)}</div>
                    <div class="crm-table-meta">@${escapeHtml(teacher.username)}</div>
                </td>
                <td>
                    <div class="crm-table-contact">${escapeHtml(teacher.phone || '-')}</div>
                    <div class="crm-table-contact">${escapeHtml(teacher.email || '-')}</div>
                </td>
                <td>${escapeHtml(teacher.city || '-')}</td>
                <td>
                    <span class="crm-badge crm-badge--blue">${teacher.groups_count || 0} групп</span>
                </td>
                <td>${escapeHtml(teacher.date_joined || '-')}</td>
                <td>${getStatusBadge(teacher.is_active)}</td>
                <td>
                    <button class="crm-table-action-btn" type="button" onclick="event.stopPropagation(); openTeacherDetailsDrawer(${teacher.id})" title="Открыть карточку">
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
        const search = document.getElementById("teachersSearch").value.toLowerCase();
        const sort = document.getElementById("teachersSortFilter").value;
        const statusFilter = document.getElementById("teachersStatusFilter").value;

        let filtered = currentTeachers.filter((teacher) => {
            const searchText = `${teacher.full_name} ${teacher.username} ${teacher.phone || ''} ${teacher.email || ''}`.toLowerCase();
            const matchesSearch = searchText.includes(search);
            
            let matchesStatus = true;
            if (statusFilter === 'active') {
                matchesStatus = teacher.is_active === true;
            } else if (statusFilter === 'archive') {
                matchesStatus = teacher.is_active === false;
            }
            
            return matchesSearch && matchesStatus;
        });

        filtered.sort((a, b) => {
            switch (sort) {
                case "name_az":
                    return a.full_name.localeCompare(b.full_name, 'ru');
                case "name_za":
                    return b.full_name.localeCompare(a.full_name, 'ru');
                case "date_new":
                    return new Date(b.date_joined) - new Date(a.date_joined);
                case "date_old":
                    return new Date(a.date_joined) - new Date(b.date_joined);
                default:
                    return 0;
            }
        });

        renderTeachers(filtered);
    }

    function loadTeachers() {
        const tbody = document.getElementById("teachersTableBody");
        tbody.innerHTML = '<tr><td colspan="7" class="crm-table-loading"><div class="crm-spinner"></div><span>Загрузка учителей...</span></td></tr>';

        fetch("/api/v1/teachers/", { headers })
            .then((response) => jsonOrError(response))
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(data.error || "Не удалось загрузить учителей");
                }

                currentTeachers = data;
                applyFilters();
            })
            .catch((error) => {
                tbody.innerHTML = `<tr><td colspan="7" class="crm-table-error">Ошибка: ${escapeHtml(error.message)}</td></tr>`;
            });
    }

    function loadTeacherDetails(teacherId) {
        fetch(`/api/v1/teachers/${teacherId}/`, { headers })
            .then((response) => jsonOrError(response))
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(data.error || "Не удалось загрузить данные учителя");
                }

                displayTeacherDetails(data);
            })
            .catch((error) => {
                alert(`Ошибка: ${error.message}`);
                closeTeacherDetailsDrawer();
            });
    }

    function displayTeacherDetails(teacher) {
        document.getElementById("teacherDrawerTitle").textContent = "Карточка учителя";
        document.getElementById("teacherDrawerSubtitle").textContent = `@${teacher.username}`;
        document.getElementById("teacherDrawerInitials").textContent = getInitials(teacher.full_name);
        document.getElementById("teacherDrawerName").textContent = teacher.full_name;
        document.getElementById("teacherDrawerStatus").innerHTML = getStatusBadge(teacher.is_active);
        document.getElementById("teacherDrawerPhone").textContent = teacher.phone || '-';
        document.getElementById("teacherDrawerEmail").textContent = teacher.email || '-';
        document.getElementById("teacherDrawerCity").textContent = teacher.city || '-';
        document.getElementById("teacherDrawerDate").textContent = teacher.date_joined || '-';

        renderGroups(teacher.groups || []);
        renderSchedule(teacher.schedule || []);

        document.getElementById("teacherEditLastName").value = teacher.last_name || '';
        document.getElementById("teacherEditFirstName").value = teacher.first_name || '';
        document.getElementById("teacherEditUsername").value = teacher.username || '';
        document.getElementById("teacherEditPhone").value = teacher.phone || '';
        document.getElementById("teacherEditEmail").value = teacher.email || '';
        document.getElementById("teacherEditCity").value = teacher.city || '';
        document.getElementById("teacherEditCountry").value = teacher.country || '';
        document.getElementById("teacherEditSex").value = teacher.sex ? '1' : '0';
        document.getElementById("teacherEditIsActive").value = teacher.is_active ? 'true' : 'false';
    }

    window.openTeacherDetailsDrawer = function (teacherId) {
        selectedTeacherId = teacherId;
        document.getElementById("teacherDetailsDrawer").classList.add("is-open");
        document.body.style.overflow = "hidden";
        loadTeacherDetails(teacherId);
    };

    window.closeTeacherDetailsDrawer = function () {
        document.getElementById("teacherDetailsDrawer").classList.remove("is-open");
        document.body.style.overflow = "";
        selectedTeacherId = null;
        cancelTeacherEdit();
    };

    window.showTeacherEditForm = function () {
        document.getElementById("teacherEditForm").hidden = false;
        document.getElementById("teacherEditToggleBtn").hidden = true;
        document.getElementById("teacherEditCancelBtn").hidden = false;
        document.getElementById("teacherEditSaveBtn").hidden = false;
        setTeacherEditAlert("", false);
    };

    window.cancelTeacherEdit = function () {
        document.getElementById("teacherEditForm").hidden = true;
        document.getElementById("teacherEditToggleBtn").hidden = false;
        document.getElementById("teacherEditCancelBtn").hidden = true;
        document.getElementById("teacherEditSaveBtn").hidden = true;
        setTeacherEditAlert("", false);
    };

    window.refreshTeachers = function () {
        loadTeachers();
    };

    on("teacherEditForm", "submit", function (event) {
        event.preventDefault();
        setTeacherEditAlert("", false);

        const lastName = document.getElementById("teacherEditLastName").value.trim();
        const firstName = document.getElementById("teacherEditFirstName").value.trim();
        const username = document.getElementById("teacherEditUsername").value.trim();
        const phone = document.getElementById("teacherEditPhone").value.trim();
        const email = document.getElementById("teacherEditEmail").value.trim();
        const city = document.getElementById("teacherEditCity").value.trim();
        const country = document.getElementById("teacherEditCountry").value.trim();
        const sex = document.getElementById("teacherEditSex").value;

        if (!lastName || !firstName || !username) {
            setTeacherEditAlert("Заполните обязательные поля", false);
            return;
        }

        const contactError = validateContacts(phone, email);
        if (contactError) {
            setTeacherEditAlert(contactError, false);
            return;
        }

        const payload = {
            last_name: lastName,
            first_name: firstName,
            username: username,
            phone: phone || null,
            email: email || null,
            city: city || null,
            country: country || null,
            sex: sex === '1',
            is_active: document.getElementById("teacherEditIsActive").value === 'true',
        };

        fetch(`/api/v1/teachers/${selectedTeacherId}/`, {
            method: "PATCH",
            headers: headersWithCsrf,
            body: JSON.stringify(payload),
        })
            .then((response) => jsonOrError(response))
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(getErrorMessage(data));
                }

                setTeacherEditAlert("Учитель успешно обновлен", true);
                updateTeacherInState(data);
                displayTeacherDetails(data);
                applyFilters();

                setTimeout(() => {
                    cancelTeacherEdit();
                }, 1500);
            })
            .catch((error) => {
                setTeacherEditAlert(error.message, false);
            });
    });

    on("teachersSearch", "input", applyFilters);
    on("teachersSortFilter", "change", applyFilters);
    on("teachersStatusFilter", "change", applyFilters);

    window.openCreateTeacherDrawer = function () {
        document.getElementById("createTeacherDrawer").classList.add("is-open");
        document.body.style.overflow = "hidden";
        document.getElementById("createTeacherForm").reset();
        document.getElementById("createTeacherAlert").hidden = true;
    };

    window.closeCreateTeacherDrawer = function () {
        document.getElementById("createTeacherDrawer").classList.remove("is-open");
        document.body.style.overflow = "";
    };

    on("openCreateTeacherBtn", "click", openCreateTeacherDrawer);

    on("createTeacherForm", "submit", function (event) {
        event.preventDefault();
        const alert = document.getElementById("createTeacherAlert");
        alert.hidden = true;

        const lastName = document.getElementById("createTeacherLastName").value.trim();
        const firstName = document.getElementById("createTeacherFirstName").value.trim();
        const sex = document.getElementById("createTeacherSex").value;
        const phone = document.getElementById("createTeacherPhone").value.trim();
        const email = document.getElementById("createTeacherEmail").value.trim();
        const city = document.getElementById("createTeacherCity").value.trim();
        const country = document.getElementById("createTeacherCountry").value.trim();
        const username = document.getElementById("createTeacherUsername").value.trim();
        const password = document.getElementById("createTeacherPassword").value.trim();

        if (!lastName || !firstName || !sex || !username || !password) {
            alert.textContent = "Заполните все обязательные поля";
            alert.hidden = false;
            alert.classList.remove("is-success");
            return;
        }

        const contactError = validateContacts(phone, email);
        if (contactError) {
            alert.textContent = contactError;
            alert.hidden = false;
            alert.classList.remove("is-success");
            return;
        }

        const payload = {
            last_name: lastName,
            first_name: firstName,
            sex: sex === '1',
            phone: phone || null,
            email: email || null,
            city: city || null,
            country: country || null,
            username: username,
            password: password,
            role: 0,
        };

        const submitBtn = document.getElementById("createTeacherSubmitBtn");
        submitBtn.disabled = true;

        fetch("/api/v1/teachers/create/", {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify(payload),
        })
            .then((response) => jsonOrError(response))
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(getErrorMessage(data));
                }

                alert.textContent = "Учитель успешно создан";
                alert.hidden = false;
                alert.classList.add("is-success");

                setTimeout(() => {
                    closeCreateTeacherDrawer();
                    loadTeachers();
                }, 1500);
            })
            .catch((error) => {
                alert.textContent = error.message;
                alert.hidden = false;
                alert.classList.remove("is-success");
            })
            .finally(() => {
                submitBtn.disabled = false;
            });
    });

    document.addEventListener("DOMContentLoaded", loadTeachers);
})();
