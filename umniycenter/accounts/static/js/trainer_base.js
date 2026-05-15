(function () {
    const apiHeaders = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    };

    function setText(selector, value) {
        document.querySelectorAll(selector).forEach((node) => {
            node.textContent = value || "";
        });
    }

    function formatLocation(user) {
        return [user.city, user.country].filter(Boolean).join(", ");
    }

    function loadCount(url, targetId) {
        const target = document.getElementById(targetId);

        if (!target) {
            return;
        }

        fetch(url, { headers: apiHeaders })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load count");
                }
                return response.json();
            })
            .then((data) => {
                target.textContent = data.count ?? "";
            })
            .catch(() => {
                target.textContent = "";
            });
    }

    function initUserMenu() {
        const menu = document.querySelector(".trainer-user-menu");

        if (!menu) {
            return;
        }

        const button = menu.querySelector(".trainer-user-menu__button");
        const dropdown = menu.querySelector(".trainer-user-menu__dropdown");

        if (!button || !dropdown) {
            return;
        }

        function closeMenu() {
            menu.classList.remove("is-open");
            button.setAttribute("aria-expanded", "false");
            dropdown.hidden = true;
        }

        function toggleMenu() {
            const shouldOpen = dropdown.hidden;
            menu.classList.toggle("is-open", shouldOpen);
            button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
            dropdown.hidden = !shouldOpen;
        }

        button.addEventListener("click", toggleMenu);

        document.addEventListener("click", (event) => {
            if (!menu.contains(event.target)) {
                closeMenu();
            }
        });

        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closeMenu();
            }
        });

        fetch(menu.dataset.currentUserApi, { headers: apiHeaders })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load current user");
                }
                return response.json();
            })
            .then((user) => {
                setText("[data-user-name]", user.display_name || user.username);
                setText("[data-user-role]", user.role_display);
                setText("[data-user-email]", user.email);
                setText("[data-user-phone]", user.phone);
                setText("[data-user-location]", formatLocation(user));
                setText("[data-user-initials]", user.initials);
            })
            .catch(() => {
                // Server-rendered values remain visible if the API is temporarily unavailable.
            });
    }

    document.addEventListener("DOMContentLoaded", () => {
        loadCount("/api/v1/students/count/", "students-count");
        loadCount("/api/v1/groups/count/", "groups-count");
        initUserMenu();
    });
})();
