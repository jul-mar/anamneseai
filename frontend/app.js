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
                credentials: 'include',
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
        
        // Use our custom classes defined in style.css
        let bubbleClasses = 'chat-bubble';
        if (message.role === 'error') {
            bubbleClasses += ' bg-red-100 text-red-700'; // Using Tailwind defaults for error
        } else if (isUser) {
            bubbleClasses += ' bg-primary text-primary-content';
        } else {
            bubbleClasses += ' bg-secondary text-secondary-content';
        }

        const avatarInitial = isUser ? 'P' : 'A';
        const avatarClasses = isUser ? 'bg-primary text-primary-content' : 'bg-gray-300 text-black';

        const messageDiv = document.createElement('div');
        messageDiv.className = `chat ${chatAlignment}`;
        messageDiv.innerHTML = `
            <div class="chat-image avatar placeholder">
                <div class="w-10 rounded-full font-semibold ${avatarClasses}">
                    <span>${avatarInitial}</span>
                </div>
            </div>
            <div class="chat-header text-xs text-neutral-muted mb-1">
                ${message.role.charAt(0).toUpperCase() + message.role.slice(1)}
            </div>
            <div class="${bubbleClasses} whitespace-pre-wrap break-words shadow-sm">${message.content}</div>
        `;
        return messageDiv;
    }

    function render() {
        // Clear chatbox and render messages
        chatBox.innerHTML = '';
        state.messages.forEach(msg => {
            chatBox.appendChild(renderMessage(msg));
        });
        chatBox.scrollTop = chatBox.scrollHeight;
        
        // Update debug toggle state
        debugToggle.checked = state.debugMode;

        // --- Form & Button State Control ---
        const isWaitingForUser = state.botState === 'EXPECTING_USER_ANSWER';
        const formDisabled = state.isLoading || !isWaitingForUser;
        
        messageInput.disabled = formDisabled;
        sendButton.disabled = formDisabled;

        if (formDisabled) {
            messageInput.classList.remove('bg-gray-100');
            messageInput.classList.add('bg-gray-200', 'opacity-70');
            messageInput.placeholder = 'Bitte warten...';
        } else {
            messageInput.classList.remove('bg-gray-200', 'opacity-70');
            messageInput.classList.add('bg-gray-100');
            messageInput.placeholder = 'Ihre Antwort...';
            messageInput.focus();
        }

        // --- Loading Indicators Control ---
        if (state.isLoading) {
            sendButton.classList.add('loading');
            statusIndicator.textContent = 'lädt...';
            statusIndicator.className = 'ml-2 font-mono badge badge-outline badge-info';
        } else {
            sendButton.classList.remove('loading');
            statusIndicator.textContent = 'bereit';
            statusIndicator.className = 'ml-2 font-mono badge badge-outline badge-success';
        }
    }

    function setLoading(isLoading) {
        state.isLoading = isLoading;
        render(); // The render function is now the single source of truth for UI state
    }

    function renderError(errorMessage) {
        const errorMsg = {
            id: `err-${Date.now()}`,
            role: 'error',
            content: `Ein Fehler ist aufgetreten:\n${errorMessage}`
        };
        state.messages.push(errorMsg);
        render(); // Re-render to show the error message

        // Also update status indicator immediately for clarity
        statusIndicator.textContent = 'Fehler';
        statusIndicator.className = 'ml-2 font-mono badge badge-outline badge-error';
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
