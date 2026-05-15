/**
 * Messaging System - Parent Side
 * Handles WebSocket connection, message sending/receiving, and UI updates
 */

class MessagingApp {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this.currentTicket = null;
        this.selectedCategory = null;
        this.customSubject = null;
        this.isTyping = false;
        this.typingTimeout = null;
        this.typingIndicatorTimeout = null;
        
        this.initElements();
        this.initEventListeners();
        this.loadChatHistory();
    }
    
    initElements() {
        // Topic selector
        this.topicSelector = document.getElementById('topicSelector');
        this.topicButtons = document.querySelectorAll('.messages-topic-btn');
        this.customTopicDiv = document.getElementById('customTopicDiv');
        this.customTopicInput = document.getElementById('customTopicInput');
        this.customTopicConfirm = document.getElementById('customTopicConfirm');
        this.selectedTopicDiv = document.getElementById('selectedTopicDiv');
        this.selectedTopicText = document.getElementById('selectedTopicText');
        
        // Chat elements
        this.chatBody = document.getElementById('chatBody');
        this.messageForm = document.getElementById('messageForm');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.messagesLoading = document.getElementById('messagesLoading');
        this.messagesEmpty = document.getElementById('messagesEmpty');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.adminStatus = document.getElementById('adminStatus');
        this.charCount = document.getElementById('charCount');
        
        // Templates
        this.messageTemplate = document.getElementById('messageTemplate');
        this.ticketSeparatorTemplate = document.getElementById('ticketSeparatorTemplate');
        this.dateSeparatorTemplate = document.getElementById('dateSeparatorTemplate');
    }
    
    initEventListeners() {
        // Topic selection
        this.topicButtons.forEach(btn => {
            btn.addEventListener('click', () => this.handleTopicSelect(btn));
        });
        
        this.customTopicConfirm.addEventListener('click', () => this.handleCustomTopicConfirm());
        this.customTopicInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleCustomTopicConfirm();
        });
        
        // Message form
        this.messageForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });
        
        // Typing indicator
        this.messageInput.addEventListener('input', () => {
            this.handleTyping();
            this.updateCharCount();
        });
    }
    
    async loadChatHistory() {
        try {
            this.showLoading(true);
            
            const response = await fetch(`${window.MESSAGING_CONFIG.apiUrl}tickets/chat-history/`, {
                headers: {
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin'
            });
            
            if (!response.ok) throw new Error('Failed to load chat history');
            
            const data = await response.json();
            
            this.showLoading(false);
            
            if (data.tickets && data.tickets.length > 0) {
                this.renderChatHistory(data.tickets);
                this.currentTicket = data.active_ticket;
                
                if (this.currentTicket) {
                    // Есть активный тикет - скрываем селектор темы
                    this.topicSelector.style.display = 'none';
                    this.enableMessageInput();
                } else {
                    // Нет активного тикета - показываем селектор
                    this.topicSelector.style.display = 'block';
                    this.disableMessageInput();
                }
            } else {
                // Нет сообщений - показываем пустое состояние и селектор
                this.showEmptyState();
                this.topicSelector.style.display = 'block';
                this.disableMessageInput();
            }
            
            // Подключаемся к WebSocket после загрузки истории
            this.connectWebSocket();
            
        } catch (error) {
            console.error('Error loading chat history:', error);
            this.showError('Не удалось загрузить историю сообщений');
            this.showEmptyState();
        }
    }
    
    renderChatHistory(tickets) {
        this.chatBody.innerHTML = '';
        
        let lastDate = null;
        
        tickets.forEach((ticket, ticketIndex) => {
            // Рендерим сообщения тикета
            ticket.messages.forEach((message, msgIndex) => {
                // Добавляем разделитель даты
                const messageDate = this.formatDate(message.created_at);
                if (messageDate !== lastDate) {
                    this.addDateSeparator(messageDate);
                    lastDate = messageDate;
                }
                
                // Добавляем сообщение
                this.addMessageToUI(message);
            });
            
            // Если тикет закрыт, добавляем разделитель
            if (ticket.status === 'closed') {
                this.addTicketClosedSeparator(ticket);
            }
        });
        
        this.scrollToBottom();
    }
    
    addTicketClosedSeparator(ticket) {
        const separator = document.createElement('div');
        separator.className = 'ticket-closed-separator';
        separator.innerHTML = `
            <div class="ticket-closed-line"></div>
            <div class="ticket-closed-content">
                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path d="M9 11l3 3L22 4"/>
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                </svg>
                <span>Обращение закрыто ${this.formatDateTime(ticket.closed_at)}</span>
            </div>
            <div class="ticket-closed-line"></div>
        `;
        this.chatBody.appendChild(separator);
    }
    
    addMessageToUI(message) {
        const messageEl = this.messageTemplate.content.cloneNode(true);
        const messageItem = messageEl.querySelector('.message-item');
        const avatar = messageEl.querySelector('.message-avatar');
        const text = messageEl.querySelector('.message-text');
        const time = messageEl.querySelector('.message-time');
        
        const isReceived = message.sender_id !== window.MESSAGING_CONFIG.userId;
        
        messageItem.classList.add(isReceived ? 'message-item--received' : 'message-item--sent');
        messageItem.dataset.messageId = message.id;
        
        if (isReceived) {
            avatar.textContent = 'А';
        } else {
            avatar.remove();
        }
        
        const createdAt = this.normalizeMessageDate(message);
        text.textContent = message.content;
        time.textContent = this.formatTime(createdAt);
        
        this.chatBody.appendChild(messageEl);
    }
    
    addTicketSeparator(ticket) {
        const separatorEl = this.ticketSeparatorTemplate.content.cloneNode(true);
        const dateEl = separatorEl.querySelector('.ticket-separator-date');
        
        dateEl.textContent = this.formatDateTime(ticket.closed_at);
        
        this.chatBody.appendChild(separatorEl);
    }
    
    addDateSeparator(dateText) {
        const separatorEl = this.dateSeparatorTemplate.content.cloneNode(true);
        const dateDiv = separatorEl.querySelector('.messages-chat-date');
        
        dateDiv.textContent = dateText;
        
        this.chatBody.appendChild(separatorEl);
    }
    
    connectWebSocket() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }
        
        try {
            this.ws = new WebSocket(window.MESSAGING_CONFIG.wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                this.updateAdminStatus('online');
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.updateAdminStatus('offline');
                this.attemptReconnect();
            };
            
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            this.attemptReconnect();
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
            setTimeout(() => this.connectWebSocket(), this.reconnectDelay);
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'new_message':
                this.handleNewMessage(data.message);
                break;
            case 'message_sent':
                this.handleMessageSent(data.message);
                break;
            case 'typing':
                this.handleTypingIndicator(data);
                break;
            case 'ticket_created':
                this.handleTicketCreated(data.ticket);
                break;
            case 'ticket_closed':
                this.handleTicketClosed(data.ticket);
                break;
            case 'error':
                this.showError(data.message);
                break;
        }
    }
    
    handleNewMessage(message) {
        // Проверяем, нужно ли добавить разделитель даты
        const dateSeparators = this.chatBody.querySelectorAll('.messages-chat-date');
        const lastDateSeparator = dateSeparators.length ? dateSeparators[dateSeparators.length - 1] : null;
        const messageDate = this.formatDate(this.normalizeMessageDate(message));
        
        if (!lastDateSeparator || lastDateSeparator.textContent !== messageDate) {
            this.addDateSeparator(messageDate);
        }
        
        this.addMessageToUI(message);
        this.scrollToBottom();
        
        // Отмечаем сообщение как прочитанное (только если это не наше сообщение)
        if (message.sender_id !== window.MESSAGING_CONFIG.userId) {
            this.markMessageAsRead(message.id);
        }
    }
    
    handleMessageSent(message) {
        // Сообщение уже добавлено оптимистично, просто обновляем ID
        // Ищем временное сообщение (начинается с "temp_")
        const tempMessages = this.chatBody.querySelectorAll('.message-item[data-message-id^="temp_"]');
        if (tempMessages.length > 0) {
            // Обновляем последнее временное сообщение
            const tempMessage = tempMessages[tempMessages.length - 1];
            tempMessage.dataset.messageId = message.id;
        }
    }
    
    handleTypingIndicator(data) {
        if (data.is_typing) {
            this.typingIndicator.style.display = 'flex';
            this.scrollToBottom();
            
            // Auto-hide typing indicator after 10 seconds
            clearTimeout(this.typingIndicatorTimeout);
            this.typingIndicatorTimeout = setTimeout(() => {
                this.typingIndicator.style.display = 'none';
            }, 10000);
        } else {
            clearTimeout(this.typingIndicatorTimeout);
            this.typingIndicator.style.display = 'none';
        }
    }
    
    handleTicketClosed(ticket) {
        // Тикет был закрыт админом
        this.currentTicket = null;
        
        // Добавляем разделитель закрытого тикета в чат
        const separator = document.createElement('div');
        separator.className = 'ticket-closed-separator';
        separator.innerHTML = `
            <div class="ticket-closed-line"></div>
            <div class="ticket-closed-content">
                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path d="M9 11l3 3L22 4"/>
                    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                </svg>
                <span>Обращение закрыто администратором</span>
            </div>
            <div class="ticket-closed-line"></div>
        `;
        this.chatBody.appendChild(separator);
        this.scrollToBottom();
        
        // Показываем селектор темы для нового обращения
        this.topicSelector.style.display = 'block';
        this.disableMessageInput();
        
        // Сбрасываем выбранную тему
        this.selectedCategory = null;
        this.customSubject = null;
        this.selectedTopicDiv.style.display = 'none';
        this.topicButtons.forEach(btn => btn.classList.remove('active'));
    }
    
    handleTicketCreated(ticket) {
        this.currentTicket = ticket;
        this.topicSelector.style.display = 'none';
        
        // Скрываем пустое состояние если оно было
        if (this.messagesEmpty.style.display !== 'none') {
            this.messagesEmpty.style.display = 'none';
        }
    }
    
    handleTopicSelect(button) {
        const category = button.dataset.category;
        
        // Убираем active со всех кнопок
        this.topicButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        
        if (category === 'other') {
            // Показываем поле для своей темы
            this.customTopicDiv.style.display = 'flex';
            this.customTopicInput.focus();
            this.selectedCategory = category;
            this.selectedTopicDiv.style.display = 'none';
        } else {
            // Выбрана предопределенная категория
            this.customTopicDiv.style.display = 'none';
            this.selectedCategory = category;
            this.customSubject = null;
            
            const topicText = button.querySelector('span').textContent;
            this.selectedTopicText.textContent = topicText;
            this.selectedTopicDiv.style.display = 'flex';
            
            this.enableMessageInput();
        }
    }
    
    handleCustomTopicConfirm() {
        const customTopic = this.customTopicInput.value.trim();
        if (customTopic) {
            this.customSubject = customTopic;
            this.selectedTopicText.textContent = customTopic;
            this.selectedTopicDiv.style.display = 'flex';
            this.customTopicDiv.style.display = 'none';
            
            this.enableMessageInput();
        }
    }
    
    async sendMessage() {
        const content = this.messageInput.value.trim();
        if (!content) return;
        
        // Check message length
        if (content.length > 2000) {
            this.showError('Сообщение слишком длинное (максимум 2000 символов)');
            return;
        }
        
        // Если нет активного тикета и не выбрана тема
        if (!this.currentTicket && !this.selectedCategory) {
            this.showError('Пожалуйста, выберите тему обращения');
            return;
        }
        
        // Disable send button to prevent double-sending
        this.sendBtn.disabled = true;
        this.sendBtn.classList.add('sending');
        
        // Очищаем поле ввода
        this.messageInput.value = '';
        this.updateCharCount();
        
        // Генерируем уникальный временный ID
        const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // Добавляем сообщение оптимистично
        this.addMessageToUI({
            id: tempId,
            sender_id: window.MESSAGING_CONFIG.userId,
            content: content,
            created_at: new Date().toISOString()
        });
        this.scrollToBottom();
        
        // Отправляем через WebSocket
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const payload = {
                type: 'send_message',
                content: content
            };
            
            // Если это первое сообщение (нет активного тикета), добавляем тему
            if (!this.currentTicket) {
                payload.category = this.selectedCategory;
                if (this.customSubject) {
                    payload.custom_subject = this.customSubject;
                }
            } else {
                payload.ticket_id = this.currentTicket.id;
            }
            
            this.ws.send(JSON.stringify(payload));
            
            // Re-enable send button after a short delay
            setTimeout(() => {
                this.sendBtn.disabled = false;
                this.sendBtn.classList.remove('sending');
            }, 500);
        } else {
            // Fallback на REST API
            await this.sendMessageViaAPI(content);
        }
    }
    
    async sendMessageViaAPI(content) {
        try {
            const payload = {
                content: content
            };
            
            if (!this.currentTicket) {
                payload.category = this.selectedCategory;
                if (this.customSubject) {
                    payload.custom_subject = this.customSubject;
                }
            }
            
            const url = this.currentTicket 
                ? `${window.MESSAGING_CONFIG.apiUrl}tickets/${this.currentTicket.id}/send-message/`
                : `${window.MESSAGING_CONFIG.apiUrl}tickets/create/`;
            
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) throw new Error('Failed to send message');
            
            const data = await response.json();
            
            if (!this.currentTicket && data.ticket) {
                this.handleTicketCreated(data.ticket);
            }
            
            // Re-enable send button
            this.sendBtn.disabled = false;
            this.sendBtn.classList.remove('sending');
            
        } catch (error) {
            console.error('Error sending message:', error);
            this.showError('Не удалось отправить сообщение');
            
            // Удаляем оптимистичное сообщение
            const tempMessages = this.chatBody.querySelectorAll('.message-item[data-message-id^="temp_"]');
            if (tempMessages.length > 0) {
                tempMessages[tempMessages.length - 1].remove();
            }
            
            // Re-enable send button
            this.sendBtn.disabled = false;
            this.sendBtn.classList.remove('sending');
        }
    }
    
    handleTyping() {
        if (!this.currentTicket) return;
        
        if (!this.isTyping) {
            this.isTyping = true;
            this.sendTypingStatus(true);
        }
        
        clearTimeout(this.typingTimeout);
        this.typingTimeout = setTimeout(() => {
            this.isTyping = false;
            this.sendTypingStatus(false);
        }, 2000);
    }
    
    sendTypingStatus(isTyping) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN && this.currentTicket) {
            this.ws.send(JSON.stringify({
                type: 'typing',
                ticket_id: this.currentTicket.id,
                is_typing: isTyping
            }));
        }
    }
    
    async markMessageAsRead(messageId) {
        try {
            if (this.currentTicket?.id) {
                await fetch(`${window.MESSAGING_CONFIG.apiUrl}tickets/${this.currentTicket.id}/mark-read/`, {
                    method: 'PATCH',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': this.getCookie('csrftoken')
                    },
                    credentials: 'same-origin'
                });
            }
        } catch (error) {
            console.error('Error marking message as read:', error);
        }
    }
    
    enableMessageInput() {
        this.messageInput.disabled = false;
        this.sendBtn.disabled = false;
        this.messageInput.focus();
        this.updateCharCount();
    }
    
    disableMessageInput() {
        this.messageInput.disabled = true;
        this.sendBtn.disabled = true;
    }
    
    updateCharCount() {
        if (this.charCount) {
            const length = this.messageInput.value.length;
            this.charCount.textContent = `${length} / 2000`;
            
            if (length > 1900) {
                this.charCount.style.color = '#ff4444';
            } else if (length > 1700) {
                this.charCount.style.color = '#ffaa00';
            } else {
                this.charCount.style.color = 'rgba(255, 255, 255, 0.5)';
            }
        }
    }
    
    showLoading(show) {
        this.messagesLoading.style.display = show ? 'flex' : 'none';
    }
    
    showEmptyState() {
        this.messagesLoading.style.display = 'none';
        this.messagesEmpty.style.display = 'flex';
    }
    
    updateAdminStatus(status) {
        const statusText = this.adminStatus.querySelector('.status-text');
        if (status === 'online') {
            statusText.textContent = 'Онлайн';
        } else {
            statusText.textContent = 'Оффлайн';
        }
    }
    
    showError(message) {
        // Можно добавить toast-уведомление
        console.error(message);
        alert(message);
    }
    
    scrollToBottom() {
        setTimeout(() => {
            this.chatBody.scrollTop = this.chatBody.scrollHeight;
        }, 100);
    }
    
    formatDate(dateString) {
        const date = new Date(dateString);
        if (Number.isNaN(date.getTime())) return 'Сегодня';
        const today = new Date();
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        
        if (date.toDateString() === today.toDateString()) {
            return 'Сегодня';
        } else if (date.toDateString() === yesterday.toDateString()) {
            return 'Вчера';
        } else {
            return date.toLocaleDateString('ru-RU', { 
                day: 'numeric', 
                month: 'long',
                year: date.getFullYear() !== today.getFullYear() ? 'numeric' : undefined
            });
        }
    }
    
    formatTime(dateString) {
        const date = new Date(dateString);
        if (Number.isNaN(date.getTime())) return new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
        return date.toLocaleTimeString('ru-RU', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    formatDateTime(dateString) {
        const date = new Date(dateString);
        if (Number.isNaN(date.getTime())) return '';
        return date.toLocaleDateString('ru-RU', { 
            day: 'numeric', 
            month: 'long',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    normalizeMessageDate(message) {
        const value = message?.created_at || message?.created || message?.timestamp || message?.sent_at;
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? new Date().toISOString() : value;
    }
    
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    if (window.MESSAGING_CONFIG) {
        new MessagingApp();
    }
});
