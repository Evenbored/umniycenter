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

    let currentCourses = [];
    let selectedCourseId = null;

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
        return ((parts[0]?.[0] || "К") + (parts[1]?.[0] || "")).toUpperCase();
    }

    function setCourseEditAlert(message, isSuccess) {
        const alert = document.getElementById("courseEditAlert");
        alert.textContent = message || "";
        alert.hidden = !message;
        alert.classList.toggle("is-success", Boolean(isSuccess));
    }

    function setCreateCourseAlert(message, isSuccess) {
        const alert = document.getElementById("createCourseAlert");
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

        return messages.join(" ") || "Не удалось сохранить курс";
    }

    function getCourseById(courseId) {
        return currentCourses.find((course) => course.id === courseId);
    }

    function updateCourseInState(updatedCourse) {
        const index = currentCourses.findIndex((course) => course.id === updatedCourse.id);
        if (index !== -1) {
            currentCourses[index] = updatedCourse;
        }
    }

    function removeCourseFromState(courseId) {
        currentCourses = currentCourses.filter((course) => course.id !== courseId);
    }

    function renderCourses(courses) {
        const tbody = document.getElementById("coursesTableBody");
        document.getElementById("coursesCount").textContent = courses.length;

        if (!courses.length) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="3" class="crm-table-empty">Курсы не найдены. Попробуйте изменить фильтры.</td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = courses.map((course) => `
            <tr onclick="openCourseDetailsDrawer(${course.id})">
                <td>
                    <div class="crm-table-name">${escapeHtml(course.name)}</div>
                </td>
                <td><span class="crm-table-meta">ID ${course.id}</span></td>
                <td>
                    <button class="crm-table-action-btn" type="button" onclick="event.stopPropagation(); openCourseDetailsDrawer(${course.id})" title="Открыть курс">
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
        const search = document.getElementById("coursesSearch").value.trim().toLowerCase();
        const sort = document.getElementById("coursesSortFilter").value;

        let filtered = [...currentCourses];

        if (search) {
            filtered = filtered.filter((course) => 
                course.name.toLowerCase().includes(search)
            );
        }

        filtered.sort((a, b) => {
            if (sort === "name_za") {
                return b.name.localeCompare(a.name, "ru");
            }
            return a.name.localeCompare(b.name, "ru");
        });

        renderCourses(filtered);
    }

    function loadCourses() {
        const tbody = document.getElementById("coursesTableBody");
        tbody.innerHTML = `
            <tr>
                <td colspan="3" class="crm-table-loading">
                    <div class="crm-spinner"></div>
                    <span>Загрузка курсов...</span>
                </td>
            </tr>
        `;

        fetch("/api/v1/courses/", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load courses");
                }
                return response.json();
            })
            .then((data) => {
                currentCourses = data;
                applyFilters();
            })
            .catch(() => {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="3" class="crm-table-empty">Не удалось загрузить курсы. Попробуйте обновить страницу.</td>
                    </tr>
                `;
            });
    }

    function setCourseEditMode(isEditing) {
        document.getElementById("courseEditForm").hidden = !isEditing;
        document.getElementById("courseEditCancelBtn").hidden = !isEditing;
        document.getElementById("courseEditSaveBtn").hidden = !isEditing;
        document.getElementById("courseEditToggleBtn").hidden = isEditing;
        document.getElementById("courseDeleteBtn").hidden = isEditing;

        if (!isEditing) {
            setCourseEditAlert("");
        }
    }

    function fillCourseEditForm(course) {
        document.getElementById("courseEditName").value = course.name || "";
    }

    window.openCourseDetailsDrawer = function (courseId) {
        const course = getCourseById(courseId);

        if (!course) {
            return;
        }

        selectedCourseId = course.id;

        document.getElementById("courseDrawerTitle").textContent = `Курс #${course.id}`;
        document.getElementById("courseDrawerSubtitle").textContent = course.name;
        document.getElementById("courseDrawerName").textContent = course.name;
        document.getElementById("courseDrawerInitials").textContent = getInitials(course.name);
        document.getElementById("courseDrawerId").textContent = course.id;
        document.getElementById("courseDrawerNameInfo").textContent = course.name;
        fillCourseEditForm(course);
        setCourseEditMode(false);

        document.getElementById("courseDetailsDrawer").classList.add("is-open");
    };

    window.closeCourseDetailsDrawer = function () {
        document.getElementById("courseDetailsDrawer").classList.remove("is-open");
        selectedCourseId = null;
    };

    window.showCourseEditForm = function () {
        setCourseEditMode(true);
    };

    window.cancelCourseEdit = function () {
        const course = getCourseById(selectedCourseId);
        if (course) {
            fillCourseEditForm(course);
        }
        setCourseEditMode(false);
    };

    function saveCourseEdit(event) {
        event.preventDefault();

        if (!selectedCourseId) {
            return;
        }

        const name = document.getElementById("courseEditName").value.trim();

        if (!name) {
            setCourseEditAlert("Название курса обязательно");
            return;
        }

        const submitBtn = document.getElementById("courseEditSaveBtn");
        submitBtn.disabled = true;
        submitBtn.textContent = "Сохранение...";

        const payload = { name };

        fetch(`/api/v1/courses/${selectedCourseId}/`, {
            method: "PATCH",
            headers: headersWithCsrf,
            body: JSON.stringify(payload),
        })
            .then((response) => response.text().then((text) => {
                const data = text ? JSON.parse(text) : {};
                return { ok: response.ok, data };
            }))
            .then(({ ok, data }) => {
                if (ok) {
                    setCourseEditAlert("Курс успешно обновлен", true);
                    updateCourseInState(data.course);
                    applyFilters();
                    setTimeout(() => {
                        setCourseEditMode(false);
                        openCourseDetailsDrawer(selectedCourseId);
                    }, 1000);
                } else {
                    setCourseEditAlert(getErrorMessage(data));
                }
            })
            .catch(() => {
                setCourseEditAlert("Не удалось обновить курс. Попробуйте позже.");
            })
            .finally(() => {
                submitBtn.disabled = false;
                submitBtn.textContent = "Сохранить";
            });
    }

    window.deleteCourse = function () {
        if (!selectedCourseId) {
            return;
        }

        if (!confirm("Вы уверены, что хотите удалить этот курс? Это действие нельзя отменить.")) {
            return;
        }

        fetch(`/api/v1/courses/${selectedCourseId}/delete/`, {
            method: "DELETE",
            headers: headersWithCsrf,
        })
            .then((response) => response.text().then((text) => {
                const data = text ? JSON.parse(text) : {};
                return { ok: response.ok, data };
            }))
            .then(({ ok, data }) => {
                if (ok) {
                    removeCourseFromState(selectedCourseId);
                    applyFilters();
                    closeCourseDetailsDrawer();
                    alert("Курс успешно удален");
                } else {
                    alert(getErrorMessage(data));
                }
            })
            .catch(() => {
                alert("Не удалось удалить курс. Попробуйте позже.");
            });
    };

    window.openCreateCourseDrawer = function () {
        setCreateCourseAlert("");
        document.getElementById("createCourseForm").reset();
        document.getElementById("createCourseDrawer").classList.add("is-open");
    };

    window.closeCreateCourseDrawer = function () {
        document.getElementById("createCourseDrawer").classList.remove("is-open");
        document.getElementById("createCourseForm").reset();
        setCreateCourseAlert("");
    };

    function createCourse(event) {
        event.preventDefault();

        const name = document.getElementById("createCourseName").value.trim();

        if (!name) {
            setCreateCourseAlert("Название курса обязательно");
            return;
        }

        const submitBtn = document.getElementById("createCourseSubmitBtn");
        submitBtn.disabled = true;
        submitBtn.textContent = "Сохранение...";

        const payload = { name };

        fetch("/api/v1/courses/create/", {
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
                    setCreateCourseAlert("Курс успешно создан", true);
                    setTimeout(() => {
                        closeCreateCourseDrawer();
                        loadCourses();
                    }, 1000);
                } else {
                    setCreateCourseAlert(getErrorMessage(data));
                }
            })
            .catch(() => {
                setCreateCourseAlert("Не удалось создать курс. Попробуйте позже.");
            })
            .finally(() => {
                submitBtn.disabled = false;
                submitBtn.textContent = "Сохранить курс";
            });
    }

    window.refreshCourses = function () {
        loadCourses();
    };

    document.addEventListener("DOMContentLoaded", () => {
        loadCourses();

        document.getElementById("coursesSearch").addEventListener("input", applyFilters);
        document.getElementById("coursesSortFilter").addEventListener("change", applyFilters);
        document.getElementById("courseEditForm").addEventListener("submit", saveCourseEdit);
        document.getElementById("createCourseForm").addEventListener("submit", createCourse);

        const openCreateBtn = document.getElementById("openCreateCourseBtn");
        if (openCreateBtn) {
            openCreateBtn.addEventListener("click", openCreateCourseDrawer);
        }
    });
})();
