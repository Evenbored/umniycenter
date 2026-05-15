(function () {
    function getCsrfToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
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
        "X-CSRFToken": getCsrfToken(),
    };

    let currentRequests = [];
    let currentView = "table";
    let currentRequestId = null;
    let studentSourceRequestId = null;

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatDate(isoString) {
        const date = new Date(isoString);
        const day = String(date.getDate()).padStart(2, "0");
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const year = date.getFullYear();
        return `${day}.${month}.${year}`;
    }

    function formatDateTime(isoString) {
        const date = new Date(isoString);
        const day = String(date.getDate()).padStart(2, "0");
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const year = date.getFullYear();
        const hours = String(date.getHours()).padStart(2, "0");
        const minutes = String(date.getMinutes()).padStart(2, "0");
        return `${day}.${month}.${year} в ${hours}:${minutes}`;
    }

    function getStatusBadge(checked) {
        if (checked) {
            return '<span class="crm-status-badge crm-status-badge--processed">Обработана</span>';
        }
        return '<span class="crm-status-badge crm-status-badge--new">Новая</span>';
    }

    function splitFullName(value) {
        const parts = String(value || "").trim().split(/\s+/).filter(Boolean);

        return {
            lastName: parts[0] || "",
            firstName: parts[1] || "",
        };
    }

    function makeUsername(value) {
        return String(value || "")
            .trim()
            .toLowerCase()
            .replace(/[^a-zа-яё0-9]+/gi, "_")
            .replace(/^_+|_+$/g, "") || "student";
    }

    function setStudentFormAlert(message, isSuccess) {
        const alert = document.getElementById("studentFormAlert");
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function showToast(title, message, isSuccess) {
        const existingToast = document.querySelector(".crm-toast");
        if (existingToast) {
            existingToast.remove();
        }

        const toast = document.createElement("div");
        toast.className = `crm-toast ${isSuccess ? "is-success" : "is-error"}`;
        toast.innerHTML = `
            <div class="crm-toast__icon">
                ${isSuccess 
                    ? '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>'
                    : '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>'
                }
            </div>
            <div class="crm-toast__content">
                <h4 class="crm-toast__title">${escapeHtml(title)}</h4>
                <p class="crm-toast__message">${escapeHtml(message)}</p>
            </div>
            <button class="crm-toast__close" onclick="this.parentElement.remove()">
                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path d="M18 6 6 18M6 6l12 12"/>
                </svg>
            </button>
        `;

        document.body.appendChild(toast);

        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.animation = "crm-toast-out 0.3s cubic-bezier(0.16, 1, 0.3, 1)";
                setTimeout(() => toast.remove(), 300);
            }
        }, 5000);
    }

    function updateSidebarRequestsCount() {
        const newRequestsCount = currentRequests.filter(r => !r.checked).length;
        document.querySelectorAll('[data-nav-count="requests"]').forEach((el) => {
            el.textContent = newRequestsCount;
        });
    }

    function renderTableView(requests) {
        const tbody = document.getElementById("requestsTableBody");

        if (!requests.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="crm-table-empty">
                        Заявок не найдено. Попробуйте изменить фильтры.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = requests.map((request) => `
            <tr onclick="openRequestDrawer(${request.id})">
                <td>
                    <div class="crm-table-name">${escapeHtml(request.child_fio)}</div>
                </td>
                <td>
                    <div class="crm-table-name">${escapeHtml(request.parent_fio)}</div>
                </td>
                <td>
                    <div>${escapeHtml(request.phone)}</div>
                    ${request.email ? `<div class="crm-table-meta">${escapeHtml(request.email)}</div>` : ''}
                </td>
                <td>
                    <div>${escapeHtml(request.age)} лет</div>
                </td>
                <td>
                    <div class="crm-table-meta">${escapeHtml(request.courses_display)}</div>
                </td>
                <td>
                    <div>${escapeHtml(request.source_display || '-')}</div>
                </td>
                <td>
                    <div>${formatDate(request.created)}</div>
                </td>
                <td>
                    ${getStatusBadge(request.checked)}
                </td>
                <td>
                    <div class="crm-table-actions">
                        <button onclick="event.stopPropagation(); openRequestDrawer(${request.id})" title="Открыть">
                            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                <circle cx="12" cy="12" r="3"/>
                            </svg>
                        </button>
                    </div>
                </td>
            </tr>
        `).join("");
    }

    function renderCardsView(requests) {
        const grid = document.getElementById("requestsCardsGrid");

        if (!requests.length) {
            grid.innerHTML = '<div class="crm-empty">Заявок не найдено. Попробуйте изменить фильтры.</div>';
            return;
        }

        grid.innerHTML = requests.map((request) => `
            <article class="crm-request-card" onclick="openRequestDrawer(${request.id})">
                <div class="crm-request-card__header">
                    <div>
                        <h4 class="crm-request-card__title">${escapeHtml(request.child_fio)}</h4>
                        <div class="crm-request-card__meta">${formatDate(request.created)}</div>
                    </div>
                    ${getStatusBadge(request.checked)}
                </div>
                <div class="crm-request-card__body">
                    <div class="crm-request-card__row">
                        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                            <circle cx="12" cy="7" r="4"/>
                        </svg>
                        <span>${escapeHtml(request.parent_fio)}</span>
                    </div>
                    <div class="crm-request-card__row">
                        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
                        </svg>
                        <span>${escapeHtml(request.phone)}</span>
                    </div>
                    <div class="crm-request-card__row">
                        <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
                        </svg>
                        <span>${escapeHtml(request.courses_display)}</span>
                    </div>
                </div>
            </article>
        `).join("");
    }

    function renderRequests(requests) {
        document.getElementById("requestsCount").textContent = requests.length;

        if (currentView === "table") {
            renderTableView(requests);
        } else {
            renderCardsView(requests);
        }
    }

    function applyFilters() {
        const search = document.getElementById("requestsSearch").value.toLowerCase();
        const status = document.getElementById("requestsStatusFilter").value;
        const sort = document.getElementById("requestsSortFilter").value;

        let filtered = [...currentRequests];

        if (search) {
            filtered = filtered.filter((request) => {
                return (
                    request.child_fio.toLowerCase().includes(search) ||
                    request.parent_fio.toLowerCase().includes(search) ||
                    request.phone.toLowerCase().includes(search) ||
                    (request.email && request.email.toLowerCase().includes(search)) ||
                    request.courses_display.toLowerCase().includes(search)
                );
            });
        }

        if (status === "new") {
            filtered = filtered.filter((request) => !request.checked);
        } else if (status === "processed") {
            filtered = filtered.filter((request) => request.checked);
        }

        if (sort === "-created") {
            filtered.sort((a, b) => new Date(b.created) - new Date(a.created));
        } else if (sort === "created") {
            filtered.sort((a, b) => new Date(a.created) - new Date(b.created));
        } else if (sort === "child_fio") {
            filtered.sort((a, b) => a.child_fio.localeCompare(b.child_fio));
        }

        renderRequests(filtered);
    }

    function loadRequests() {
        const tbody = document.getElementById("requestsTableBody");
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="crm-table-loading">
                    <div class="crm-spinner"></div>
                    <span>Загрузка заявок...</span>
                </td>
            </tr>
        `;

        fetch("/api/v1/participant-requests/", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load requests");
                }
                return response.json();
            })
            .then((data) => {
                currentRequests = data;
                applyFilters();
            })
            .catch(() => {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="9" class="crm-table-empty">
                            Не удалось загрузить заявки. Попробуйте обновить страницу.
                        </td>
                    </tr>
                `;
            });
    }

    window.openRequestDrawer = function (requestId) {
        const request = currentRequests.find((r) => r.id === requestId);

        if (!request) {
            return;
        }

        currentRequestId = requestId;

        document.getElementById("drawerRequestTitle").textContent = `Заявка #${request.id}`;
        document.getElementById("drawerRequestDate").textContent = formatDateTime(request.created);
        document.getElementById("drawerChildFio").textContent = request.child_fio;
        document.getElementById("drawerChildAge").textContent = `${request.age} лет`;
        document.getElementById("drawerParentFio").textContent = request.parent_fio;
        document.getElementById("drawerEmail").textContent = request.phone + (request.email ? ` · ${request.email}` : '');
        document.getElementById("drawerSource").textContent = request.source_display || "-";
        document.getElementById("drawerCreatedFull").textContent = formatDateTime(request.created);
        document.getElementById("drawerStatus").innerHTML = getStatusBadge(request.checked);

        const coursesContainer = document.getElementById("drawerCourses");
        const courses = request.courses_list || [];
        coursesContainer.innerHTML = courses.map((course) => `
            <span class="crm-tag">${escapeHtml(course.name)}</span>
        `).join("") || '<span class="crm-tag">Не указаны</span>';

        const markBtn = document.getElementById("drawerMarkProcessedBtn");
        if (request.checked) {
            markBtn.disabled = true;
            markBtn.style.opacity = "0.5";
            markBtn.style.cursor = "not-allowed";
        } else {
            markBtn.disabled = false;
            markBtn.style.opacity = "1";
            markBtn.style.cursor = "pointer";
            markBtn.innerHTML = `
                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <path d="M20 6 9 17l-5-5"/>
                </svg>
                Отметить обработанной
            `;
        }

        document.getElementById("requestDrawer").classList.add("is-open");
    };

    window.closeRequestDrawer = function () {
        document.getElementById("requestDrawer").classList.remove("is-open");
        currentRequestId = null;
    };

    window.closeStudentDrawer = function () {
        document.getElementById("studentDrawer").classList.remove("is-open");
        studentSourceRequestId = null;
        setStudentFormAlert("");
    };

    window.markRequestProcessed = function () {
        if (!currentRequestId) {
            return;
        }

        const request = currentRequests.find((r) => r.id === currentRequestId);

        if (!request || request.checked) {
            return;
        }

        const markBtn = document.getElementById("drawerMarkProcessedBtn");
        markBtn.disabled = true;
        markBtn.innerHTML = `
            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path d="M20 6 9 17l-5-5"/>
            </svg>
            Обработка...
        `;

        fetch(`/api/v1/participant-requests/${currentRequestId}/mark-processed/`, {
            method: "PATCH",
            headers: headersWithCsrf
        })
            .then((response) => {
                if (!response.ok) {
                    return response.json().then((data) => {
                        throw new Error(data.error || "Не удалось обработать заявку");
                    });
                }
                return response.json();
            })
            .then((data) => {
                // Обновляем данные в currentRequests
                const index = currentRequests.findIndex((r) => r.id === currentRequestId);
                if (index !== -1) {
                    currentRequests[index] = data.request;
                }
                
                // Обновляем отображение
                applyFilters();
                closeRequestDrawer();
            })
            .catch((error) => {
                alert("Ошибка: " + error.message);
                markBtn.disabled = false;
                markBtn.innerHTML = `
                    <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                        <path d="M20 6 9 17l-5-5"/>
                    </svg>
                    Отметить обработанной
                `;
            });
    };

    window.createStudentFromRequest = function () {
        if (!currentRequestId) {
            return;
        }

        const request = currentRequests.find((r) => r.id === currentRequestId);

        if (!request) {
            return;
        }

        const childName = splitFullName(request.child_fio);
        const parentName = splitFullName(request.parent_fio);
        studentSourceRequestId = request.id;
        setStudentFormAlert("");

        document.getElementById("studentLastName").value = childName.lastName;
        document.getElementById("studentFirstName").value = childName.firstName;
        document.getElementById("studentBirthDate").value = "";
        document.getElementById("studentSex").value = "";
        document.getElementById("studentPhone").value = "";
        document.getElementById("studentEmail").value = "";
        document.getElementById("studentCity").value = "";
        document.getElementById("studentCountry").value = "Россия";
        document.getElementById("studentSource").value = request.source || "";
        document.getElementById("parentLastName").value = parentName.lastName;
        document.getElementById("parentFirstName").value = parentName.firstName;
        document.getElementById("parentPhone").value = request.phone || "";
        document.getElementById("parentEmail").value = request.email || "";
        document.getElementById("studentUsername").value = makeUsername(request.child_fio);
        document.getElementById("studentPassword").value = `student${request.id}`;
        document.getElementById("studentRequestPreview").innerHTML = `
            <strong>${escapeHtml(request.child_fio)}</strong>
            Родитель: ${escapeHtml(request.parent_fio)}<br>
            Телефон родителя: ${escapeHtml(request.phone)}<br>
            Курсы: ${escapeHtml(request.courses_display || "Не указаны")}
        `;

        document.getElementById("studentDrawer").classList.add("is-open");
    };

    function submitStudentForm(event) {
        event.preventDefault();

        if (!studentSourceRequestId) {
            return;
        }

        const submitBtn = document.getElementById("studentSubmitBtn");
        const payload = {
            last_name: document.getElementById("studentLastName").value.trim(),
            first_name: document.getElementById("studentFirstName").value.trim(),
            birth_date: document.getElementById("studentBirthDate").value.trim() || null,
            sex: document.getElementById("studentSex").value.trim(),
            phone: document.getElementById("studentPhone").value.trim() || null,
            email: document.getElementById("studentEmail").value.trim(),
            city: document.getElementById("studentCity").value.trim(),
            country: document.getElementById("studentCountry").value.trim(),
            source: document.getElementById("studentSource").value.trim() || null,
            parent_last_name: document.getElementById("parentLastName").value.trim(),
            parent_first_name: document.getElementById("parentFirstName").value.trim(),
            parent_phone: document.getElementById("parentPhone").value.trim(),
            parent_email: document.getElementById("parentEmail").value.trim(),
            username: document.getElementById("studentUsername").value.trim(),
            password: document.getElementById("studentPassword").value.trim(),
        };

        setStudentFormAlert("");
        submitBtn.disabled = true;
        submitBtn.innerHTML = "Сохранение...";

        fetch(`/api/v1/participant-requests/${studentSourceRequestId}/create-student/`, {
            method: "POST",
            headers: {
                ...headersWithCsrf,
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        })
            .then((response) => {
                if (!response.ok) {
                    return response.json().then((data) => {
                        throw new Error(data.error || "Не удалось создать ученика");
                    });
                }
                return response.json();
            })
            .then((data) => {
                const index = currentRequests.findIndex((r) => r.id === studentSourceRequestId);

                if (index !== -1) {
                    currentRequests[index] = data.request;
                }

                showToast(
                    "Ученик успешно создан",
                    `Логин: ${data.student.username}. ${data.parent_created ? 'Родитель также создан.' : 'Родитель уже существовал.'}`,
                    true
                );

                updateSidebarRequestsCount();
                applyFilters();
                closeStudentDrawer();
                closeRequestDrawer();
            })
            .catch((error) => {
                showToast("Ошибка создания ученика", error.message, false);
                setStudentFormAlert(error.message);
            })
            .finally(() => {
                submitBtn.disabled = false;
                submitBtn.innerHTML = `
                    <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path d="M12 5v14M5 12h14"/>
                    </svg>
                    Сохранить ученика
                `;
            });
    }

    window.toggleView = function () {
        currentView = currentView === "table" ? "cards" : "table";

        const tableWrapper = document.getElementById("requestsTableWrapper");
        const cardsGrid = document.getElementById("requestsCardsGrid");

        if (currentView === "table") {
            tableWrapper.style.display = "block";
            cardsGrid.style.display = "none";
        } else {
            tableWrapper.style.display = "none";
            cardsGrid.style.display = "grid";
        }

        renderRequests(currentRequests);
    };

    window.refreshRequests = function () {
        loadRequests();
    };

    window.exportRequests = function () {
        alert("Экспорт в Excel будет реализован позже.");
    };

    document.addEventListener("DOMContentLoaded", () => {
        loadRequests();

        document.getElementById("requestsSearch").addEventListener("input", applyFilters);
        document.getElementById("requestsStatusFilter").addEventListener("change", applyFilters);
        document.getElementById("requestsSortFilter").addEventListener("change", applyFilters);
        document.getElementById("studentFromRequestForm").addEventListener("submit", submitStudentForm);

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeStudentDrawer();
            }
        });
    });
})();
