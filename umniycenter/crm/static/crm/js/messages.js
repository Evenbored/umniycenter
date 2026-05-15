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
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
    };

    let currentTickets = [];
    let selectedTicketId = null;
    let currentFilter = 'all';
    let currentDateFilter = 'all';
    let searchQuery = '';
    let ws = null;

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatDate(isoString) {
        if (!isoString) return "-";
        const date = new Date(isoString);
        return date.toLocaleDateString("ru-RU", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        });
    }

    function formatTime(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        return date.toLocaleTimeString("ru-RU", {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    function formatDateTime(isoString) {
        if (!isoString) return "";
        const date = new Date(isoString);
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const messageDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());

        if (messageDate.getTime() === today.getTime()) {
            return formatTime(isoString);
        } else {
            return formatDate(isoString);
        }
    }

    function getInitials(name) {
        const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
        return (parts[0]?.[0] || "У") + (parts[1]?.[0] || "");
    }

    function getStatusBadge(status) {
        const statusMap = {
            'open': { text: 'Новое', class: 'crm-ticket-status--open' },
            'in_progress': { text: 'В работе', class: 'crm-ticket-status--in_progress' },
            'waiting_parent': { text: 'Ожидает', class: 'crm-ticket-status--waiting_parent' },
            'closed': { text: 'Закрыто', class: 'crm-ticket-status--closed' }
        };
        const info = statusMap[status] || statusMap['open'];
        return `<span class="crm-ticket-status ${info.class}">${info.text}</span>`;
    }

    function getCategoryDisplay(category) {
        const categoryMap = {
            'payment': 'Вопрос по оплате',
            'schedule': 'Вопрос по расписанию',
            'progress': 'Успеваемость ребенка',
            'absence': 'Пропуск занятий',
            'teacher': 'Вопрос по преподавателю',
            'technical': 'Технический вопрос',
            'other': 'Другое'
        };
        return categoryMap[category] || 'Другое';
    }

    function filterTickets() {
        let filtered = currentTickets;

        // Filter by status
        if (currentFilter !== 'all') {
            filtered = filtered.filter(ticket => ticket.status === currentFilter);
        }

        // Filter by date
        if (currentDateFilter !== 'all') {
            const now = new Date();
            const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            
            filtered = filtered.filter(ticket => {
                const ticketDate = new Date(ticket.created_at);
                const ticketDay = new Date(ticketDate.getFullYear(), ticketDate.getMonth(), ticketDate.getDate());

                if (currentDateFilter === 'today') {
                    return ticketDay.getTime() === today.getTime();
                } else if (currentDateFilter === 'week') {
                    const weekAgo = new Date(today);
                    weekAgo.setDate(weekAgo.getDate() - 7);
                    return ticketDay >= weekAgo;
                } else if (currentDateFilter === 'month') {
                    const monthAgo = new Date(today);
                    monthAgo.setMonth(monthAgo.getMonth() - 1);
                    return ticketDay >= monthAgo;
                }
                return true;
            });
        }

        // Filter by search query
        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            filtered = filtered.filter(ticket => 
                ticket.parent_name.toLowerCase().includes(query) ||
                ticket.subject.toLowerCase().includes(query)
            );
        }

        return filtered;
    }

    function updateFilterCounts() {
        const counts = {
            all: currentTickets.length,
            open: currentTickets.filter(t => t.status === 'open').length,
            in_progress: currentTickets.filter(t => t.status === 'in_progress' || t.status === 'waiting_parent').length,
            closed: currentTickets.filter(t => t.status === 'closed').length
        };

        document.querySelectorAll('[data-count]').forEach(el => {
            const filter = el.dataset.count;
            el.textContent = counts[filter] || 0;
        });
    }

    function renderTicketsList(tickets) {
        const listEl = document.getElementById('ticketsList');
        
        if (tickets.length === 0) {
            listEl.innerHTML = `
                <div class="crm-messages-empty">
                    <svg width="48" height="48" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                    <p>Нет обращений</p>
                </div>
            `;
            return;
        }

        // Sort: new first, then active, then closed
        tickets.sort((a, b) => {
            const statusOrder = { 'open': 0, 'in_progress': 1, 'waiting_parent': 1, 'closed': 2 };
            const orderA = statusOrder[a.status] || 1;
            const orderB = statusOrder[b.status] || 1;
            
            if (orderA !== orderB) {
                return orderA - orderB;
            }
            
            return new Date(b.last_message_at || b.created_at) - new Date(a.last_message_at || a.created_at);
        });

        const template = document.getElementById('ticketItemTemplate');
        listEl.innerHTML = '';

        tickets.forEach(ticket => {
            const clone = template.content.cloneNode(true);
            const item = clone.querySelector('.crm-ticket-item');
            
            item.dataset.ticketId = ticket.id;
            item.querySelector('.crm-ticket-item__avatar').textContent = getInitials(ticket.parent_name);
            item.querySelector('.crm-ticket-item__name').textContent = escapeHtml(ticket.parent_name);
            item.querySelector('.crm-ticket-item__time').textContent = formatDateTime(ticket.last_message_at || ticket.created_at);
            item.querySelector('.crm-ticket-item__subject').textContent = escapeHtml(ticket.subject || getCategoryDisplay(ticket.category));
            
            const lastMsg = ticket.last_message;
            item.querySelector('.crm-ticket-item__preview').textContent = lastMsg ? escapeHtml(lastMsg.content).substring(0, 60) + '...' : 'Нет сообщений';
            
            item.querySelector('.crm-ticket-status').outerHTML = getStatusBadge(ticket.status);
            
            const unreadBadge = item.querySelector('.crm-ticket-unread');
            if (ticket.unread_count > 0) {
                unreadBadge.textContent = ticket.unread_count;
                unreadBadge.style.display = 'flex';
            }

            if (ticket.id === selectedTicketId) {
                item.classList.add('active');
            }

            item.addEventListener('click', () => selectTicket(ticket.id));
            
            listEl.appendChild(clone);
        });
    }

    function loadTickets() {
        fetch(`${window.CRM_MESSAGES_CONFIG.apiUrl}tickets/`, { headers })
            .then(response => {
                if (!response.ok) throw new Error('Failed to load tickets');
                return response.json();
            })
            .then(data => {
                currentTickets = data.results || data;
                updateFilterCounts();
                renderTicketsList(filterTickets());
            })
            .catch(error => {
                console.error('Error loading tickets:', error);
                showNotification('Ошибка загрузки обращений', 'error');
            });
    }

    function selectTicket(ticketId) {
        selectedTicketId = ticketId;
        
        // Update active state in list
        document.querySelectorAll('.crm-ticket-item').forEach(item => {
            item.classList.toggle('active', item.dataset.ticketId == ticketId);
        });

        // Load ticket details
        fetch(`${window.CRM_MESSAGES_CONFIG.apiUrl}tickets/${ticketId}/`, { headers })
            .then(response => {
                if (!response.ok) throw new Error('Failed to load ticket');
                return response.json();
            })
            .then(ticket => {
                renderChat(ticket);
                markTicketAsRead(ticketId);
            })
            .catch(error => {
                console.error('Error loading ticket:', error);
                showNotification('Ошибка загрузки обращения', 'error');
            });
    }

    function renderChat(ticket) {
        document.getElementById('chatEmpty').style.display = 'none';
        document.getElementById('chatContent').style.display = 'flex';

        document.getElementById('chatAvatar').textContent = getInitials(ticket.parent_name);
        document.getElementById('chatName').textContent = escapeHtml(ticket.parent_name);
        document.getElementById('chatCategory').textContent = getCategoryDisplay(ticket.category);
        document.getElementById('chatDate').textContent = formatDate(ticket.created_at);

        const closeBtn = document.getElementById('closeTicketBtn');
        if (ticket.status === 'closed') {
            closeBtn.disabled = true;
            closeBtn.textContent = 'Закрыто';
        } else {
            closeBtn.disabled = false;
            closeBtn.innerHTML = `
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path d="M9 11l3 3L22 4"/>
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                </svg>
                Закрыть обращение
            `;
        }

        renderMessages(ticket.messages || []);
    }

    function renderMessages(messages) {
        const chatBody = document.getElementById('chatBody');
        const template = document.getElementById('messageTemplate');
        chatBody.innerHTML = '';

        messages.forEach(message => {
            const clone = template.content.cloneNode(true);
            const messageEl = clone.querySelector('.crm-message');
            
            // Проверяем роль отправителя: 2 = ADMIN, 3 = PARENT
            const isAdmin = message.sender_role === 2;
            if (isAdmin) {
                messageEl.classList.add('crm-message--sent');
            }

            messageEl.dataset.messageId = message.id;
            messageEl.querySelector('.crm-message__avatar').textContent = getInitials(message.sender_name);
            messageEl.querySelector('.crm-message__sender').textContent = escapeHtml(message.sender_name);
            messageEl.querySelector('.crm-message__time').textContent = formatTime(message.created_at);
            messageEl.querySelector('.crm-message__text').textContent = escapeHtml(message.content);

            chatBody.appendChild(clone);
        });

        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function markTicketAsRead(ticketId) {
        fetch(`${window.CRM_MESSAGES_CONFIG.apiUrl}tickets/${ticketId}/mark-read/`, {
            method: 'PATCH',
            headers: headersWithCsrf
        })
        .then(() => {
            // Обновляем общий badge непрочитанных сообщений
            const allMessagesBadge = document.querySelector('[data-nav-count="messages"]');
            const ticketItem = document.querySelector(`.crm-ticket-item[data-ticket-id="${ticketId}"]`);
            const unreadBadge = ticketItem ? ticketItem.querySelector('.crm-ticket-unread') : null;

            const unreadCount = unreadBadge ? parseInt(unreadBadge.textContent || '0', 10) : 0;

            if (allMessagesBadge) {
                const currentTotal = parseInt(allMessagesBadge.textContent || '0', 10);
                const nextTotal = Math.max(0, currentTotal - unreadCount);
                allMessagesBadge.textContent = nextTotal;
            }

            // Обновляем UI - убираем счётчик непрочитанных
            if (ticketItem) {
                if (unreadBadge) {
                    unreadBadge.style.display = 'none';
                    unreadBadge.textContent = '0';
                }
            }
        })
        .catch(error => console.error('Error marking as read:', error));
    }

    function sendMessage(content) {
        if (!selectedTicketId || !content.trim()) return;

        const messageContent = content.trim();
        
        // Check message length
        if (messageContent.length > 2000) {
            showNotification('Сообщение слишком длинное (максимум 2000 символов)', 'error');
            return;
        }
        
        // Disable send button
        const sendBtn = document.querySelector('#messageForm button[type="submit"]');
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.classList.add('sending');
        }

        fetch(`${window.CRM_MESSAGES_CONFIG.apiUrl}tickets/${selectedTicketId}/send-message/`, {
            method: 'POST',
            headers: headersWithCsrf,
            body: JSON.stringify({ content: messageContent })
        })
        .then(response => {
            if (!response.ok) throw new Error('Failed to send message');
            return response.json();
        })
        .then(message => {
            // Add message to chat immediately
            const chatBody = document.getElementById('chatBody');
            const template = document.getElementById('messageTemplate');
            const clone = template.content.cloneNode(true);
            const messageEl = clone.querySelector('.crm-message');
            
            messageEl.classList.add('crm-message--sent');
            messageEl.dataset.messageId = message.id;
            messageEl.querySelector('.crm-message__avatar').textContent = getInitials(message.sender_name);
            messageEl.querySelector('.crm-message__sender').textContent = escapeHtml(message.sender_name);
            messageEl.querySelector('.crm-message__time').textContent = formatTime(message.created_at);
            messageEl.querySelector('.crm-message__text').textContent = escapeHtml(message.content);

            chatBody.appendChild(clone);
            chatBody.scrollTop = chatBody.scrollHeight;

            // Clear input
            document.getElementById('messageInput').value = '';
            autoResizeTextarea(document.getElementById('messageInput'));
            updateCharCount();

            // Reload tickets list to update preview
            loadTickets();
            
            // Re-enable send button
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.classList.remove('sending');
            }
        })
        .catch(error => {
            console.error('Error sending message:', error);
            showNotification('Ошибка отправки сообщения', 'error');
            
            // Re-enable send button
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.classList.remove('sending');
            }
        });
    }

    function closeTicket() {
        if (!selectedTicketId) return;

        if (!confirm('Вы уверены, что хотите закрыть это обращение?')) return;

        fetch(`${window.CRM_MESSAGES_CONFIG.apiUrl}tickets/${selectedTicketId}/close/`, {
            method: 'POST',
            headers: headersWithCsrf
        })
        .then(response => {
            if (!response.ok) throw new Error('Failed to close ticket');
            return response.json();
        })
        .then(() => {
            showNotification('Обращение закрыто', 'success');
            loadTickets();
            if (selectedTicketId) {
                selectTicket(selectedTicketId);
            }
        })
        .catch(error => {
            console.error('Error closing ticket:', error);
            showNotification('Ошибка закрытия обращения', 'error');
        });
    }

    function connectWebSocket() {
        // Use global WebSocket from dashboard.js
        if (window.CRM && window.CRM.connectWebSocket) {
            // WebSocket is already connected globally
            console.log('Using global WebSocket connection');
            
            // Listen for custom events from global WebSocket
            window.addEventListener('crm:new_message', handleGlobalWebSocketEvent);
            return;
        }
        
        // Fallback: create local WebSocket if global not available
        if (ws && ws.readyState === WebSocket.OPEN) return;

        ws = new WebSocket(window.CRM_MESSAGES_CONFIG.wsUrl);

        ws.onopen = () => {
            console.log('WebSocket connected');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        ws.onclose = () => {
            console.log('WebSocket disconnected');
            setTimeout(connectWebSocket, 3000);
        };
    }
    
    function handleGlobalWebSocketEvent(event) {
        // Handle messages from global WebSocket
        handleWebSocketMessage(event.detail);
    }

    function handleWebSocketMessage(data) {
        if (data.type === 'new_ticket_message') {
            const message = data.message;
            
            // Skip own messages - they're already added optimistically
            if (message.sender_id === window.CRM_MESSAGES_CONFIG.userId) {
                return;
            }
            
            // Show notification using global notification system
            if (window.CRM && window.CRM.showNotification) {
                window.CRM.showNotification('Новое сообщение', `От родителя: ${message.sender_name}`, 'info');
            } else {
                showNotification(`Новое сообщение от родителя`, 'info');
            }

            // Reload tickets list
            loadTickets();

            // If this ticket is currently open, add message to chat
            if (selectedTicketId && message.ticket_id == selectedTicketId) {
                const chatBody = document.getElementById('chatBody');
                const template = document.getElementById('messageTemplate');
                const clone = template.content.cloneNode(true);
                const messageEl = clone.querySelector('.crm-message');
                
                messageEl.dataset.messageId = message.id;
                messageEl.querySelector('.crm-message__avatar').textContent = getInitials(message.sender_name);
                messageEl.querySelector('.crm-message__sender').textContent = escapeHtml(message.sender_name);
                messageEl.querySelector('.crm-message__time').textContent = formatTime(message.created_at);
                messageEl.querySelector('.crm-message__text').textContent = escapeHtml(message.content);

                chatBody.appendChild(clone);
                chatBody.scrollTop = chatBody.scrollHeight;
            }
        } else if (data.type === 'typing') {
            if (selectedTicketId && data.ticket_id == selectedTicketId) {
                const typingIndicator = document.getElementById('typingIndicator');
                typingIndicator.style.display = data.is_typing ? 'flex' : 'none';
                
                // Auto-hide typing indicator after 10 seconds
                if (data.is_typing) {
                    clearTimeout(window.typingTimeout);
                    window.typingTimeout = setTimeout(() => {
                        typingIndicator.style.display = 'none';
                    }, 10000);
                }
            }
        }
    }

    function showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `crm-notification crm-notification--${type}`;
        notification.innerHTML = `
            <div class="crm-notification__content">
                <span>${escapeHtml(message)}</span>
            </div>
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('crm-notification--show');
        }, 10);

        setTimeout(() => {
            notification.classList.remove('crm-notification--show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    function autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
    
    function updateCharCount() {
        const charCountEl = document.getElementById('charCount');
        const messageInput = document.getElementById('messageInput');
        if (charCountEl && messageInput) {
            const length = messageInput.value.length;
            charCountEl.textContent = `${length} / 2000`;
            
            if (length > 1900) {
                charCountEl.style.color = '#ff4444';
            } else if (length > 1700) {
                charCountEl.style.color = '#ffaa00';
            } else {
                charCountEl.style.color = 'rgba(255, 255, 255, 0.5)';
            }
        }
    }

    // Event listeners
    document.addEventListener('DOMContentLoaded', () => {
        loadTickets();
        connectWebSocket();

        // Filter buttons
        document.querySelectorAll('.crm-filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.crm-filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentFilter = btn.dataset.filter;
                renderTicketsList(filterTickets());
            });
        });

        // Date filter
        document.getElementById('dateFilter').addEventListener('change', (e) => {
            currentDateFilter = e.target.value;
            renderTicketsList(filterTickets());
        });

        // Search
        document.getElementById('ticketsSearch').addEventListener('input', (e) => {
            searchQuery = e.target.value;
            renderTicketsList(filterTickets());
        });

        // Message form
        document.getElementById('messageForm').addEventListener('submit', (e) => {
            e.preventDefault();
            const input = document.getElementById('messageInput');
            sendMessage(input.value);
        });

        // Auto-resize textarea
        const messageInput = document.getElementById('messageInput');
        messageInput.addEventListener('input', (e) => {
            autoResizeTextarea(e.target);
            updateCharCount();
        });

        // Send on Enter, new line on Shift+Enter
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage(messageInput.value);
            }
        });

        // Close ticket button
        document.getElementById('closeTicketBtn').addEventListener('click', closeTicket);
    });

    // Global functions
    window.refreshTickets = loadTickets;
})();
