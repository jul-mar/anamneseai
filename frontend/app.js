document.addEventListener('DOMContentLoaded', () => {

    const API_BASE_URL = 'http://localhost:8000/api';

    // UI Elements
    const chatBox = document.getElementById('chat-box');
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('user-message-input');
    const sendButton = document.getElementById('send-button');
    const restartButton = document.getElementById('restart-button');
    const debugToggle = document.getElementById('debug-toggle');
    const statusIndicator = document.getElementById('status-indicator');

    // Application State
    const state = {
        messages: [],
        botState: 'INIT',
        debugMode: false,
        isLoading: false,
    };

    /**
     * API Communication Layer
     */
    const api = {
        async startSession() {
            return await _fetch('/session/start', 'POST');
        },
        async sendMessage(message) {
            return await _fetch('/chat', 'POST', { message });
        },
        async restartSession() {
            return await _fetch('/session/restart', 'POST');
        },
        async toggleDebug() {
            return await _fetch('/debug/toggle', 'POST');
        }
    };

    /**
     * Generic fetch wrapper to handle requests and errors.
     * It also manages loading state.
     * @param {string} endpoint - The API endpoint to call.
     * @param {string} method - The HTTP method.
     * @param {object} body - The request body.
     * @returns {Promise<object|null>} - The JSON response or null on error.
     */
    async function _fetch(endpoint, method, body = null) {
        setLoading(true);
        try {
            const options = {
                method,
                headers: { 'Content-Type': 'application/json' },
            };
            if (body) {
                options.body = JSON.stringify(body);
            }

            const response = await fetch(API_BASE_URL + endpoint, options);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`API Error calling ${endpoint}:`, error);
            renderError(error.message);
            return null;
        } finally {
            setLoading(false);
        }
    }


    /**
     * --- State and UI Management ---
     */

    function renderMessage(message) {
        const isUser = message.role === 'user';
        const chatAlignment = isUser ? 'chat-end' : 'chat-start';
        
        let bubbleColor;
        if (message.role === 'error') {
            bubbleColor = 'chat-bubble-error';
        } else if (isUser) {
            bubbleColor = 'chat-bubble-primary';
        } else {
            bubbleColor = 'chat-bubble-secondary';
        }

        const avatarInitial = isUser ? 'P' : 'A';
        const avatarClass = isUser ? 'bg-primary text-primary-content' : 'bg-secondary text-secondary-content';

        const messageDiv = document.createElement('div');
        messageDiv.className = `chat ${chatAlignment}`;
        messageDiv.innerHTML = `
            <div class="chat-image avatar placeholder">
                <div class="w-10 rounded-full ${avatarClass}">
                    <span>${avatarInitial}</span>
                </div>
            </div>
            <div class="chat-header text-xs opacity-70">
                ${message.role.charAt(0).toUpperCase() + message.role.slice(1)}
            </div>
            <div class="chat-bubble ${bubbleColor} whitespace-pre-wrap break-words">${message.content}</div>
        `;
        return messageDiv;
    }

    function render() {
        // Clear chatbox
        chatBox.innerHTML = '';

        // Render messages
        state.messages.forEach(msg => {
            chatBox.appendChild(renderMessage(msg));
        });

        // Scroll to bottom
        chatBox.scrollTop = chatBox.scrollHeight;
        
        // Update debug toggle state
        debugToggle.checked = state.debugMode;

        // Enable/disable form based on bot state
        const isWaitingForUser = state.botState === 'EXPECTING_USER_ANSWER';
        const formDisabled = state.isLoading || !isWaitingForUser;
        
        messageInput.disabled = formDisabled;
        sendButton.disabled = formDisabled;

        if(formDisabled) {
            messageInput.placeholder = 'Bitte warten...';
        } else {
            messageInput.placeholder = 'Ihre Antwort...';
            messageInput.focus();
        }
    }

    function setLoading(isLoading) {
        state.isLoading = isLoading;
        if (isLoading) {
            statusIndicator.textContent = 'lädt...';
            statusIndicator.classList.remove('badge-success', 'badge-error');
            statusIndicator.classList.add('badge-info');
            sendButton.classList.add('loading');
            messageInput.disabled = true;
        } else {
            statusIndicator.textContent = 'bereit';
            statusIndicator.classList.remove('badge-info');
            statusIndicator.classList.add('badge-success');
            sendButton.classList.remove('loading');
            // Re-enable based on bot state, which will be handled by render()
            // messageInput.disabled = false; 
        }
    }

    function renderError(errorMessage) {
        const errorMsg = {
            id: `err-${Date.now()}`,
            role: 'error',
            content: `Ein Fehler ist aufgetreten:\n${errorMessage}`
        };
        state.messages.push(errorMsg);
        render(); // Re-render to show the error message
    }

    function updateState(apiResponse) {
        if (!apiResponse) return;
        
        if (apiResponse.chat_messages) {
            state.messages = apiResponse.chat_messages;
        }
        if (apiResponse.bot_state) {
            state.botState = apiResponse.bot_state;
        }
        if (typeof apiResponse.debug_mode === 'boolean') {
            state.debugMode = apiResponse.debug_mode;
            debugToggle.checked = apiResponse.debug_mode;
        }

        render();
    }


    /**
     * --- Event Handlers ---
     */

    async function handleFormSubmit(event) {
        event.preventDefault();
        const message = messageInput.value.trim();
        if (!message || state.isLoading) return;

        // Add user message to state and render immediately for optimistic UI
        const userMessage = { id: `user-${Date.now()}`, role: 'user', content: message };
        state.messages.push(userMessage);
        render();
        messageInput.value = '';
        
        const response = await api.sendMessage(message);
        updateState(response);
    }
    
    async function handleRestart() {
        if (state.isLoading) return;
        console.log("Requesting session restart...");
        const response = await api.restartSession();
        // Clear local messages and then update state from response
        state.messages = [];
        updateState(response);
    }

    async function handleDebugToggle() {
        if (state.isLoading) {
            // Revert the checkbox if a request is in flight
            debugToggle.checked = !debugToggle.checked;
            return;
        };
        console.log("Toggling debug mode...");
        const response = await api.toggleDebug();
        updateState(response);
    }


    /**
     * --- Initialization ---
     */

    async function initialize() {
        console.log("Initializing session...");
        const initialState = await api.startSession();
        state.messages = []; // Clear any potential stale messages
        updateState(initialState);
    }

    // Bind event listeners
    chatForm.addEventListener('submit', handleFormSubmit);
    restartButton.addEventListener('click', handleRestart);
    debugToggle.addEventListener('change', handleDebugToggle);

    // Start the application
    initialize();
});
