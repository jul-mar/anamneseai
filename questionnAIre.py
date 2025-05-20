# chat.py
from fasthtml.common import *
import ollama  # ollama python client
import uuid  # For unique IDs for messages
import datetime  # Not strictly needed for logic, but good to keep if it was used elsewhere
import os  # For creating session directory
import shutil  # For removing session directory

# -----------------------------------------------------------------------------
# LLM SERVICE LAYER
# -----------------------------------------------------------------------------
class LLMService:
    """Service class to handle LLM-related operations and configuration."""
    
    # Default configuration
    DEFAULT_HOST = "http://localhost:11434"
    DEFAULT_MODEL = "gemma3:4b-it-qat" # Corrected from gemma3:4b-it-qat as gemma2 is more common
    
    # System prompt configuration
    SYSTEM_PROMPT = """You are QuestionnAIre, a medical assistant chatbot designed to gather patient information while they wait for their appointment.

Your role is to:
1. Ask relevant questions about the patient's symptoms, medical history, and concerns
2. Gather complete information by asking follow-up questions when answers are insufficient
3. Be professional, empathetic, and respectful at all times
4. Follow specific questioning patterns requested by the doctor
5. Create a comprehensive but concise summary of the patient's history when requested

Remember:
- Don't use Markdown in your answers
- Be clear and precise in your questions
- Don't make medical diagnoses or recommendations
- Maintain a friendly, reassuring tone
- Respect patient privacy and be sensitive to personal health issues
- DON'T ask multiple questions at once. Ask one question and then wait for the answer before asking another question to avoid overwhelming the patient
"""

    def __init__(self, host=None, model_name=None):
        """Initialize the LLM service with the given host and model."""
        self.host = host or self.DEFAULT_HOST
        self.model_name = model_name or self.DEFAULT_MODEL
        self.client = None
        self.initialize_client()
    
    def initialize_client(self):
        """Initialize the Ollama client or fallback to mock client."""
        try:
            print(f"Attempting to connect to Ollama at {self.host}")
            self.client = ollama.Client(host=self.host)
            
            # Simple connection check
            models = self.client.list().get('models', [])
            available_models = [m.get('name', '') for m in models if isinstance(m, dict) and 'name' in m]
            
            if self.model_name in available_models:
                print(f"Successfully connected to Ollama. Using model: {self.model_name}")
            else:
                # Just use the configured model name regardless
                print(f"Model {self.model_name} not found in available models: {available_models}. Proceeding anyway.")
            
        except Exception as e:
            print(f"Error connecting to Ollama: {e}. Starting with mock client.")
            self.client = self._create_mock_client()
    
    def _create_mock_client(self):
        """Create a mock client for when Ollama connection fails."""
        class MockOllamaClient:
            def list(self):
                return {'models': []}

            def chat(self, model, messages):
                print("\n--- Using Mock Ollama Client ---")
                print("Reason: Ollama connection failed or model not found.")
                print("Please check Ollama is running and the specified model is pulled.")
                print("---------------------------------\n")
                return {'message': {'content': '*(Error: Could not connect to Ollama or model not found. Check server logs.)*'}}
        
        return MockOllamaClient()
    
    def get_model_name(self):
        """Get the name of the model being used."""
        return self.model_name
    
    def get_system_prompt(self):
        """Get the current system prompt."""
        return self.SYSTEM_PROMPT
    
    def chat(self, messages):
        """Send a chat request to the LLM and get the response."""
        try:
            # Prepare the messages with system prompt
            ollama_messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
            
            # Add user/assistant messages
            for msg in messages:
                if msg["role"] != "system":  # Skip any existing system messages
                    ollama_messages.append({"role": msg["role"], "content": msg["content"]})
            
            # Debug logging of the prompt being sent to the LLM
            print("\n----- SENDING PROMPT TO LLM -----")
            print(f"Model: {self.model_name}")
            for i, msg in enumerate(ollama_messages):
                print(f"\n[Message {i}] Role: {msg['role']}")
                print(f"Content: {msg['content'][:200]}..." if len(msg['content']) > 200 else f"Content: {msg['content']}")
            print("----- END OF PROMPT -----\n")
            
            # Send request to Ollama
            response = self.client.chat(
                model=self.model_name,
                messages=ollama_messages
            )
            return response.get('message', {}).get('content', 'No response from AI')
        
        except Exception as e:
            print(f"Error in chat: {e}")
            return "Sorry, there was an error processing your request."

# -----------------------------------------------------------------------------
# SESSION MANAGEMENT
# -----------------------------------------------------------------------------
class SessionManager:
    """Handles session-related operations for the chat application."""
    
    @staticmethod
    def initialize_session(session):
        """Initialize a new chat session."""
        # Initialize core session structure only if session_id is missing
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
            welcome_msg = {
                "id": "welcome-msg",
                "role": "assistant",
                "content": "Welcome to QuestionnAIre. I'm a Chatbot that asks the patient questions while they wait for the appointment. The doctor can specify how the questions have to be answered and I will rephrase questions or ask again until I get sufficient answers. The doctor then gets a summary before seeing the patient. Here is an example question: How much do you smoke?"
            }
            session['chat_messages'] = [welcome_msg]
            session['debug_mode_enabled'] = False # Initialize debug mode
        
        # Ensure debug_mode_enabled exists even if session_id was already there
        # This handles cases where an old session might exist without this flag
        if 'debug_mode_enabled' not in session:
             session['debug_mode_enabled'] = False
        if 'chat_messages' not in session: # Ensure chat_messages list exists
            session['chat_messages'] = []


    @staticmethod
    def add_message(session, role, content):
        """Add a message to the session chat history."""
        message_id = str(uuid.uuid4())
        message = {"id": message_id, "role": role, "content": content}
        
        if 'chat_messages' not in session: # Should be initialized by initialize_session
            session['chat_messages'] = []
            
        session['chat_messages'].append(message)
        return message
    
    @staticmethod
    def get_messages(session):
        """Get all messages from the session."""
        return session.get('chat_messages', [])
    
    @staticmethod
    def cleanup():
        """Clean up session data directories."""
        try:
            session_dir = ".sessions"
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                print(f"Removed session data directory: {session_dir}")
        except Exception as e:
            print(f"Error cleaning session data: {e}")

# -----------------------------------------------------------------------------
# UI COMPONENTS
# -----------------------------------------------------------------------------
class UIComponents:
    """UI components for the chat application."""
    
    @staticmethod
    def get_headers():
        """Return the header components for the application."""
        return (
            Script(src="https://cdn.tailwindcss.com"),
            Script(src="https://unpkg.com/htmx.org@1.9.10"),
            Script(src="https://unpkg.com/htmx.org@1.9.10/dist/ext/loading-states.js"),
            Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.10.1/dist/full.min.css"),
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
            Script("""
            document.addEventListener('DOMContentLoaded', function() {
                htmx.config.useTemplateFragments = true;
                htmx.config.indicatorClass = 'htmx-indicator';
                htmx.config.requestClass = 'htmx-request';
            });
            """, type="text/javascript"),
        )

    @staticmethod
    def get_head_components(model_name):
        """Return the head components for the application."""
        return (
            Title("QuestionnAIre - Professional Medical Assistant"),
            Link(rel="icon", href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚕️</text></svg>"),
            Meta(name="description", content="Professional AI assistant for taking a patients history"),
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            Style("""
                body { background-color: #f8fafc; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
                ::-webkit-scrollbar { width: 8px; height: 8px; }
                ::-webkit-scrollbar-track { background: #f1f5f9; }
                ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
                ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
                #loading-indicator { opacity: 0; transition: opacity 200ms ease-in; }
                #loading-indicator.processing { opacity: 1 !important; }
                .htmx-request .htmx-indicator { opacity: 1 !important; }
            """),
        )
    
    @staticmethod
    def chat_message(message):
        """Renders a single chat message using DaisyUI chat bubble component."""
        is_user = message.get("role") == "user"
        chat_alignment = "chat-end" if is_user else "chat-start"

        if message.get("role") == "error":
            bubble_color = "bg-red-100 text-red-800"
            border_style = "border-l-4 border-red-500"
        elif is_user:
            bubble_color = "bg-white text-gray-800"
            border_style = "border-l-4 border-medical-blue"
        else:
            bubble_color = "bg-medical-blue text-white"
            border_style = ""
        
        message_content = message.get("content", "")
        avatar_initial = "P" if is_user else "A"
        avatar_bg = "bg-medical-blue-dark text-white" if is_user else "bg-white text-medical-blue-dark border border-medical-blue"
        avatar = Div(
            Div(
                Span(avatar_initial, cls="inline-flex items-center justify-center w-full h-full"), 
                cls=f"w-8 h-8 rounded-full {avatar_bg} flex items-center justify-center text-sm font-semibold shadow-sm"
            ),
            cls="chat-image avatar"
        )
        role_label = "Patient" if is_user else "Assistant"
        return Div(
            avatar,
            Div(role_label, cls="chat-header text-xs font-medium mb-1 text-gray-600"),
            Div(
                P(message_content), 
                cls=f"chat-bubble shadow-sm {bubble_color} {border_style} break-words prose prose-sm sm:prose-base rounded-lg px-4 py-3"
            ),
            cls=f"chat {chat_alignment}",
            id=f"message-{message.get('id', uuid.uuid4())}"
        )

    @staticmethod
    def input_field():
        """Return the input field component."""
        return Input(
            id="user-message-input",
            type="text", name="user_message",
            placeholder="Type your medical query...",
            cls="input bg-white border border-gray-300 focus:border-medical-blue focus:ring-2 focus:ring-medical-blue-light w-full flex-grow mr-2 rounded-lg",
            autofocus=True
        )
    
    @staticmethod
    def loading_indicator():
        """Return the loading indicator component."""
        return Div(
            Div(
                _innerHTML="""
                <svg class="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                """,
                cls="inline-block"
            ),
            Span("Processing...", cls="text-sm font-medium"),
            id="loading-indicator", 
            cls="htmx-indicator flex items-center text-medical-blue ml-2",
            style="opacity: 0; transition: opacity 200ms ease-in;"
        )
    
    @staticmethod
    def submit_button():
        """Return the submit button component."""
        return Button(
            "Send",
            type="submit",
            cls="bg-medical-blue hover:bg-medical-blue-dark text-white font-medium py-2 px-6 rounded-lg transition-colors duration-200",
        )
    
    @staticmethod
    def header(model_name):
        """Return the header component for the chat interface."""
        return Div(
            Div(
                Div(
                    _innerHTML="""
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-medical-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    """,
                    cls="mr-3"
                ),
                Div(
                    H1("QuestionnAIre", cls="text-2xl font-bold text-medical-blue-dark"),
                    P("Patient history Chatbot", cls="text-sm text-gray-600"),
                    cls="flex flex-col"
                ),
                cls="flex items-center mb-2"
            ),
            Div(cls="w-full h-px bg-gray-200 mb-4"),
            Div(
                Div(
                    _innerHTML="""
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    """,
                    cls="text-medical-blue"
                ),
                Span(f"Powered by: {model_name}", cls="text-xs text-gray-600"),
                cls="flex items-center justify-end mb-4"
            ),
            cls="bg-white rounded-lg shadow-sm p-4 mb-4 border border-gray-200"
        )

    @staticmethod
    def debug_status_indicator_and_toggle_button(is_enabled: bool):
        status_text = "ON" if is_enabled else "OFF"
        button_text = "Disable Debug Mode" if is_enabled else "Enable Debug Mode"
        button_cls = "btn-warning" if is_enabled else "btn-outline btn-info" # DaisyUI button classes
        return Div(
            Span(f"Debug Mode: {status_text}", cls="mr-2 text-sm font-medium align-middle"),
            Button(
                button_text,
                hx_post="/toggle_debug",
                hx_target="#debug-status-container", 
                hx_swap="outerHTML",                
                cls=f"btn btn-xs {button_cls} align-middle" # DaisyUI button classes
            ),
            id="debug-status-container", 
            cls="py-2 text-center" 
        )

    @staticmethod
    def continue_debug_button():
        return Button(
            "Process AI Response",
            hx_post="/continue_debug",
            hx_target="#chat-box",      
            hx_swap="beforeend",        
            cls="btn btn-sm btn-accent mt-2" # DaisyUI button class
        )

    @staticmethod
    def clear_debug_action_area_component():
        """Returns an empty Div to clear the debug action area via OOB swap."""
        return Div(id="debug-action-area", hx_swap_oob="true")

    @staticmethod
    def chat_interface(messages, model_name, debug_mode_enabled: bool):
        """Renders the full chat interface."""
        if messages is None: messages = []
            
        chat_box = Div(
            *[UIComponents.chat_message(msg) for msg in messages],
            id="chat-box",
            # Adjusted height to account for debug toggle potentially taking space
            cls="p-4 space-y-6 overflow-y-auto h-[calc(100vh-290px)] bg-white rounded-lg shadow-md border border-gray-200" 
        )

        chat_form = Form(
            UIComponents.input_field(),
            UIComponents.submit_button(),
            UIComponents.loading_indicator(),
            hx_post="/chat",
            hx_target="#chat-box",
            hx_swap="beforeend",
            hx_indicator="#loading-indicator",
            hx_ext="loading-states",
            data_loading_delay="100",
            data_loading_class="processing",
            data_loading_target="#loading-indicator",
            data_loading_class_remove="opacity-0",
            hx_on_htmx_after_on_load="this.closest('.container').querySelector('#chat-box').scrollTop = this.closest('.container').querySelector('#chat-box').scrollHeight",
            cls="p-4 flex items-center bg-gray-50 rounded-lg shadow-sm mt-4 sticky bottom-0 border border-gray-200", 
        )

        debug_toggle_component = UIComponents.debug_status_indicator_and_toggle_button(debug_mode_enabled)

        return Div(
            UIComponents.header(model_name),
            chat_box,
            chat_form,
            Div(id="debug-action-area", cls="text-center mt-1 mb-1"), # Placeholder for "Process AI" button
            debug_toggle_component, # This is the Div with id="debug-status-container"
            cls="container mx-auto max-w-3xl p-4 flex flex-col h-screen font-sans bg-gray-50"
        )
    
    @staticmethod
    def clear_input_component():
        """Return the component to clear the input field after submission."""
        return Input(
            id="user-message-input",
            name="user_message",
            placeholder="Type your medical query...",
            cls="input bg-white border border-gray-300 focus:border-medical-blue focus:ring-2 focus:ring-medical-blue-light w-full flex-grow mr-2 rounded-lg",
            hx_swap_oob="true", 
            value="", 
            autofocus=True 
        )

# -----------------------------------------------------------------------------
# MAIN APPLICATION
# -----------------------------------------------------------------------------
llm_service = LLMService()
app = FastHTML(hdrs=UIComponents.get_headers())
rt = app.route

@rt("/")
async def get_chat_ui(session: dict):
    """Serves the main chat page, loading history from session."""
    SessionManager.initialize_session(session) 
    
    initial_debug_status = session.get('debug_mode_enabled', False)
    
    return (
        *UIComponents.get_head_components(llm_service.get_model_name()),
        UIComponents.chat_interface(
            SessionManager.get_messages(session), 
            llm_service.get_model_name(),
            initial_debug_status 
        )
    )

@rt("/toggle_debug")
async def toggle_debug_mode(session: dict):
    current_status = session.get('debug_mode_enabled', False)
    session['debug_mode_enabled'] = not current_status
    
    updated_toggle_button = UIComponents.debug_status_indicator_and_toggle_button(session['debug_mode_enabled'])
    
    components_to_return = [updated_toggle_button]

    if not session['debug_mode_enabled']:
        components_to_return.append(UIComponents.clear_debug_action_area_component())
        
    return tuple(components_to_return)

@rt("/chat")
async def post_chat_message(user_message: str, session: dict):
    """Handles incoming user messages, gets AI response, and updates chat via HTMX."""
    clear_input = UIComponents.clear_input_component()

    if not user_message or not user_message.strip():
        return clear_input

    user_msg_data = SessionManager.add_message(session, "user", user_message)
    user_msg_component = UIComponents.chat_message(user_msg_data)
    
    components_to_return = [user_msg_component, clear_input]

    if session.get('debug_mode_enabled', False):
        # In debug mode, add user message and the "Process AI" button via OOB swap
        process_ai_button_container = Div(
            UIComponents.continue_debug_button(), 
            id="debug-action-area", 
            hx_swap_oob="true"      
        )
        components_to_return.append(process_ai_button_container)
    else:
        # Debug mode is off, process AI response immediately
        session_chat_messages = SessionManager.get_messages(session)
        ai_response_content = llm_service.chat(session_chat_messages)
        ai_msg_data = SessionManager.add_message(session, "assistant", ai_response_content)
        ai_message_component = UIComponents.chat_message(ai_msg_data)
        components_to_return.append(ai_message_component)
        components_to_return.append(UIComponents.clear_debug_action_area_component())
           
    return tuple(components_to_return)

@rt("/continue_debug")
async def continue_ai_response(session: dict):
    """Triggers AI response when the 'Process AI Response' button is clicked."""
    if not session.get('debug_mode_enabled', False):
        return UIComponents.clear_debug_action_area_component()

    session_chat_messages = SessionManager.get_messages(session)
    
    if not session_chat_messages or session_chat_messages[-1]["role"] != "user":
       return UIComponents.clear_debug_action_area_component()

    ai_response_content = llm_service.chat(session_chat_messages)
    ai_msg_data = SessionManager.add_message(session, "assistant", ai_response_content)
    ai_message_component = UIComponents.chat_message(ai_msg_data)
    
    return ai_message_component, UIComponents.clear_debug_action_area_component()

# -----------------------------------------------------------------------------
# APPLICATION ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Starting QuestionnAIre Chatbot...")
    print(f"Using LLM model: {llm_service.get_model_name()}")
    print(f"System prompt configured with {len(llm_service.get_system_prompt())} characters")
    
    SessionManager.cleanup()
    serve(port=5001)