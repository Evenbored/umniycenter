(function () {

    const headers = {
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    };

    // Global WebSocket for notifications
    let globalWs = null;
    let wsReconnectAttempts = 0;
    const maxWsReconnectAttempts = 5;

    // Calendar state
    let currentDate = new Date();
    let selectedDate = new Date();
    let latestDashboardRequest = 0;

    function padDatePart(value) {
        return String(value).padStart(2, '0');
    }

    function toApiDate(date) {
        return `${date.getFullYear()}-${padDatePart(date.getMonth() + 1)}-${padDatePart(date.getDate())}`;
    }

    function parseApiDate(value) {
        const [year, month, day] = String(value).split('-').map(Number);
        return new Date(year, month - 1, day);
    }

    function setText(selector, value) {
        document.querySelectorAll(selector).forEach((node) => {
            node.textContent = value ?? 0;
        });
    }

    function setDashboardLoading(isLoading) {
        document.body.classList.toggle('dashboard-is-loading', isLoading);
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Calendar functions
    function formatDate(date) {
        const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 
                       'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
        return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()}`;
    }

    function formatMonthYear(date) {
        const months = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 
                       'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
        return `${months[date.getMonth()]} ${date.getFullYear()}`;
    }

    function isSameDay(date1, date2) {
        return date1.getDate() === date2.getDate() &&
               date1.getMonth() === date2.getMonth() &&
               date1.getFullYear() === date2.getFullYear();
    }

    function renderCalendar() {
        const calendarGrid = document.getElementById('calendarGrid');
        const currentMonthEl = document.getElementById('currentMonth');
        const selectedDateDisplay = document.getElementById('selectedDateDisplay');

        if (!calendarGrid) return;

        currentMonthEl.textContent = formatMonthYear(currentDate);
        selectedDateDisplay.textContent = formatDate(selectedDate);

        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();
        
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const prevLastDay = new Date(year, month, 0);
        
        const firstDayOfWeek = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1;
        const lastDate = lastDay.getDate();
        const prevLastDate = prevLastDay.getDate();

        let html = '';
        
        // Day headers
        const dayHeaders = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
        dayHeaders.forEach(day => {
            html += `<div class="calendar-day-header">${day}</div>`;
        });

        // Previous month days
        for (let i = firstDayOfWeek; i > 0; i--) {
            const day = prevLastDate - i + 1;
            html += `<div class="calendar-day is-other-month">${day}</div>`;
        }

        // Current month days
        const today = new Date();
        for (let day = 1; day <= lastDate; day++) {
            const date = new Date(year, month, day);
            const isToday = isSameDay(date, today);
            const isSelected = isSameDay(date, selectedDate);
            
            let classes = 'calendar-day';
            if (isToday) classes += ' is-today';
            if (isSelected) classes += ' is-selected';
            
            html += `<div class="${classes}" data-date="${toApiDate(date)}">${day}</div>`;
        }

        // Next month days
        const remainingDays = 42 - (firstDayOfWeek + lastDate);
        for (let day = 1; day <= remainingDays; day++) {
            html += `<div class="calendar-day is-other-month">${day}</div>`;
        }

        calendarGrid.innerHTML = html;

        // Add click handlers
        calendarGrid.querySelectorAll('.calendar-day:not(.is-other-month)').forEach(dayEl => {
            dayEl.addEventListener('click', function() {
                const dateStr = this.getAttribute('data-date');
                if (dateStr) {
                    selectedDate = parseApiDate(dateStr);
                    renderCalendar();
                    updateSelectedDateTitles();
                    loadDashboardDataForDate(selectedDate);
                }
            });
        });
    }

    function updateSelectedDateTitles() {
        const formatted = formatDate(selectedDate);
        const titles = {
            dashboardSalesTitle: `Продажи за ${formatted}`,
            dashboardAttendanceTitle: `Посещения за ${formatted}`,
            dashboardBalanceTitle: `Баланс за ${formatted}`,
            dashboardGroupAttendanceTitle: `Посещения по группам за ${formatted}`,
        };

        Object.entries(titles).forEach(([id, text]) => {
            const element = document.getElementById(id);
            if (element) element.textContent = text;
        });

        const individualTitle = document.getElementById('dashboardIndividualAttendanceTitle');
        const countEl = individualTitle?.querySelector('.section-count');
        if (individualTitle) {
            individualTitle.textContent = `Посещения по индивидуальным занятиям за ${formatted} `;
            if (countEl) individualTitle.appendChild(countEl);
        }
    }

    function initCalendar() {
        const prevBtn = document.getElementById('prevMonth');
        const nextBtn = document.getElementById('nextMonth');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                currentDate.setMonth(currentDate.getMonth() - 1);
                renderCalendar();
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                currentDate.setMonth(currentDate.getMonth() + 1);
                renderCalendar();
            });
        }

        renderCalendar();
        updateSelectedDateTitles();
    }

    // Sales data functions
    function updateCircleProgress(circleId, value, total, offset = 0) {
        const circle = document.getElementById(circleId);
        if (!circle) return;

        const circumference = 2 * Math.PI * 80;
        const percentage = total > 0 ? (value / total) : 0;
        const dashArray = (percentage * circumference) + ' ' + circumference;
        const dashOffset = -offset * circumference;

        circle.setAttribute('stroke-dasharray', dashArray);
        circle.setAttribute('stroke-dashoffset', dashOffset);
    }

    function loadDashboardDataForDate(date) {
        const dateStr = toApiDate(date);
        const requestId = ++latestDashboardRequest;

        setDashboardLoading(true);
        updateSelectedDateTitles();
        
        fetch(`/api/v1/dashboard/?date=${dateStr}`, { headers })
            .then((response) => {
                if (!response.ok) {
                    throw new Error("Failed to load dashboard data");
                }
                return response.json();
            })
            .then((data) => {
                if (requestId !== latestDashboardRequest) return;
                updateSalesUI(data);
                updateStats(data.stats || {});
            })
            .catch((error) => {
                if (requestId !== latestDashboardRequest) return;
                console.error('Error loading dashboard data:', error);
                // Показываем нули при ошибке
                updateSalesUI({
                    subscriptions: { group: 0, individual: 0, total: 0 },
                    singleLessons: { group: 0, individual: 0, total: 0 },
                    products: { total: 0 },
                    attendance: { group: 0, individual: 0, total: 0 },
                    balance: {
                        income: { total: 0, breakdown: {} },
                        expense: { total: 0, breakdown: {} },
                        total: 0
                    },
                    groupAttendances: [],
                    individualAttendances: []
                });
            })
            .finally(() => {
                if (requestId === latestDashboardRequest) {
                    setDashboardLoading(false);
                }
            });
    }

    function updateSalesUI(data) {
        const subscriptions = data.subscriptions || { group: 0, individual: 0, total: 0 };
        const singleLessons = data.singleLessons || { group: 0, individual: 0, total: 0 };
        const products = data.products || { total: 0 };
        const attendance = data.attendance || { group: 0, individual: 0, total: 0 };

        // Update subscriptions
        setText('#subscriptionsTotal', subscriptions.total);
        setText('#subscriptionsGroup', subscriptions.group);
        setText('#subscriptionsIndividual', subscriptions.individual);
        
        if (subscriptions.total > 0) {
            const subGroupPercent = subscriptions.group / subscriptions.total;
            updateCircleProgress('subscriptionsGroupCircle', subscriptions.group, subscriptions.total, 0);
            updateCircleProgress('subscriptionsIndividualCircle', subscriptions.individual, subscriptions.total, subGroupPercent);
        } else {
            updateCircleProgress('subscriptionsGroupCircle', 0, 1, 0);
            updateCircleProgress('subscriptionsIndividualCircle', 0, 1, 0);
        }

        // Update single lessons
        setText('#singleLessonsTotal', singleLessons.total);
        setText('#singleLessonsGroup', singleLessons.group);
        setText('#singleLessonsIndividual', singleLessons.individual);
        
        if (singleLessons.total > 0) {
            const lessonGroupPercent = singleLessons.group / singleLessons.total;
            updateCircleProgress('singleLessonsGroupCircle', singleLessons.group, singleLessons.total, 0);
            updateCircleProgress('singleLessonsIndividualCircle', singleLessons.individual, singleLessons.total, lessonGroupPercent);
        } else {
            updateCircleProgress('singleLessonsGroupCircle', 0, 1, 0);
            updateCircleProgress('singleLessonsIndividualCircle', 0, 1, 0);
        }

        // Update products
        setText('#productsTotal', products.total);
        setText('#productsCount', products.total);
        if (products.total > 0) {
            updateCircleProgress('productsCircle', products.total, products.total, 0);
        } else {
            updateCircleProgress('productsCircle', 0, 1, 0);
        }

        // Update attendance
        setText('#attendanceTotal', attendance.total);
        setText('#attendanceGroup', attendance.group);
        setText('#attendanceIndividual', attendance.individual);
        
        if (attendance.total > 0) {
            const attGroupPercent = attendance.group / attendance.total;
            updateCircleProgress('attendanceGroupCircle', attendance.group, attendance.total, 0);
            updateCircleProgress('attendanceIndividualCircle', attendance.individual, attendance.total, attGroupPercent);
        } else {
            updateCircleProgress('attendanceGroupCircle', 0, 1, 0);
            updateCircleProgress('attendanceIndividualCircle', 0, 1, 0);
        }

        // Update balance
        updateBalanceUI(data.balance || {
            income: { total: 0, breakdown: {} },
            expense: { total: 0, breakdown: {} },
            total: 0
        });
        
        // Update group attendances list
        updateGroupAttendancesList(data.groupAttendances || []);
        
        // Update individual attendances list
        updateIndividualAttendancesList(data.individualAttendances || []);
    }

    function updateBalanceUI(balance) {
        const income = balance.income || { total: 0, breakdown: {} };
        const expense = balance.expense || { total: 0, breakdown: {} };
        const breakdown = income.breakdown || {};
        const expenseBreakdown = expense.breakdown || {};
        
        // Находим максимальное значение для расчета процентов
        const maxIncome = Math.max(
            breakdown.groupSubscriptions || 0,
            breakdown.groupSingle || 0,
            breakdown.individualSubscriptions || 0,
            breakdown.individualSingle || 0,
            breakdown.rentSubscriptions || 0,
            breakdown.rentSingle || 0,
            breakdown.products || 0,
            breakdown.accountTopup || 0
        );

        // Обновляем доходы
        updateBalanceItem('groupSubscriptions', breakdown.groupSubscriptions || 0, maxIncome);
        updateBalanceItem('groupSingle', breakdown.groupSingle || 0, maxIncome);
        updateBalanceItem('individualSubscriptions', breakdown.individualSubscriptions || 0, maxIncome);
        updateBalanceItem('individualSingle', breakdown.individualSingle || 0, maxIncome);
        updateBalanceItem('rentSubscriptions', breakdown.rentSubscriptions || 0, maxIncome);
        updateBalanceItem('rentSingle', breakdown.rentSingle || 0, maxIncome);
        updateBalanceItem('products', breakdown.products || 0, maxIncome);
        updateBalanceItem('accountTopup', breakdown.accountTopup || 0, maxIncome);

        // Обновляем расходы
        const maxExpense = Math.max(
            expenseBreakdown.accountWithdraw || 0,
            expenseBreakdown.refunds || 0
        );
        updateBalanceItem('accountWithdraw', expenseBreakdown.accountWithdraw || 0, maxExpense, true);
        updateBalanceItem('refunds', expenseBreakdown.refunds || 0, maxExpense, true);

        // Обновляем итоги
        const incomeTotalEl = document.querySelector('.balance-row:nth-child(1) .balance-total-amount');
        if (incomeTotalEl) {
            incomeTotalEl.textContent = formatCurrency(income.total || 0);
        }

        const expenseTotalEl = document.querySelector('.balance-row:nth-child(2) .balance-total-amount');
        if (expenseTotalEl) {
            expenseTotalEl.textContent = formatCurrency(expense.total || 0);
        }

        const finalTotalEl = document.querySelector('.balance-final-amount');
        if (finalTotalEl) {
            finalTotalEl.textContent = formatCurrency(balance.total || 0);
        }
    }

    function updateBalanceItem(key, amount, maxAmount, isExpense = false) {
        // Находим элементы по порядку в HTML
        const itemsMap = {
            'groupSubscriptions': 0,
            'groupSingle': 1,
            'individualSubscriptions': 2,
            'individualSingle': 3,
            'rentSubscriptions': 4,
            'rentSingle': 5,
            'products': 6,
            'accountTopup': 7,
            'accountWithdraw': 0,
            'refunds': 1
        };

        const section = isExpense ? 2 : 1;
        const itemIndex = itemsMap[key];
        const item = document.querySelector(`.balance-row:nth-child(${section}) .balance-item:nth-child(${itemIndex + 1})`);
        
        if (item) {
            const barFill = item.querySelector('.balance-item-bar-fill');
            const amountEl = item.querySelector('.balance-item-amount');
            
            if (barFill && maxAmount > 0) {
                const percent = (amount / maxAmount) * 100;
                barFill.style.width = percent + '%';
            } else if (barFill) {
                barFill.style.width = '0%';
            }
            
            if (amountEl) {
                amountEl.textContent = formatCurrency(amount);
            }
        }
    }

    function updateGroupAttendancesList(groupAttendances) {
        const container = document.querySelector('.dashboard-group-attendance-card .attendance-list');
        if (!container) return;

        if (groupAttendances.length === 0) {
            container.innerHTML = '<div class="crm-empty">Нет занятий в группах за выбранную дату</div>';
            return;
        }

        container.innerHTML = groupAttendances.map(item => `
            <div class="attendance-list-item">
                <span class="attendance-group-name">${escapeHtml(item.group_name)}</span>
                <span class="attendance-stats">${item.total} (${item.present}/${item.absent})</span>
            </div>
        `).join('');
    }

    function updateIndividualAttendancesList(individualAttendances) {
        const container = document.querySelector('.dashboard-individual-attendance-card .attendance-list');
        const countEl = document.querySelector('.dashboard-individual-attendance-card .section-count');
        
        if (!container) return;

        if (countEl) {
            countEl.textContent = `(${individualAttendances.length})`;
        }

        if (individualAttendances.length === 0) {
            container.innerHTML = '<div class="crm-empty">Нет индивидуальных занятий за выбранную дату</div>';
            return;
        }

        container.innerHTML = individualAttendances.map(item => `
            <div class="attendance-list-item">
                <span class="attendance-group-name">${escapeHtml(item.student_name)}</span>
                <span class="attendance-stats">${item.present + item.absent} (${item.present}/${item.absent})</span>
            </div>
        `).join('');
    }

    function formatCurrency(amount) {
        return new Intl.NumberFormat('ru-RU', {
            style: 'currency',
            currency: 'RUB',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount);
    }

    function updateStats(stats) {
        if (window.CRM?.updateStats) {
            window.CRM.updateStats(stats);
            return;
        }

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

    function markDashboardReady() {
        document.body.classList.add('dashboard-calendar-ready');
    }

    function loadDashboard() {
        // Загружаем данные для текущей выбранной даты
        loadDashboardDataForDate(selectedDate);
    }

    // Global WebSocket for real-time notifications
    function connectGlobalWebSocket() {
        if (globalWs && globalWs.readyState === WebSocket.OPEN) return;

        // Get WebSocket URL from page config
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat/`;

        try {
            globalWs = new WebSocket(wsUrl);

            globalWs.onopen = () => {
                console.log('Global WebSocket connected');
                wsReconnectAttempts = 0;
            };

            globalWs.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleGlobalWebSocketMessage(data);
            };

            globalWs.onerror = (error) => {
                console.error('Global WebSocket error:', error);
            };

            globalWs.onclose = () => {
                console.log('Global WebSocket disconnected');
                attemptWsReconnect();
            };
        } catch (error) {
            console.error('Failed to connect global WebSocket:', error);
            attemptWsReconnect();
        }
    }

    function attemptWsReconnect() {
        if (wsReconnectAttempts < maxWsReconnectAttempts) {
            wsReconnectAttempts++;
            console.log(`Reconnecting WebSocket... Attempt ${wsReconnectAttempts}`);
            setTimeout(connectGlobalWebSocket, 3000);
        }
    }

    function handleGlobalWebSocketMessage(data) {
        if (data.type === 'new_ticket_message') {
            const message = data.message;
            
            // Update unread messages counter
            const currentCount = parseInt(document.querySelector('[data-nav-count="messages"]')?.textContent || '0');
            setText('[data-nav-count="messages"]', currentCount + 1);
            
            // Show notification only if not on messages page
            const isOnMessagesPage = window.location.pathname.includes('/crm/messages');
            if (!isOnMessagesPage) {
                showGlobalNotification(
                    'Новое сообщение',
                    `От родителя: ${message.sender_name}`,
                    'info',
                    '/crm/messages/'
                );
            }
            
            // Dispatch custom event for messages page to handle
            window.dispatchEvent(new CustomEvent('crm:new_message', { detail: data }));
        }
    }

    function showGlobalNotification(title, message, type = 'info', redirectUrl = null) {
        const notification = document.createElement('div');
        notification.className = `crm-notification crm-notification--${type}`;
        notification.innerHTML = `
            <div class="crm-notification__content">
                <svg class="crm-notification__icon" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                <div class="crm-notification__text">
                    <div class="crm-notification__title">${escapeHtml(title)}</div>
                    <div class="crm-notification__message">${escapeHtml(message)}</div>
                </div>
            </div>
        `;

        if (redirectUrl) {
            notification.style.cursor = 'pointer';
            notification.addEventListener('click', () => {
                window.location.href = redirectUrl;
            });
        }

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('crm-notification--show');
        }, 10);

        setTimeout(() => {
            notification.classList.remove('crm-notification--show');
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    }

    // Expose global WebSocket and notification function
    window.CRM = window.CRM || {};
    window.CRM.ws = globalWs;
    window.CRM.showNotification = showGlobalNotification;
    window.CRM.connectWebSocket = connectGlobalWebSocket;

    document.addEventListener("DOMContentLoaded", function() {
        initCalendar();
        loadDashboard();
        markDashboardReady();
        connectGlobalWebSocket();
    });
})();
