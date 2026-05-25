(function () {
    const DASHBOARD_TARGET = '#dashboardContent';

    function parsePayload() {
        const node = document.getElementById('dashboard-data');
        if (!node) return null;

        try {
            return JSON.parse(node.textContent || '{}');
        } catch (error) {
            console.error('Failed to parse dashboard payload', error);
            return null;
        }
    }

    function formatDate(dateStr) {
        const date = new Date(dateStr);
        if (Number.isNaN(date.getTime())) return dateStr;

        const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
        return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()}`;
    }

    function toApiDate(date) {
        const pad = (value) => String(value).padStart(2, '0');
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
    }

    function circleSegment(value, total, startRatio = 0) {
        const radius = 80;
        const circumference = 2 * Math.PI * radius;
        const safeTotal = Number(total || 0);
        const safeValue = Math.max(Number(value || 0), 0);
        const ratio = safeTotal > 0 ? Math.min(safeValue / safeTotal, 1) : 0;
        const start = Math.max(Number(startRatio || 0), 0);
        return {
            dasharray: `${ratio * circumference} ${circumference}`,
            dashoffset: `${-start * circumference}`,
        };
    }

    function loadDashboard(date) {
        const target = document.querySelector(DASHBOARD_TARGET);
        if (!target) return;

        const url = date ? `${window.location.pathname}?date=${date}` : window.location.pathname;

        if (window.htmx) {
            htmx.ajax('GET', url, { target: DASHBOARD_TARGET, swap: 'innerHTML' });
            return;
        }

        fetch(url, {
            headers: {
                'HX-Request': 'true',
            },
        })
            .then((response) => response.text())
            .then((html) => {
                target.innerHTML = html;
            });
    }

    window.dashboardPage = function dashboardPage() {
        return {
            loading: false,
            dashboard: {
                date: null,
                date_display: '',
                calendar: {
                    month_label: '',
                    selected_date_display: '',
                    selected_date_iso: '',
                    weekdays: [],
                    weeks: [],
                },
                subscriptions: { group: 0, individual: 0, new: 0, renewal: 0, total: 0 },
                singleLessons: { group: 0, individual: 0, total: 0 },
                products: { total: 0 },
                attendance: { group: 0, individual: 0, total: 0 },
                balance: {
                    income: { total: 0, breakdown: {}, items: [] },
                    expense: { total: 0, breakdown: {}, items: [] },
                    total: 0,
                    formatted_total: '0',
                    formatted_income_total: '0',
                    formatted_expense_total: '0',
                },
                groupAttendances: [],
                individualAttendances: [],
            },
            titles: {
                sales: 'Продажи за выбранную дату',
                attendance: 'Посещения за выбранную дату',
                balance: 'Баланс за выбранную дату',
                groupAttendance: 'Посещения по группам за выбранную дату',
                individualAttendance: 'Посещения по индивидуальным занятиям за выбранную дату',
            },
            circles: {
                subscriptionsGroup: { dasharray: '0 502', dashoffset: '0' },
                subscriptionsIndividual: { dasharray: '0 502', dashoffset: '0' },
                singleGroup: { dasharray: '0 502', dashoffset: '0' },
                singleIndividual: { dasharray: '0 502', dashoffset: '0' },
                products: { dasharray: '0 502', dashoffset: '0' },
                attendanceGroup: { dasharray: '0 502', dashoffset: '0' },
                attendanceIndividual: { dasharray: '0 502', dashoffset: '0' },
            },
            get calendar() {
                return this.dashboard?.calendar || {
                    month_label: '',
                    selected_date_display: '',
                    selected_date_iso: '',
                    weekdays: [],
                    weeks: [],
                    days: [],
                };
            },
            init() {
                const payload = parsePayload();
                if (payload) {
                    this.applyPayload(payload);
                }
            },
            applyPayload(payload) {
                this.dashboard = payload;
                this.refreshTitles();
                this.refreshCircles();
                this.refreshBalancePercents();
            },
            refreshTitles() {
                const formatted = this.dashboard.date_display || '';
                this.titles.sales = `Продажи за ${formatted}`;
                this.titles.attendance = `Посещения за ${formatted}`;
                this.titles.balance = `Баланс за ${formatted}`;
                this.titles.groupAttendance = `Посещения по группам за ${formatted}`;
                this.titles.individualAttendance = `Посещения по индивидуальным занятиям за ${formatted}`;
            },
            refreshCircles() {
                const subscriptions = this.dashboard.subscriptions || { group: 0, individual: 0, total: 0 };
                const singleLessons = this.dashboard.singleLessons || { group: 0, individual: 0, total: 0 };
                const products = this.dashboard.products || { total: 0 };
                const attendance = this.dashboard.attendance || { group: 0, individual: 0, total: 0 };

                const subscriptionsGroupRatio = subscriptions.total > 0 ? subscriptions.group / subscriptions.total : 0;
                const singleGroupRatio = singleLessons.total > 0 ? singleLessons.group / singleLessons.total : 0;
                const attendanceGroupRatio = attendance.total > 0 ? attendance.group / attendance.total : 0;

                this.circles.subscriptionsGroup = circleSegment(subscriptions.group, subscriptions.total, 0);
                this.circles.subscriptionsIndividual = circleSegment(subscriptions.individual, subscriptions.total, subscriptionsGroupRatio);
                this.circles.singleGroup = circleSegment(singleLessons.group, singleLessons.total, 0);
                this.circles.singleIndividual = circleSegment(singleLessons.individual, singleLessons.total, singleGroupRatio);
                this.circles.products = circleSegment(products.total, products.total || 1, 0);
                this.circles.attendanceGroup = circleSegment(attendance.group, attendance.total, 0);
                this.circles.attendanceIndividual = circleSegment(attendance.individual, attendance.total, attendanceGroupRatio);
            },
            refreshBalancePercents() {
                const incomeItems = this.dashboard.balance?.income?.items || [];
                const expenseItems = this.dashboard.balance?.expense?.items || [];

                const maxIncome = incomeItems.reduce((max, item) => Math.max(max, Number(item.amount || 0)), 0);
                const maxExpense = expenseItems.reduce((max, item) => Math.max(max, Number(item.amount || 0)), 0);

                incomeItems.forEach((item) => {
                    item.percent = maxIncome > 0 ? (Number(item.amount || 0) / maxIncome) * 100 : 0;
                });

                expenseItems.forEach((item) => {
                    item.percent = maxExpense > 0 ? (Number(item.amount || 0) / maxExpense) * 100 : 0;
                });
            },
            navigateMonth(direction) {
                const current = this.dashboard.calendar?.selected_date_iso ? new Date(this.dashboard.calendar.selected_date_iso) : new Date();
                current.setDate(1);
                current.setMonth(current.getMonth() + (direction === 'next' ? 1 : -1));
                loadDashboard(toApiDate(current));
            },
            selectDate(dateIso) {
                loadDashboard(dateIso);
            },
        };
    };
})();
