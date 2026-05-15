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

    let currentTariffs = [];
    let currentCourses = [];
    let selectedTariffId = null;

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatMoney(value) {
        return Number(value || 0).toLocaleString("ru-RU", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function setFormAlert(message, isSuccess) {
        const alert = document.getElementById("tariffFormAlert");
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
        }).join(" ") || "Не удалось сохранить тариф";
    }

    function renderCourseOptions() {
        const filter = document.getElementById("tariffsCourseFilter");
        const formSelect = document.getElementById("tariffCourse");
        const options = currentCourses.map((course) => (
            `<option value="${course.id}">${escapeHtml(course.name)}</option>`
        )).join("");

        filter.innerHTML = '<option value="">Все курсы</option>' + options;
        formSelect.innerHTML = '<option value="">Выберите курс</option>' + options;
    }

    function renderTariffs(tariffs) {
        const tbody = document.getElementById("tariffsTableBody");
        document.getElementById("tariffsCount").textContent = tariffs.length;

        if (!tariffs.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="crm-table-empty">Тарифы не найдены. Измените фильтры или создайте новый тариф.</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = tariffs.map((tariff) => `
            <tr onclick="openTariffDrawer(${tariff.id})">
                <td>
                    <div class="crm-table-name">${escapeHtml(tariff.name)}</div>
                    ${tariff.description ? `<span class="crm-table-meta">${escapeHtml(tariff.description)}</span>` : ''}
                </td>
                <td><span class="crm-group-chip">${escapeHtml(tariff.course_name)}</span></td>
                <td><strong>${tariff.lessons_count}</strong></td>
                <td>${tariff.validity_days} дней</td>
                <td><span class="crm-tariff-price">${formatMoney(tariff.price)} ₽</span></td>
                <td><span class="crm-tariff-chip">${escapeHtml(tariff.subscription_type_display || tariff.subscription_type || 'Групповой')}</span></td>
                <td><span class="crm-tariff-chip">${tariff.is_trial ? 'Пробный' : 'Платный'}</span></td>
                <td>${tariff.is_active ? '<span class="crm-status-badge crm-status-badge--active">Активен</span>' : '<span class="crm-status-badge crm-status-badge--archive">Архив</span>'}</td>
                <td>
                    <button class="crm-table-action-btn" type="button" onclick="event.stopPropagation(); openTariffDrawer(${tariff.id})" title="Редактировать">
                        <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                            <path d="M12 20h9"/>
                            <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>
                        </svg>
                    </button>
                </td>
            </tr>
        `).join("");
    }

    function applyFilters() {
        const search = document.getElementById("tariffsSearch").value.trim().toLowerCase();
        const courseId = document.getElementById("tariffsCourseFilter").value;
        const status = document.getElementById("tariffsStatusFilter").value;
        const type = document.getElementById("tariffsTypeFilter").value;
        const trialType = document.getElementById("tariffsTrialFilter").value;

        let filtered = [...currentTariffs];

        if (search) {
            filtered = filtered.filter((tariff) => (
                [tariff.name, tariff.course_name, tariff.description].join(" ").toLowerCase().includes(search)
            ));
        }

        if (courseId) {
            filtered = filtered.filter((tariff) => String(tariff.course) === courseId);
        }

        if (status) {
            filtered = filtered.filter((tariff) => String(tariff.is_active) === status);
        }

        if (type) {
            filtered = filtered.filter((tariff) => tariff.subscription_type === type);
        }

        if (trialType === "trial") {
            filtered = filtered.filter((tariff) => tariff.is_trial);
        } else if (trialType === "paid") {
            filtered = filtered.filter((tariff) => !tariff.is_trial);
        }

        renderTariffs(filtered);
    }

    function loadTariffs() {
        const tbody = document.getElementById("tariffsTableBody");
        tbody.innerHTML = `
            <tr>
                    <td colspan="9" class="crm-table-loading">
                    <div class="crm-spinner"></div>
                    <span>Загрузка тарифов...</span>
                </td>
            </tr>
        `;

        fetch("/api/v1/subscriptions/tariffs/", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load tariffs");
                }
                return response.json();
            })
            .then((data) => {
                currentTariffs = data;
                applyFilters();
            })
            .catch(() => {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="9" class="crm-table-empty">Не удалось загрузить тарифы. Попробуйте обновить страницу.</td>
                    </tr>
                `;
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
                renderCourseOptions();
            })
            .catch(() => {
                currentCourses = [];
            });
    }

    function fillTariffForm(tariff) {
        document.getElementById("tariffName").value = tariff?.name || "";
        document.getElementById("tariffCourse").value = tariff?.course || "";
        document.getElementById("tariffSubscriptionType").value = tariff?.subscription_type || "group";
        document.getElementById("tariffLessonsCount").value = tariff?.lessons_count || "";
        document.getElementById("tariffValidityDays").value = tariff?.validity_days || "";
        document.getElementById("tariffPrice").value = tariff?.price || "0.00";
        document.getElementById("tariffIsTrial").checked = Boolean(tariff?.is_trial);
        document.getElementById("tariffIsActive").checked = tariff ? Boolean(tariff.is_active) : true;
        document.getElementById("tariffDescription").value = tariff?.description || "";
    }

    window.openTariffDrawer = function (tariffId) {
        selectedTariffId = tariffId || null;
        const tariff = selectedTariffId ? currentTariffs.find((item) => item.id === selectedTariffId) : null;

        document.getElementById("tariffDrawerTitle").textContent = tariff ? "Редактировать тариф" : "Создать тариф";
        document.getElementById("tariffDrawerSubtitle").textContent = tariff ? `${tariff.course_name} · ${tariff.lessons_count} занятий` : "Заполните параметры тарифа";
        document.getElementById("tariffSubmitBtn").textContent = tariff ? "Сохранить" : "Создать";
        setFormAlert("");
        fillTariffForm(tariff);

        document.getElementById("tariffDrawer").classList.add("is-open");
    };

    window.closeTariffDrawer = function () {
        document.getElementById("tariffDrawer").classList.remove("is-open");
        selectedTariffId = null;
        setFormAlert("");
        document.getElementById("tariffForm").reset();
    };

    function saveTariff(event) {
        event.preventDefault();
        setFormAlert("");
        document.getElementById("tariffSubmitBtn").disabled = true;

        const payload = {
            name: document.getElementById("tariffName").value.trim(),
            course: Number(document.getElementById("tariffCourse").value),
            subscription_type: document.getElementById("tariffSubscriptionType").value,
            lessons_count: Number(document.getElementById("tariffLessonsCount").value),
            validity_days: Number(document.getElementById("tariffValidityDays").value),
            price: document.getElementById("tariffPrice").value || "0.00",
            description: document.getElementById("tariffDescription").value.trim(),
            is_trial: document.getElementById("tariffIsTrial").checked,
            is_active: document.getElementById("tariffIsActive").checked,
        };

        const url = selectedTariffId ? `/api/v1/subscriptions/tariffs/${selectedTariffId}/` : "/api/v1/subscriptions/tariffs/create/";
        const method = selectedTariffId ? "PATCH" : "POST";

        fetch(url, {
            method,
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
            .then(() => {
                setFormAlert(selectedTariffId ? "Тариф сохранен" : "Тариф создан", true);
                loadTariffs();
                setTimeout(closeTariffDrawer, 600);
            })
            .catch((error) => {
                setFormAlert(error.message, false);
            })
            .finally(() => {
                document.getElementById("tariffSubmitBtn").disabled = false;
            });
    }

    window.refreshTariffs = function () {
        loadCourses();
        loadTariffs();
    };

    document.addEventListener("DOMContentLoaded", () => {
        loadCourses();
        loadTariffs();

        document.getElementById("tariffsSearch").addEventListener("input", applyFilters);
        document.getElementById("tariffsCourseFilter").addEventListener("change", applyFilters);
        document.getElementById("tariffsStatusFilter").addEventListener("change", applyFilters);
        document.getElementById("tariffsTypeFilter").addEventListener("change", applyFilters);
        document.getElementById("tariffsTrialFilter").addEventListener("change", applyFilters);
        document.getElementById("tariffForm").addEventListener("submit", saveTariff);

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeTariffDrawer();
            }
        });
    });
})();
