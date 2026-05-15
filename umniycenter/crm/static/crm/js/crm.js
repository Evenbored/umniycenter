(function () {
    function initSidebar() {
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

    document.addEventListener("DOMContentLoaded", initSidebar);
})();
