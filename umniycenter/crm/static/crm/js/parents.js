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

    let currentParents = [];
    let selectedParentId = null;

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

        return messages.join(" ") || "Не удалось сохранить родителя";
    }

    function getInitials(name) {
        const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
        return ((parts[0]?.[0] || "Р") + (parts[1]?.[0] || "")).toUpperCase();
    }

    function getStatusBadge(isActive) {
        return isActive
            ? '<span class="crm-status-badge crm-status-badge--active">Активный</span>'
            : '<span class="crm-status-badge crm-status-badge--archive">Архивный</span>';
    }

    function setParentEditAlert(message, isSuccess) {
        const alert = document.getElementById("parentEditAlert");
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

    function getParentById(parentId) {
        return currentParents.find((parent) => parent.id === parentId);
    }

    function updateParentInState(updatedParent) {
        const index = currentParents.findIndex((parent) => parent.id === updatedParent.id);
        if (index !== -1) {
            currentParents[index] = updatedParent;
        }
    }

    function renderChildren(children) {
        const container = document.getElementById("parentDrawerChildren");
        if (!children || children.length === 0) {
            container.innerHTML = '<p style="color: var(--crm-muted); font-size: 13px;">У родителя нет привязанных детей</p>';
            return;
        }

        container.innerHTML = children.map((child) => `
            <div class="crm-parent-card">
                <div class="crm-parent-card__header">
                    <strong>${escapeHtml(child.full_name)}</strong>
                    ${getStatusBadge(child.is_active)}
                </div>
                <div class="crm-info-grid" style="margin-top: 8px;">
                    <div class="crm-info-item"><span class="crm-info-label">Логин</span><strong>${escapeHtml(child.username)}</strong></div>
                    <div class="crm-info-item"><span class="crm-info-label">Контакты</span><strong>${escapeHtml(child.phone || child.email || '-')}</strong></div>
                </div>
            </div>
        `).join("");
    }

    function renderParents(parents) {
        const tbody = document.getElementById("parentsTableBody");
        document.getElementById("parentsCount").textContent = parents.length;
        document.querySelectorAll('[data-nav-count="parents"]').forEach((item) => {
            item.textContent = currentParents.length;
        });

        if (!parents.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="crm-table-empty">Родители не найдены. Попробуйте изменить поиск.</td></tr>';
            return;
        }

        tbody.innerHTML = parents.map((parent) => `
            <tr onclick="openParentDetailsDrawer(${parent.id})">
                <td>
                    <div class="crm-table-name">${escapeHtml(parent.full_name)}</div>
                    <span class="crm-table-meta">#${parent.id}</span>
                </td>
                <td>
                    <div>${escapeHtml(parent.phone || '-')}</div>
                    ${parent.email ? `<span class="crm-table-meta">${escapeHtml(parent.email)}</span>` : ''}
                </td>
                <td>${escapeHtml(parent.username)}</td>
                <td>${escapeHtml((parent.children || []).map((child) => child.full_name).join(', ') || '-')}</td>
                <td>${getStatusBadge(parent.is_active)}</td>
                <td>
                    <button class="crm-table-action-btn" type="button" onclick="event.stopPropagation(); openParentDetailsDrawer(${parent.id})" title="Открыть карточку">
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
        const search = document.getElementById("parentsSearch").value.trim().toLowerCase();
        const sort = document.getElementById("parentsSortFilter").value;
        let filtered = [...currentParents];

        if (search) {
            filtered = filtered.filter((parent) => {
                const haystack = [
                    parent.full_name,
                    parent.phone,
                    parent.email,
                    parent.username,
                    ...(parent.children || []).map((child) => `${child.full_name} ${child.username}`),
                ].join(" ").toLowerCase();
                return haystack.includes(search);
            });
        }

        filtered.sort((a, b) => {
            if (sort === "name_za") {
                return b.full_name.localeCompare(a.full_name);
            }
            if (sort === "children_many") {
                return (b.children || []).length - (a.children || []).length;
            }
            return a.full_name.localeCompare(b.full_name);
        });

        renderParents(filtered);
    }

    function loadParents() {
        const tbody = document.getElementById("parentsTableBody");
        tbody.innerHTML = '<tr><td colspan="6" class="crm-table-loading"><div class="crm-spinner"></div><span>Загрузка родителей...</span></td></tr>';

        fetch("/api/v1/parents/", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load parents");
                }
                return response.json();
            })
            .then((data) => {
                currentParents = data;
                applyFilters();
            })
            .catch(() => {
                tbody.innerHTML = '<tr><td colspan="6" class="crm-table-empty">Не удалось загрузить родителей. Попробуйте обновить страницу.</td></tr>';
            });
    }

    function fillParentEditForm(parent) {
        document.getElementById("parentEditLastName").value = parent.last_name || "";
        document.getElementById("parentEditFirstName").value = parent.first_name || "";
        document.getElementById("parentEditPhone").value = parent.phone || "";
        document.getElementById("parentEditEmail").value = parent.email || "";
        document.getElementById("parentEditUsername").value = parent.username || "";
        document.getElementById("parentEditPassword").value = "";
        document.getElementById("parentEditIsActive").value = parent.is_active ? "true" : "false";
    }

    function setParentEditMode(isEditing) {
        document.getElementById("parentEditForm").hidden = !isEditing;
        document.getElementById("parentEditCancelBtn").hidden = !isEditing;
        document.getElementById("parentEditSaveBtn").hidden = !isEditing;
        document.getElementById("parentEditToggleBtn").hidden = isEditing;

        if (!isEditing) {
            setParentEditAlert("");
        }
    }

    window.openParentDetailsDrawer = function (parentId) {
        const parent = getParentById(parentId);
        if (!parent) {
            return;
        }

        selectedParentId = parentId;
        document.getElementById("parentDrawerTitle").textContent = `Родитель #${parent.id}`;
        document.getElementById("parentDrawerSubtitle").textContent = parent.username;
        document.getElementById("parentDrawerInitials").textContent = getInitials(parent.full_name);
        document.getElementById("parentDrawerName").textContent = parent.full_name;
        document.getElementById("parentDrawerStatus").innerHTML = getStatusBadge(parent.is_active);
        document.getElementById("parentDrawerPhone").textContent = parent.phone || "-";
        document.getElementById("parentDrawerEmail").textContent = parent.email || "-";
        document.getElementById("parentDrawerUsername").textContent = parent.username || "-";
        renderChildren(parent.children || []);
        fillParentEditForm(parent);
        setParentEditMode(false);
        document.getElementById("parentDetailsDrawer").classList.add("is-open");
    };

    window.closeParentDetailsDrawer = function () {
        document.getElementById("parentDetailsDrawer").classList.remove("is-open");
        selectedParentId = null;
        setParentEditMode(false);
    };

    window.showParentEditForm = function () {
        const parent = getParentById(selectedParentId);
        if (!parent) {
            return;
        }
        fillParentEditForm(parent);
        setParentEditMode(true);
    };

    window.cancelParentEdit = function () {
        const parent = getParentById(selectedParentId);
        if (parent) {
            fillParentEditForm(parent);
        }
        setParentEditMode(false);
    };

    function saveParentEdit(event) {
        event.preventDefault();
        if (!selectedParentId) {
            return;
        }

        const phone = document.getElementById("parentEditPhone").value.trim();
        const email = document.getElementById("parentEditEmail").value.trim();
        const contactError = validateContacts(phone, email);
        if (contactError) {
            setParentEditAlert(contactError, false);
            return;
        }

        const payload = {
            last_name: document.getElementById("parentEditLastName").value.trim(),
            first_name: document.getElementById("parentEditFirstName").value.trim(),
            phone: phone || null,
            email: email || null,
            username: document.getElementById("parentEditUsername").value.trim(),
            is_active: document.getElementById("parentEditIsActive").value === "true",
        };
        const password = document.getElementById("parentEditPassword").value.trim();
        if (password) {
            payload.password = password;
        }

        if (!payload.last_name || !payload.first_name || !payload.username) {
            setParentEditAlert("Заполните имя, фамилию и логин родителя", false);
            return;
        }

        const button = document.getElementById("parentEditSaveBtn");
        button.disabled = true;
        setParentEditAlert("");

        fetch(`/api/v1/parents/${selectedParentId}/`, {
            method: "PATCH",
            headers: headersWithCsrf,
            body: JSON.stringify(payload),
        })
            .then(jsonOrError)
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(getErrorMessage(data));
                }
                updateParentInState(data.parent);
                applyFilters();
                selectedParentId = data.parent.id;
                window.openParentDetailsDrawer(data.parent.id);
                setParentEditAlert("Данные родителя сохранены", true);
                setParentEditMode(true);
            })
            .catch((error) => {
                setParentEditAlert(error.message, false);
            })
            .finally(() => {
                button.disabled = false;
            });
    }

    window.refreshParents = function () {
        loadParents();
    };

    document.addEventListener("DOMContentLoaded", () => {
        loadParents();
        on("parentsSearch", "input", applyFilters);
        on("parentsSortFilter", "change", applyFilters);
        on("parentEditForm", "submit", saveParentEdit);
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeParentDetailsDrawer();
            }
        });
    });
})();
