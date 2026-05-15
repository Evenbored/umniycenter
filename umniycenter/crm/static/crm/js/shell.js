(function () {
    function toggleSidebar() {
        const toggle = document.querySelector("[data-sidebar-toggle]");

        if (!toggle) {
            return;
        }

        toggle.addEventListener("click", () => {
            document.body.classList.toggle("crm-sidebar-open");
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                document.body.classList.remove("crm-sidebar-open");
            }
        });
    }

    function initNavDropdowns() {
        document.querySelectorAll(".crm-nav__item--dropdown").forEach((item) => {
            item.addEventListener("click", () => {
                item.closest(".crm-nav__dropdown")?.classList.toggle("is-open");
            });
        });
    }

    function initUserMenu() {
        const userMenu = document.querySelector('.crm-user-menu');
        const userMenuButton = userMenu?.querySelector('.crm-admin-chip');
        const userMenuDropdown = userMenu?.querySelector('.crm-user-menu__dropdown');

        if (!userMenuButton || !userMenuDropdown) {
            return;
        }

        userMenuButton.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = userMenu.classList.toggle('is-open');
            userMenuButton.setAttribute('aria-expanded', isOpen);
            userMenuDropdown.hidden = !isOpen;
        });

        document.addEventListener('click', (e) => {
            if (!userMenu.contains(e.target)) {
                userMenu.classList.remove('is-open');
                userMenuButton.setAttribute('aria-expanded', 'false');
                userMenuDropdown.hidden = true;
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && userMenu.classList.contains('is-open')) {
                userMenu.classList.remove('is-open');
                userMenuButton.setAttribute('aria-expanded', 'false');
                userMenuDropdown.hidden = true;
                userMenuButton.focus();
            }
        });
    }

    function ensureToastContainer() {
        let container = document.getElementById('crmToastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'crmToastContainer';
            container.className = 'crm-toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    function showToast({ type = 'info', title = '', message = '' } = {}) {
        const container = ensureToastContainer();
        const toast = document.createElement('div');
        toast.className = `crm-toast crm-toast--${type}`;
        const safeTitle = String(title ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
        const safeMessage = String(message ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');

        toast.innerHTML = `
            <div class="crm-toast__content">
                <strong class="crm-toast__title">${safeTitle}</strong>
                <div class="crm-toast__message">${safeMessage}</div>
            </div>
            <button type="button" class="crm-toast__close" aria-label="Закрыть уведомление">×</button>
        `;

        toast.querySelector('.crm-toast__close')?.addEventListener('click', () => toast.remove());
        container.appendChild(toast);

        requestAnimationFrame(() => toast.classList.add('is-visible'));
        window.setTimeout(() => {
            toast.classList.remove('is-visible');
            window.setTimeout(() => toast.remove(), 250);
        }, 4500);
    }

    function setText(selector, value) {
        document.querySelectorAll(selector).forEach((node) => {
            node.textContent = value ?? 0;
        });
    }

    function updateStats(stats = {}) {
        Object.entries(stats).forEach(([key, value]) => {
            setText(`[data-stat="${key}"]`, value);
        });

        setText('[data-nav-count="requests"]', stats.new_requests_count || 0);
        setText('[data-nav-count="students"]', stats.students_count || 0);
        setText('[data-nav-count="groups"]', stats.groups_count || 0);
        setText('[data-nav-count="payments"]', stats.payments_count || 0);
        setText('[data-nav-count="parents"]', stats.parents_count || 0);
        setText('[data-nav-count="teachers"]', stats.teachers_count || 0);
        setText('[data-nav-count="messages"]', stats.unread_messages_count || 0);
    }

    function loadNavStats() {
        fetch('/api/v1/dashboard/', {
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error('Failed to load CRM counters');
                }
                return response.json();
            })
            .then((data) => updateStats(data.stats || {}))
            .catch(() => {
                // Counters are non-critical; keep the page usable if the request fails.
            });
    }

    window.CRM = window.CRM || {};
    window.CRM.updateStats = updateStats;
    window.CRM.loadNavStats = loadNavStats;

    document.addEventListener("DOMContentLoaded", () => {
        toggleSidebar();
        initNavDropdowns();
        initUserMenu();
        ensureToastContainer();
        loadNavStats();

        document.body.addEventListener('crm:toast', (event) => {
            showToast(event.detail || {});
        });

        document.body.addEventListener('crm:refresh-stats', loadNavStats);
    });
})();
