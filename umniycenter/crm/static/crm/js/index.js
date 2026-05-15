(function () {
    const headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    };

    // Универсальная функция для обновления текста (как в dashboard.js)
    function setText(selector, value) {
        document.querySelectorAll(selector).forEach((node) => {
            node.textContent = value ?? 0;
        });
    }

    // Загрузка счетчика заявок (только НОВЫЕ, непросмотренные)
    function loadRequestsCount() {
        fetch("/api/v1/participant-requests/?is_processed=false", { headers })
            .then((response) => {
                if (!response.ok) throw new Error("Failed to load requests count");
                return response.json();
            })
            .then((data) => {
                // Считаем только непросмотренные заявки (checked=false)
                const newRequests = data.filter(request => !request.checked);
                const count = newRequests.length || 0;
                setText('[data-nav-count="requests"]', count);
            })
            .catch((err) => {
                console.error("Failed to load requests count:", err);
            });
    }

    // Загрузка счетчика студентов (ВСЕ ученики)
    function loadStudentsCount() {
        fetch("/api/v1/students/count/", { headers })
            .then((response) => {
                if (!response.ok) throw new Error("Failed to load students count");
                return response.json();
            })
            .then((data) => {
                setText('[data-nav-count="students"]', data.count);
            })
            .catch((err) => {
                console.error("Failed to load students count:", err);
            });
    }

    // Загрузка счетчика групп (ВСЕ группы)
    function loadGroupsCount() {
        fetch("/api/v1/groups/count/", { headers })
            .then((response) => {
                if (!response.ok) throw new Error("Failed to load groups count");
                return response.json();
            })
            .then((data) => {
                setText('[data-nav-count="groups"]', data.count);
            })
            .catch((err) => {
                console.error("Failed to load groups count:", err);
            });
    }

    // Загрузка всех счетчиков при загрузке страницы
    document.addEventListener("DOMContentLoaded", () => {
        loadRequestsCount();
        loadStudentsCount();
        loadGroupsCount();
    });
})();
