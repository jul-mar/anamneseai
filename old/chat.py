# chat.py
from fasthtml.common import *
import ollama # ollama python client
import uuid # For unique IDs for messages
import datetime # Not strictly needed for logic, but good to keep if it was used elsewhere
import os # For creating session directory
import shutil # For removing session directory

# --- Configuration ---
OLLAMA_HOST = "http://localhost:11434" # Default Ollama API endpoint
MODEL_NAME = "gemma3:4b-it-qat" # Target model - using 2b-it as it's common and smaller

# --- Application Setup ---
# Note: For persistent sessions in production, you might need a more robust backend
# store than the default in-memory cookie storage, but for development, this is fine.
hdrs = (
    Script(src="https://cdn.tailwindcss.com"),
    Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.10.1/dist/full.min.css"),
)

# Ensure you have Starlette SessionMiddleware configured if not using Fasthtml's default setup
# If using `serve`, Fasthtml likely handles basic session setup.
# If deploying via ASGI, you might need to explicitly add SessionMiddleware.
# Example if needed manually:
# from starlette.middleware import Middleware
# from starlette.middleware.sessions import SessionMiddleware
# middleware = [ Middleware(SessionMiddleware, secret_key="your-secret-key-here") ]
# app = FastHTML(hdrs=hdrs, middleware=middleware)
# Using serve() with FastHTML usually adds basic SessionMiddleware automatically.

app = FastHTML(hdrs=hdrs)
rt = app.route

# REMOVED: Global chat_messages list - state is now per session

# --- Ollama Client Setup ---
# Initialize client as None initially
client = None
ACTUAL_MODEL_NAME_USED = MODEL_NAME

class MockOllamaClient:
    """A mock client to allow the UI to load if Ollama connection fails."""
    def list(self):
        # Simulate the dictionary structure expected by the parsing logic
        return {'models': []}

    def chat(self, model, messages):
        # Return a structure simulating a successful chat response
        print("\n--- Using Mock Ollama Client ---")
        print("Reason: Ollama connection failed or model not found.")
        print("Please check Ollama is running and the specified model is pulled.")
        print("---------------------------------\n")
        return {'message': {'content': '*(Error: Could not connect to Ollama or model not found. Check server logs.)*'}}

try:
    print(f"Attempting to connect to Ollama at {OLLAMA_HOST}")
    client = ollama.Client(host=OLLAMA_HOST)
    
    # Simple connection check - no detailed error handling
    models = client.list().get('models', [])
    available_models = [m.get('name', '') for m in models if isinstance(m, dict) and 'name' in m]
    
    if MODEL_NAME in available_models:
        ACTUAL_MODEL_NAME_USED = MODEL_NAME
    else:
        # Just use the configured model name regardless
        ACTUAL_MODEL_NAME_USED = MODEL_NAME
    
    print(f"Successfully connected to Ollama. Using model: {ACTUAL_MODEL_NAME_USED}")
    
except Exception:
    print(f"Error connecting to Ollama. Starting with mock client.")
    client = MockOllamaClient()
    ACTUAL_MODEL_NAME_USED = MODEL_NAME


# --- Components ---

def ChatMessage(message: dict):
    """Renders a single chat message using DaisyUI chat bubble component."""
    is_user = message.get("role") == "user"
    chat_alignment = "chat-end" if is_user else "chat-start"

    # Determine bubble color based on role or status
    if message.get("role") == "error":
        bubble_color = "chat-bubble-error"
    elif is_user:
        bubble_color = "chat-bubble-primary"
    else:
        bubble_color = "chat-bubble-secondary"
    
    # Get content, defaulting to an empty string if missing
    message_content = message.get("content", "")

    # Avatar (optional - uncomment to use)
    # avatar_initial = message.get("role", "?")[0].upper()
    # avatar = Div(
    #     Div(avatar_initial, cls="w-10 h-10 rounded-full bg-neutral-focus text-neutral-content flex items-center justify-center text-xl font-semibold") ,
    #     cls="chat-image avatar"
    # )

    return Div(
        # avatar, # Uncomment to add avatars
        # Use .get() with default for safety
        Div(message.get("role", "Unknown").capitalize(), cls="chat-header text-xs opacity-70 mb-1"),
        # Render content within <p> tags inside the bubble, applying prose classes
        Div(P(message_content), cls=f"chat-bubble {bubble_color} break-words prose prose-sm sm:prose-base"), # Responsive prose
        cls=f"chat {chat_alignment}",
        id=f"message-{message.get('id', uuid.uuid4())}" # Default ID if missing
    )

# Modified ChatInterface to accept messages list
def ChatInterface(messages: list = None): # <--- Made messages parameter optional
    """Renders the full chat interface."""
    # Default to empty list if no messages provided
    if messages is None:
        messages = []
        
    chat_box = Div(
        *[ChatMessage(msg) for msg in messages], # <--- Renders messages from the passed-in list
        id="chat-box",
        cls="p-4 space-y-4 overflow-y-auto h-[calc(100vh-220px)] bg-base-200 rounded-lg shadow-inner"
    )

    user_input = Input(
        id="user-message-input",
        type="text", name="user_message",
        placeholder="Type your message...",
        cls="input input-bordered w-full flex-grow mr-2",
        autofocus=True # Add autofocus for better UX
    )

    submit_button = Button(
        "Send",
        type="submit",
        cls="btn btn-primary", # Changed from btn-square to regular button with text
    )

    chat_form = Form(
        user_input,
        submit_button,
        # Loading indicator shown while HTMX request is pending
        Div(id="loading-indicator", cls="htmx-indicator loading loading-spinner loading-sm ml-2"),
        hx_post="/chat",
        hx_target="#chat-box",
        hx_swap="beforeend", # Append the new messages to the chat-box
        # Adding a small script to scroll to bottom after new message is added via HTMX
        # This targets the chat-box within the same container
        hx_on_htmx_after_on_load="this.closest('.container').querySelector('#chat-box').scrollTop = this.closest('.container').querySelector('#chat-box').scrollHeight",
        cls="p-4 flex items-center bg-base-100 rounded-lg shadow-md mt-4 sticky bottom-0", # Sticky form at the bottom
    )

    return Div(
        H1("Ollama AI Chatbot", cls="text-3xl font-bold text-center my-4 text-primary"),
        Div(f"Using model: {ACTUAL_MODEL_NAME_USED}", cls="text-center text-xs text-base-content opacity-70 mb-4"),
        chat_box,
        chat_form,
        cls="container mx-auto max-w-3xl p-4 flex flex-col h-screen font-sans"
    )

# --- Routes ---

@rt("/")
async def get_chat_ui(session):
    """Serves the main chat page, loading history from session."""
    # Always create a new session ID and clear any existing chat messages
    session['session_id'] = str(uuid.uuid4())
    session['chat_messages'] = []  # Start with an empty chat history

    # Pass the empty chat history to the ChatInterface component
    return Title("AI Chatbot"), ChatInterface([])


@rt("/chat")
async def post_chat_message(user_message: str, session):
    """Handles incoming user messages, gets AI response, and updates chat via HTMX."""
    # Component to clear the input field after submission
    clear_input_component = Input(
        id="user-message-input",
        name="user_message",
        placeholder="Type your message...",
        cls="input input-bordered w-full flex-grow mr-2",
        hx_swap_oob="true", # Swap outerHTML of the element with this ID
        value="", # Set value to empty
        autofocus=True # Re-focus the input field
    )

    # If the message is empty, just clear the input and do nothing else
    if not user_message or not user_message.strip():
        return clear_input_component

    # --- Get messages from session ---
    # Fetch the current chat history for this session
    session_chat_messages = session.get('chat_messages', [])
    # --- End Get ---

    # Add the user's message to the session history
    user_msg_id = str(uuid.uuid4())
    user_msg_data = {"id": user_msg_id, "role": "user", "content": user_message}
    session_chat_messages.append(user_msg_data)

    # Prepare history for Ollama API call (only include role and content)
    # This now uses the session-specific chat_messages list
    ollama_history = [{"role": msg["role"], "content": msg["content"]} for msg in session_chat_messages]

    # Component for the user's new message to be inserted into the chat box
    user_message_component = ChatMessage(user_msg_data)

    # Simplified API call with minimal error handling
    try:
        response = client.chat(
            model=ACTUAL_MODEL_NAME_USED,
            messages=ollama_history
        )
        ai_response_content = response.get('message', {}).get('content', 'No response from AI')
    except Exception as e:
        print(f"Error in chat: {e}")
        ai_response_content = "Sorry, there was an error processing your request."

    # Add the AI's response to the session history
    ai_msg_id = str(uuid.uuid4())
    ai_msg_data = {"id": ai_msg_id, "role": "assistant", "content": ai_response_content}
    session_chat_messages.append(ai_msg_data)

    # --- Save the updated messages list back to the session ---
    session['chat_messages'] = session_chat_messages
    # --- End Save ---

    # Component for the AI's new message to be inserted into the chat box
    ai_message_component = ChatMessage(ai_msg_data)

    # Return the components that HTMX will swap in.
    # user_message_component and ai_message_component will be appended to #chat-box
    # clear_input_component will replace the input field via hx-swap-oob
    return user_message_component, ai_message_component, clear_input_component


# --- Clean up any session data directories ---
def clean_session_data():
    """Clean up any session data that might persist between runs"""
    try:
        # Path to the default session data directory used by Starlette's SessionMiddleware
        session_dir = ".sessions"
        
        # Check if the directory exists and remove it
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            print(f"Removed session data directory: {session_dir}")
    except Exception as e:
        print(f"Error cleaning session data: {e}")


# --- Main ---
if __name__ == "__main__":
    print(f"Starting FastHTML Ollama Chatbot...")
    print(f"Attempting to use Ollama model: {MODEL_NAME} via {OLLAMA_HOST}")
    print(f"Actual model configured for use: {ACTUAL_MODEL_NAME_USED}")
    
    print(f"Ollama client initialized using model: {ACTUAL_MODEL_NAME_USED}")
    
    # Clean up any existing session data before starting
    clean_session_data()
    
    # Using FastHTML's built-in serve function
    # This includes basic SessionMiddleware by default
    serve(port=5001)