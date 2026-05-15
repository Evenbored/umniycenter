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

    let currentPayments = [];
    let selectedPaymentId = null;

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatMoney(value) {
        return `${Number(value || 0).toLocaleString("ru-RU", { minimumFractionDigits: 0, maximumFractionDigits: 2 })} ₽`;
    }

    function formatDate(value) {
        if (!value) {
            return "-";
        }
        return new Date(value).toLocaleString("ru-RU", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    function formatShortDate(value) {
        if (!value) {
            return "-";
        }
        return new Date(value).toLocaleDateString("ru-RU");
    }

    function jsonOrError(response) {
        return response.text().then((text) => {
            const data = text ? JSON.parse(text) : {};
            return { ok: response.ok, data };
        }).catch(() => ({ ok: false, data: { error: "Сервер вернул некорректный ответ" } }));
    }

    function getStatusClass(status) {
        if (status === "completed") {
            return "active";
        }
        if (status === "pending") {
            return "archive";
        }
        return "archive";
    }

    function getStatusBadge(payment) {
        return `<span class="crm-status-badge crm-status-badge--${getStatusClass(payment.status)}">${escapeHtml(payment.status_display || payment.status)}</span>`;
    }

    function getPaymentById(paymentId) {
        return currentPayments.find((payment) => payment.id === paymentId);
    }

    function updatePaymentInState(updatedPayment) {
        const index = currentPayments.findIndex((payment) => payment.id === updatedPayment.id);
        if (index !== -1) {
            currentPayments[index] = updatedPayment;
        }
    }

    function updateStats(payments) {
        document.getElementById("paymentsCount").textContent = payments.length;
        document.querySelectorAll('[data-nav-count="payments"]').forEach((item) => {
            item.textContent = currentPayments.length;
        });
        const completedAmount = payments
            .filter((payment) => payment.status === "completed")
            .reduce((sum, payment) => sum + Number(payment.amount || 0), 0);
        document.getElementById("paymentsCompletedAmount").textContent = formatMoney(completedAmount);
        document.getElementById("paymentsPendingCount").textContent = payments.filter((payment) => payment.status === "pending").length;
        document.getElementById("paymentsProblemCount").textContent = payments.filter((payment) => ["failed", "canceled", "refunded"].includes(payment.status)).length;
    }

    function renderPayments(payments) {
        const tbody = document.getElementById("paymentsTableBody");
        updateStats(payments);

        if (!payments.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="crm-table-empty">Платежи не найдены. Попробуйте изменить фильтры.</td></tr>';
            return;
        }

        tbody.innerHTML = payments.map((payment) => {
            const sub = payment.subscription_info || {};
            return `
                <tr onclick="openPaymentDetailsDrawer(${payment.id})">
                    <td>
                        <div class="crm-table-name">Платеж #${payment.id}</div>
                        <span class="crm-table-meta">${escapeHtml(payment.transaction_id || payment.yookassa_payment_id || 'Без ID транзакции')}</span>
                    </td>
                    <td><strong>${formatMoney(payment.amount)}</strong></td>
                    <td>
                        <div>${escapeHtml(payment.parent_name || '-')}</div>
                        <span class="crm-table-meta">${escapeHtml(payment.parent_phone || payment.parent_email || '-')}</span>
                    </td>
                    <td>
                        <div>${escapeHtml(sub.student_name || '-')}</div>
                        <span class="crm-table-meta">${escapeHtml(sub.tariff_name || '-')} · ${escapeHtml(sub.course_name || '-')}</span>
                    </td>
                    <td>${escapeHtml(payment.payment_method_display || payment.payment_method)}</td>
                    <td>${getStatusBadge(payment)}</td>
                    <td>${formatDate(payment.created_at)}</td>
                    <td>
                        <button class="crm-table-action-btn" type="button" onclick="event.stopPropagation(); openPaymentDetailsDrawer(${payment.id})" title="Открыть платеж">
                            <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                <circle cx="12" cy="12" r="3"/>
                            </svg>
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
    }

    function applyFilters() {
        const search = document.getElementById("paymentsSearch").value.trim().toLowerCase();
        const status = document.getElementById("paymentsStatusFilter").value;
        const method = document.getElementById("paymentsMethodFilter").value;
        const sort = document.getElementById("paymentsSortFilter").value;
        let filtered = [...currentPayments];

        if (search) {
            filtered = filtered.filter((payment) => {
                const sub = payment.subscription_info || {};
                const haystack = [
                    payment.id,
                    payment.parent_name,
                    payment.parent_phone,
                    payment.parent_email,
                    payment.transaction_id,
                    payment.yookassa_payment_id,
                    sub.student_name,
                    sub.tariff_name,
                    sub.course_name,
                ].join(" ").toLowerCase();
                return haystack.includes(search);
            });
        }

        if (status) {
            filtered = filtered.filter((payment) => payment.status === status);
        }

        if (method) {
            filtered = filtered.filter((payment) => payment.payment_method === method);
        }

        filtered.sort((a, b) => {
            if (sort === "date_old") {
                return new Date(a.created_at) - new Date(b.created_at);
            }
            if (sort === "amount_desc") {
                return Number(b.amount || 0) - Number(a.amount || 0);
            }
            if (sort === "amount_asc") {
                return Number(a.amount || 0) - Number(b.amount || 0);
            }
            return new Date(b.created_at) - new Date(a.created_at);
        });

        renderPayments(filtered);
    }

    function loadPayments() {
        const tbody = document.getElementById("paymentsTableBody");
        tbody.innerHTML = '<tr><td colspan="8" class="crm-table-loading"><div class="crm-spinner"></div><span>Загрузка платежей...</span></td></tr>';
        fetch("/api/v1/subscriptions/payments/", { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load payments");
                }
                return response.json();
            })
            .then((data) => {
                currentPayments = data;
                applyFilters();
            })
            .catch(() => {
                tbody.innerHTML = '<tr><td colspan="8" class="crm-table-empty">Не удалось загрузить платежи. Попробуйте обновить страницу.</td></tr>';
            });
    }

    window.openPaymentDetailsDrawer = function (paymentId) {
        const payment = getPaymentById(paymentId);
        if (!payment) {
            return;
        }
        const sub = payment.subscription_info || {};
        selectedPaymentId = paymentId;
        document.getElementById("paymentDrawerTitle").textContent = `Платеж #${payment.id}`;
        document.getElementById("paymentDrawerSubtitle").textContent = payment.transaction_id || payment.yookassa_payment_id || "Без ID транзакции";
        document.getElementById("paymentDrawerAmount").textContent = formatMoney(payment.amount);
        document.getElementById("paymentDrawerStatus").innerHTML = getStatusBadge(payment);
        document.getElementById("paymentDrawerMethod").textContent = payment.payment_method_display || payment.payment_method || "-";
        document.getElementById("paymentDrawerCreated").textContent = formatDate(payment.created_at);
        document.getElementById("paymentDrawerPaid").textContent = formatDate(payment.paid_at);
        document.getElementById("paymentDrawerTransaction").textContent = payment.transaction_id || "-";
        document.getElementById("paymentDrawerParent").textContent = payment.parent_name || "-";
        document.getElementById("paymentDrawerParentContacts").textContent = payment.parent_phone || payment.parent_email || "-";
        document.getElementById("paymentDrawerStudent").textContent = sub.student_name || "-";
        document.getElementById("paymentDrawerCourse").textContent = sub.course_name || "-";
        document.getElementById("paymentDrawerTariff").textContent = sub.tariff_name || "-";
        document.getElementById("paymentDrawerSubscriptionStatus").textContent = sub.subscription_status || "-";
        document.getElementById("paymentDrawerLessons").textContent = `${sub.lessons_used ?? '-'} / ${sub.lessons_total ?? '-'} (осталось ${sub.lessons_remaining ?? '-'})`;
        document.getElementById("paymentDrawerPeriod").textContent = `${formatShortDate(sub.start_date)} - ${formatShortDate(sub.end_date)}`;
        document.getElementById("paymentDrawerOnlineSection").hidden = !payment.yookassa_payment_id && !payment.yookassa_payment_url;
        document.getElementById("paymentDrawerYookassaId").textContent = payment.yookassa_payment_id || "-";
        document.getElementById("paymentDrawerYookassaUrl").innerHTML = payment.yookassa_payment_url
            ? `<a href="${escapeHtml(payment.yookassa_payment_url)}" target="_blank" rel="noopener">Открыть ссылку оплаты</a>`
            : "-";
        document.getElementById("paymentDrawerNotes").innerHTML = `
            <strong>Примечания:</strong> ${escapeHtml(payment.notes || '-')}<br>
            <strong>Ошибка:</strong> ${escapeHtml(payment.error_message || '-')}
        `;
        const canConfirm = payment.status === "pending" && payment.payment_method !== "online";
        const canCancel = (payment.status === "pending" && payment.payment_method !== "online") || payment.status === "failed";
        document.getElementById("paymentConfirmBtn").hidden = !canConfirm;
        document.getElementById("paymentCancelBtn").hidden = !canCancel;
        document.getElementById("paymentDetailsDrawer").classList.add("is-open");
    };

    window.closePaymentDetailsDrawer = function () {
        document.getElementById("paymentDetailsDrawer").classList.remove("is-open");
        selectedPaymentId = null;
    };

    window.confirmPaymentFromDrawer = function () {
        if (!selectedPaymentId || !confirm("Подтвердить получение оплаты и активировать подписку?")) {
            return;
        }
        fetch(`/api/v1/subscriptions/payments/${selectedPaymentId}/confirm/`, {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify({}),
        })
            .then(jsonOrError)
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(data.error || "Не удалось подтвердить оплату");
                }
                updatePaymentInState(data.payment);
                applyFilters();
                window.openPaymentDetailsDrawer(data.payment.id);
            })
            .catch((error) => alert(error.message));
    };

    window.cancelPaymentFromDrawer = function () {
        if (!selectedPaymentId) {
            return;
        }
        const reason = prompt("Причина отмены платежа", "Оплата не поступила");
        if (reason === null) {
            return;
        }
        fetch(`/api/v1/subscriptions/payments/${selectedPaymentId}/cancel/`, {
            method: "POST",
            headers: headersWithCsrf,
            body: JSON.stringify({ reason }),
        })
            .then(jsonOrError)
            .then(({ ok, data }) => {
                if (!ok) {
                    throw new Error(data.error || "Не удалось отменить платеж");
                }
                updatePaymentInState(data.payment);
                applyFilters();
                window.openPaymentDetailsDrawer(data.payment.id);
            })
            .catch((error) => alert(error.message));
    };

    window.refreshPayments = function () {
        loadPayments();
    };

    window.exportPayments = function () {
        alert("Экспорт платежей будет реализован позже.");
    };

    document.addEventListener("DOMContentLoaded", () => {
        loadPayments();
        document.getElementById("paymentsSearch").addEventListener("input", applyFilters);
        document.getElementById("paymentsStatusFilter").addEventListener("change", applyFilters);
        document.getElementById("paymentsMethodFilter").addEventListener("change", applyFilters);
        document.getElementById("paymentsSortFilter").addEventListener("change", applyFilters);
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                closePaymentDetailsDrawer();
            }
        });
    });
})();
