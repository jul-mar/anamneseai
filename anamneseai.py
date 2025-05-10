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
    # Custom styles with medical theme and custom color configuration
    Script("""
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            'medical-blue': '#0077b6',
            'medical-blue-light': '#90e0ef',
            'medical-blue-dark': '#03045e',
          }
        }
      }
    }
    """, type="text/javascript"),
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

    # Professional medical-themed styling
    if message.get("role") == "error":
        bubble_color = "bg-red-100 text-red-800"
        border_style = "border-l-4 border-red-500"
    elif is_user:
        bubble_color = "bg-white text-gray-800"
        border_style = "border-l-4 border-medical-blue"
    else:
        bubble_color = "bg-medical-blue text-white"
        border_style = ""
    
    # Get content, defaulting to an empty string if missing
    message_content = message.get("content", "")

    # Professional avatar for medical interface
    avatar_initial = "P" if is_user else "A"
    avatar_bg = "bg-medical-blue-dark text-white" if is_user else "bg-white text-medical-blue-dark border border-medical-blue"
    avatar = Div(
        Div(avatar_initial, cls=f"w-8 h-8 rounded-full {avatar_bg} flex items-center justify-center text-sm font-semibold shadow-sm"),
        cls="chat-image avatar"
    )

    # Professional role label
    role_label = "Patient" if is_user else "Assistant"

    return Div(
        avatar,
        Div(role_label, cls="chat-header text-xs font-medium mb-1 text-gray-600"),
        # Render content within <p> tags inside the bubble, applying medical styling
        Div(
            P(message_content), 
            cls=f"chat-bubble shadow-sm {bubble_color} {border_style} break-words prose prose-sm sm:prose-base rounded-lg px-4 py-3"
        ),
        cls=f"chat {chat_alignment}",
        id=f"message-{message.get('id', uuid.uuid4())}"
    )

# Modified ChatInterface to accept messages list
def ChatInterface(messages: list = None): # <--- Made messages parameter optional
    """Renders the full chat interface."""
    # Default to empty list if no messages provided
    if messages is None:
        messages = []
        
    # Welcome message if no messages exist
    if not messages:
        welcome_msg = {
            "id": "welcome-msg",
            "role": "assistant",
            "content": "Welcome to AnamneseAI. I'm a Chatbot that asks the patient questions while he is waiting for the appointment. The doctor can specify how the questions have to be answered and i will rephrase questions or ask again until i get sufficent answers. The doctor then gets a summary before seeing the patient. Here is an example question: How much do you smoke?"
        }
        messages = [welcome_msg]
        
    # Professional medical-themed chat box    
    chat_box = Div(
        *[ChatMessage(msg) for msg in messages],
        id="chat-box",
        cls="p-4 space-y-6 overflow-y-auto h-[calc(100vh-220px)] bg-white rounded-lg shadow-md border border-gray-200"
    )

    # Professional input styling
    user_input = Input(
        id="user-message-input",
        type="text", name="user_message",
        placeholder="Type your medical query...",
        cls="input bg-white border border-gray-300 focus:border-medical-blue focus:ring-2 focus:ring-medical-blue-light w-full flex-grow mr-2 rounded-lg",
        autofocus=True
    )

    # Professional button styling
    submit_button = Button(
        "Send",
        type="submit",
        cls="bg-medical-blue hover:bg-medical-blue-dark text-white font-medium py-2 px-6 rounded-lg transition-colors duration-200",
    )

    # Professional loading indicator
    loading_indicator = Div(
        id="loading-indicator", 
        cls="htmx-indicator flex items-center text-medical-blue ml-2",
        _innerHTML="""
        <svg class="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span class="text-sm font-medium">Processing...</span>
        """
    )

    chat_form = Form(
        user_input,
        submit_button,
        loading_indicator,
        hx_post="/chat",
        hx_target="#chat-box",
        hx_swap="beforeend",
        hx_on_htmx_after_on_load="this.closest('.container').querySelector('#chat-box').scrollTop = this.closest('.container').querySelector('#chat-box').scrollHeight",
        cls="p-4 flex items-center bg-gray-50 rounded-lg shadow-sm mt-4 sticky bottom-0 border border-gray-200", 
    )

    # Medical professional branding header
    header = Div(
        Div(
            # Medical logo/icon
            Div(
                _innerHTML="""
                <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-medical-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                """,
                cls="mr-3"
            ),
            # Title and subtitle
            Div(
                H1("AnamneseAI", cls="text-2xl font-bold text-medical-blue-dark"),
                P("Patient history Chatbot", cls="text-sm text-gray-600"),
                cls="flex flex-col"
            ),
            cls="flex items-center mb-2"
        ),
        # Subtle divider
        Div(cls="w-full h-px bg-gray-200 mb-4"),
        # Model info with medical styling
        Div(
            Div(
                _innerHTML="""
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                """,
                cls="text-medical-blue"
            ),
            Span(f"Powered by: {ACTUAL_MODEL_NAME_USED}", cls="text-xs text-gray-600"),
            cls="flex items-center justify-end mb-4"
        ),
        cls="bg-white rounded-lg shadow-sm p-4 mb-4 border border-gray-200"
    )

    return Div(
        header,
        chat_box,
        chat_form,
        cls="container mx-auto max-w-3xl p-4 flex flex-col h-screen font-sans bg-gray-50"
    )

# --- Routes ---

@rt("/")
async def get_chat_ui(session):
    """Serves the main chat page, loading history from session."""
    # Always create a new session ID and clear any existing chat messages
    session['session_id'] = str(uuid.uuid4())
    session['chat_messages'] = []  # Start with an empty chat history

    # Pass the empty chat history to the ChatInterface component
    return (
        Title("MedAssist AI - Professional Medical Assistant"),
        # Add favicon and meta tags appropriate for a medical application
        Link(rel="icon", href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚕️</text></svg>"),
        Meta(name="description", content="Professional AI assistant for medical professionals"),
        # Add viewport meta for better mobile experience
        Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
        # Add professional medical-themed styling to the body
        Style("""
            body {
                background-color: #f8fafc;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            }
            /* Custom scrollbar for a more professional look */
            ::-webkit-scrollbar {
                width: 8px;
                height: 8px;
            }
            ::-webkit-scrollbar-track {
                background: #f1f5f9;
            }
            ::-webkit-scrollbar-thumb {
                background: #cbd5e1;
                border-radius: 4px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: #94a3b8;
            }
        """),
        ChatInterface([])
    )


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