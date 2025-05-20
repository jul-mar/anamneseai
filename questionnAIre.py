# chat.py
from fasthtml.common import *
import ollama  # ollama python client
import uuid  # For unique IDs for messages
import datetime  # Not strictly needed for logic, but good to keep if it was used elsewhere
import os  # For creating session directory
import shutil  # For removing session directory
import json # For loading questions from JSON file
from starlette.responses import RedirectResponse, Response # Ensure Response is imported

# -----------------------------------------------------------------------------
# QUESTION SERVICE
# -----------------------------------------------------------------------------
class QuestionService:
    """Handles loading and providing access to predefined questions."""

    def __init__(self, filepath="questions.json"):
        """
        Initializes the QuestionService by loading questions from a JSON file.
        Args:
            filepath (str): The path to the JSON file containing the questions.
        """
        self.filepath = filepath
        self._questions_list = []  # To maintain order
        self._questions_by_id = {} # For quick lookup by ID
        self._ordered_ids = []     # To easily get next/first
        self._load_questions()

    def _load_questions(self):
        """Loads questions from the specified JSON file."""
        try:
            # Ensure the questions.json file exists in the same directory as chat.py
            # For robustness, especially in different execution environments,
            # construct the path relative to this script's directory.
            base_dir = os.path.dirname(os.path.abspath(__file__))
            absolute_filepath = os.path.join(base_dir, self.filepath)

            if not os.path.exists(absolute_filepath):
                print(f"Error: Questions file not found at {absolute_filepath}")
                # Create a dummy questions.json if not found, for graceful failure
                # or to allow the app to start even if misconfigured.
                print(f"Creating a dummy '{self.filepath}' with sample data.")
                sample_questions = [
                    {"id": "sample_q1", "text": "This is a sample question as questions.json was not found. Please create it."},
                ]
                with open(absolute_filepath, 'w') as f:
                    json.dump(sample_questions, f, indent=2)
                self._questions_list = sample_questions
            else:
                with open(absolute_filepath, 'r') as f:
                    self._questions_list = json.load(f)
            
            # Populate lookup structures
            self._questions_by_id = {} # Clear previous data before reloading
            self._ordered_ids = []     # Clear previous data
            for index, question_data in enumerate(self._questions_list):
                if "id" not in question_data or "text" not in question_data:
                    print(f"Warning: Question at index {index} in '{self.filepath}' is missing 'id' or 'text'. Skipping.")
                    continue
                q_id = question_data["id"]
                self._questions_by_id[q_id] = question_data
                self._ordered_ids.append(q_id)
            
            if not self._ordered_ids: # Check if any valid questions were actually loaded
                 print(f"Warning: No valid questions loaded from {self.filepath}. The question list is empty.")


        except FileNotFoundError:
            print(f"Error: Questions file not found at {absolute_filepath}. Please create it.")
            # Fallback to empty list or handle as critical error
            self._questions_list = []
            self._questions_by_id = {}
            self._ordered_ids = []
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {self.filepath}. Please check its format.")
            self._questions_list = []
            self._questions_by_id = {}
            self._ordered_ids = []
        except Exception as e:
            print(f"An unexpected error occurred while loading questions: {e}")
            self._questions_list = []
            self._questions_by_id = {}
            self._ordered_ids = []

    def get_question_by_id(self, question_id):
        """
        Retrieves a question by its ID.
        Args:
            question_id (str): The ID of the question to retrieve.
        Returns:
            dict: The question data (e.g., {"id": "q1", "text": "..."}), or None if not found.
        """
        return self._questions_by_id.get(question_id)

    def get_first_question_id(self):
        """
        Gets the ID of the first question in the sequence.
        Returns:
            str: The ID of the first question, or None if no questions are loaded.
        """
        return self._ordered_ids[0] if self._ordered_ids else None

    def get_next_question_id(self, current_question_id):
        """
        Gets the ID of the question that follows the given current_question_id.
        Args:
            current_question_id (str): The ID of the current question.
        Returns:
            str: The ID of the next question, or None if the current question is the last one or not found.
        """
        try:
            current_index = self._ordered_ids.index(current_question_id)
            if current_index < len(self._ordered_ids) - 1:
                return self._ordered_ids[current_index + 1]
            else:
                return None  # Current question is the last one
        except ValueError:
            return None # current_question_id not found in the list

    def get_all_question_ids(self):
        """
        Gets a list of all question IDs in order.
        Returns:
            list: A list of strings, where each string is a question ID.
        """
        return list(self._ordered_ids)

    def get_question_text_by_id(self, question_id):
        """
        Retrieves the text of a question by its ID.
        Args:
            question_id (str): The ID of the question.
        Returns:
            str: The text of the question, or None if not found.
        """
        question = self.get_question_by_id(question_id)
        return question.get("text") if question else None

# -----------------------------------------------------------------------------
# LLM SERVICE LAYER
# -----------------------------------------------------------------------------
class LLMService:
    """Service class to handle LLM-related operations and configuration."""
    
    # Default configuration
    DEFAULT_HOST = "http://localhost:11434"
    DEFAULT_MODEL = "gemma2:latest" # Using a common Ollama model name
    
    # System prompt configuration - THIS WILL BE UPDATED IN A LATER STEP
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
            
            models_response = self.client.list() # Ollama's list() returns a dict
            models = models_response.get('models', []) if isinstance(models_response, dict) else []
            available_models = [m.get('name', '') for m in models if isinstance(m, dict) and 'name' in m]
            
            if self.model_name in available_models:
                print(f"Successfully connected to Ollama. Using model: {self.model_name}")
            else:
                print(f"Warning: Model '{self.model_name}' not found in available models: {available_models}. Proceeding with '{self.model_name}' but it might fail if not pulled.")
            
        except Exception as e:
            print(f"Error connecting to Ollama: {e}. Starting with mock client.")
            self.client = self._create_mock_client()
    
    def _create_mock_client(self):
        """Create a mock client for when Ollama connection fails."""
        class MockOllamaClient:
            def list(self):
                return {'models': []}

            def chat(self, model, messages, format=None, options=None): # Added format and options for compatibility
                print("\n--- Using Mock Ollama Client ---")
                print("Reason: Ollama connection failed or model not found.")
                print("Please check Ollama is running and the specified model is pulled.")
                print("---------------------------------\n")
                # If format is json, mock a json response for tool call
                if format == 'json':
                    mock_tool_call = {
                        "tool_name": "mark_question_sufficient",
                        "arguments": {
                            "question_id": "mock_q_id",
                            "brief_acknowledgement": "Okay, thank you. (Mocked)"
                        }
                    }
                    return {'message': {'content': json.dumps(mock_tool_call)}}
                return {'message': {'content': '*(Error: Could not connect to Ollama or model not found. Mock response.)*'}}
        
        return MockOllamaClient()
    
    def get_model_name(self):
        """Get the name of the model being used."""
        return self.model_name
    
    def get_system_prompt(self):
        """Get the current system prompt."""
        return self.SYSTEM_PROMPT
    
    def chat(self, messages_for_llm, expect_json_response=False):
        """
        Send a chat request to the LLM and get the response.
        Args:
            messages_for_llm (list): The list of messages to send to the LLM.
            expect_json_response (bool): If True, ask Ollama to return JSON.
        Returns:
            str: The content of the LLM's response.
        """
        try:
            # Debug logging of the prompt being sent to the LLM
            print("\n----- SENDING PROMPT TO LLM -----")
            print(f"Model: {self.model_name}")
            print(f"Expecting JSON response: {expect_json_response}")
            for i, msg in enumerate(messages_for_llm):
                print(f"\n[Message {i}] Role: {msg['role']}")
                content_to_log = msg['content']
                print(f"Content: {content_to_log[:300]}..." if len(content_to_log) > 300 else f"Content: {content_to_log}")
            print("----- END OF PROMPT -----\n")
            
            request_params = {
                "model": self.model_name,
                "messages": messages_for_llm
            }
            if expect_json_response:
                request_params["format"] = "json"
                # request_params["options"] = {"temperature": 0.0} # Lower temp for more deterministic JSON

            response = self.client.chat(**request_params)
            
            response_content = response.get('message', {}).get('content', 'No response from AI')
            print(f"\n----- RECEIVED RESPONSE FROM LLM -----\nContent: {response_content}\n-----------------------------------\n")
            return response_content
        
        except Exception as e:
            print(f"Error in chat: {e}")
            # If expecting JSON and an error occurs, return a string that won't parse as our tool call
            if expect_json_response:
                return '{"error": "LLM chat failed"}' 
            return "Sorry, there was an error processing your request."

# -----------------------------------------------------------------------------
# SESSION MANAGEMENT
# -----------------------------------------------------------------------------
class SessionManager:
    """Handles session-related operations for the chat application."""
    
    @staticmethod
    def initialize_session(session, first_question_id=None, first_question_text=None):
        """Initialize a new chat session."""
        # Clear existing session keys to ensure a fresh start,
        # but keep 'session_id' and 'debug_mode_enabled' if they exist from a previous interaction within the same browser session.
        # This is a bit nuanced. If session.clear() was called before this, then it's truly new.
        # If we are re-initializing an existing session object, we want to reset specific chat state.
        
        # Store session_id and debug_mode_enabled if they exist
        existing_session_id = session.get('session_id')
        existing_debug_mode = session.get('debug_mode_enabled', False) # Default to False if not present

        session.clear() # Clear all keys

        if existing_session_id:
            session['session_id'] = existing_session_id
        else:
            session['session_id'] = str(uuid.uuid4())
        
        session['debug_mode_enabled'] = existing_debug_mode # Restore or set default


        welcome_msg_content = "Welcome to QuestionnAIre. I'm here to ask a few questions about your health before your appointment. Let's start."
        
        welcome_msg = {
            "id": "welcome-msg",
            "role": "assistant",
            "content": welcome_msg_content
        }
        session['chat_messages'] = [welcome_msg] # Chat history for display
        
        # New state variables for questionnaire flow
        session['current_question_id'] = None 
        session['current_question_text'] = "" 
        session['collected_answers'] = {} 
        session['current_question_follow_up_count'] = 0
        session['bot_state'] = "INIT" 
        
        print(f"Session initialized/re-initialized. ID: {session['session_id']}, Debug: {session['debug_mode_enabled']}")


    @staticmethod
    def add_message_to_display_chat(session, role, content, msg_id=None):
        """Add a message to the session chat history for UI display."""
        if not msg_id:
            msg_id = str(uuid.uuid4())
        message = {"id": msg_id, "role": role, "content": content}
        
        if 'chat_messages' not in session:
            session['chat_messages'] = [] # Should be set by initialize_session
            
        session['chat_messages'].append(message)
        return message 
    
    @staticmethod
    def add_exchange_to_collected_answers(session, question_id, role, content):
        """Adds an exchange (user answer or bot follow-up) to the collected answers for a specific question."""
        if question_id not in session['collected_answers']:
            session['collected_answers'][question_id] = []
        session['collected_answers'][question_id].append({"role": role, "content": content})

    @staticmethod
    def get_display_messages(session):
        """Get all messages for UI display from the session."""
        return session.get('chat_messages', [])
    
    @staticmethod
    def cleanup():
        """Clean up session data directories."""
        try:
            # This cleanup is for Starlette's default file-based sessions.
            # If using cookie-based sessions, this might not be necessary or relevant.
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

        if message.get("role") == "error": # For explicit error messages in chat
            bubble_color = "bg-red-100 text-red-800"
            border_style = "border-l-4 border-red-500"
        elif is_user:
            bubble_color = "bg-white text-gray-800" # User messages are white
            border_style = "border-l-4 border-medical-blue"
        else: # Assistant messages
            bubble_color = "bg-medical-blue text-white"
            border_style = ""
        
        message_content = message.get("content", "")
        avatar_initial = "P" if is_user else "A" # Patient vs Assistant
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
                P(message_content, cls="whitespace-pre-wrap"), # Allow line breaks from LLM
                cls=f"chat-bubble shadow-sm {bubble_color} {border_style} break-words prose prose-sm sm:prose-base rounded-lg px-4 py-3"
            ),
            cls=f"chat {chat_alignment}",
            id=f"message-{message.get('id', uuid.uuid4())}" # Use provided ID or generate one
        )

    @staticmethod
    def input_field(disabled=False): # Added disabled parameter
        """Return the input field component."""
        attrs = {
            "id": "user-message-input",
            "type": "text", "name": "user_message",
            "placeholder": "Type your medical query...",
            "cls": "input bg-white border border-gray-300 focus:border-medical-blue focus:ring-2 focus:ring-medical-blue-light w-full flex-grow mr-2 rounded-lg",
            "autofocus": True
        }
        if disabled:
            attrs["disabled"] = True
            attrs["placeholder"] = "Conversation ended or bot is processing..."
        return Input(**attrs)
    
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
    def submit_button(disabled=False): # Added disabled parameter
        """Return the submit button component."""
        attrs = {
            "type": "submit",
            "cls": "bg-medical-blue hover:bg-medical-blue-dark text-white font-medium py-2 px-6 rounded-lg transition-colors duration-200",
            "data_loading_disable": True 
        }
        if disabled:
            attrs["disabled"] = True
        return Button("Send", **attrs)
    
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
        button_cls = "btn-warning" if is_enabled else "btn-outline btn-info" 
        return Div(
            Span(f"Debug Mode: {status_text}", cls="mr-2 text-sm font-medium align-middle"),
            Button(
                button_text,
                hx_post="/toggle_debug",
                hx_target="#debug-status-container", 
                hx_swap="outerHTML",                
                cls=f"btn btn-xs {button_cls} align-middle" 
            ),
            id="debug-status-container", 
            cls="py-1 text-center" 
        )

    @staticmethod
    def continue_debug_button():
        return Button(
            "Process AI Response / Next Step", 
            hx_post="/continue_debug_or_next_step", 
            hx_target="#chat-box",      
            hx_swap="beforeend", 
            cls="btn btn-sm btn-accent mt-1" 
        )

    @staticmethod
    def clear_debug_action_area_component():
        return Div(id="debug-action-area", hx_swap_oob="true")

    @staticmethod
    def restart_button():
        """Returns the restart chat button component."""
        return Button(
            "Restart Chat",
            hx_post="/restart_chat",
            # The server will respond with HX-Refresh: true header
            cls="btn btn-sm btn-error btn-outline mt-1" 
        )

    @staticmethod
    def chat_interface(messages, model_name, debug_mode_enabled: bool, bot_state: str):
        """Renders the full chat interface."""
        if messages is None: messages = []
            
        chat_box_height = "h-[calc(100vh-320px)]" # Adjusted height for more controls
        chat_box = Div(
            *[UIComponents.chat_message(msg) for msg in messages],
            id="chat-box",
            cls=f"p-4 space-y-6 overflow-y-auto {chat_box_height} bg-white rounded-lg shadow-md border border-gray-200" 
        )

        form_is_disabled = bot_state in ["GENERATING_SUMMARY", "DONE", "WAITING_TO_ASK_PREDEFINED"] and not (debug_mode_enabled and bot_state == "WAITING_TO_ASK_PREDEFINED")


        chat_form_classes = "p-4 flex items-center bg-gray-50 rounded-lg shadow-sm mt-4 sticky bottom-0 border border-gray-200"
        if form_is_disabled:
            chat_form_classes += " opacity-50"

        chat_form = Form(
            UIComponents.input_field(disabled=form_is_disabled),
            UIComponents.submit_button(disabled=form_is_disabled),
            UIComponents.loading_indicator(),
            hx_post="/chat",
            hx_target="#chat-box", 
            hx_swap="beforeend",    
            hx_indicator="#loading-indicator",
            hx_ext="loading-states",
            data_loading_delay="100",
            data_loading_class="processing",
            data_loading_target="#loading-indicator", 
            data_loading_class_remove="", 
            hx_on_htmx_after_on_load="this.closest('.container').querySelector('#chat-box').scrollTop = this.closest('.container').querySelector('#chat-box').scrollHeight; if(document.activeElement.tagName === 'BUTTON' && !document.getElementById('user-message-input').disabled) { document.getElementById('user-message-input').focus(); }",
            cls=chat_form_classes,
        )

        debug_toggle_component = UIComponents.debug_status_indicator_and_toggle_button(debug_mode_enabled)
        restart_chat_button_component = UIComponents.restart_button()
        
        # Container for bottom controls
        controls_container = Div(
            Div(id="debug-action-area", cls="text-center mt-1 mb-1"), # For continue_debug_button
            debug_toggle_component,
            restart_chat_button_component,
            cls="mt-1 space-y-2" # Add some spacing between control groups
        )

        return Div(
            UIComponents.header(model_name),
            chat_box,
            chat_form,
            controls_container,
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
            autofocus=True # Re-focus only if not disabled
        )

# -----------------------------------------------------------------------------
# MAIN APPLICATION
# -----------------------------------------------------------------------------
# Initialize services
question_service = QuestionService() 
llm_service = LLMService()

app = FastHTML(hdrs=UIComponents.get_headers())
rt = app.route


async def _trigger_initial_bot_action(session: dict):
    """
    Helper function to set the bot's initial state for asking the first question.
    Returns a list of OOB HTMX components if needed (e.g., for debug mode).
    """
    components = []
    if session.get('bot_state') == "INIT":
        first_q_id = question_service.get_first_question_id()
        if first_q_id:
            session['current_question_id'] = first_q_id
            session['current_question_text'] = question_service.get_question_text_by_id(first_q_id)
            session['bot_state'] = "WAITING_TO_ASK_PREDEFINED" 
            print(f"INIT: Set to ask first question: {first_q_id}. Bot state: {session['bot_state']}")

            if session.get('debug_mode_enabled', False): 
                components.append(
                    Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true")
                )
            else:
                # If not in debug, we want to immediately trigger the bot to ask the first question.
                # This can be done by returning components from handle_bot_turn.
                # This function is called during GET / , so OOB swaps are what we can return.
                # The main page is already being rendered.
                # We need a way for the client to immediately make another request if not in debug.
                # For now, handle_bot_turn will be called by /continue_debug_or_next_step or /chat.
                # The user will see the welcome message, then the first question if not in debug mode (after a very brief moment or next interaction).
                # To make it truly immediate without debug, we might need an hx-trigger="load" on a component.
                # Let's simplify: the first action will be triggered by /continue_debug_or_next_step if debug,
                # or the first /chat if not debug (though /chat expects user input).
                # The most straightforward is that if not in debug, the first question is asked via handle_bot_turn
                # called from /continue_debug_or_next_step, which means we might need to auto-trigger that if not in debug.
                # This is getting complex for initial load.
                # Let's ensure the first question is asked when the user first interacts or if debug "next step" is pressed.
                # The _trigger_initial_bot_action will primarily set the state.
                # The first actual bot message will appear on first user send or "next step".
                # This is slightly different from auto-asking on load.
                # To auto-ask on load (if not debug):
                # We could have the root ("/") route call handle_bot_turn if not debug and state is WAITING_TO_ASK_PREDEFINED
                # and append its results (the first question message) to the display messages.
                pass
        else:
            summary_text = "No questions were configured for this session."
            summary_msg_data = SessionManager.add_message_to_display_chat(session, "assistant", summary_text)
            # components.append(UIComponents.chat_message(summary_msg_data)) # This would be OOB
            session['bot_state'] = "DONE"
            print("INIT: No questions. Bot state: DONE")
    return components


@rt("/")
async def get_chat_ui(session: dict):
    """Serves the main chat page, loading history from session."""
    SessionManager.initialize_session(session) # Initializes or re-initializes with defaults
    
    # After initialize_session, bot_state is INIT. Call _trigger_initial_bot_action to set up for first question.
    # _trigger_initial_bot_action will set state to WAITING_TO_ASK_PREDEFINED if questions exist.
    # It returns OOB components, which are not directly usable in a full page render.
    # However, the session state is now correctly set.
    await _trigger_initial_bot_action(session) 

    # If not in debug mode, and bot is WAITING_TO_ASK_PREDEFINED, ask the first question immediately.
    # This makes the first question appear on initial page load without user interaction.
    if not session.get('debug_mode_enabled') and session.get('bot_state') == "WAITING_TO_ASK_PREDEFINED":
        # Call handle_bot_turn to generate the first question message and add it to session['chat_messages']
        # This mutates session['chat_messages'] directly.
        # The components returned are for HTMX swaps, not needed for initial full page render here.
        await handle_bot_turn(session, user_message_content=None)


    return UIComponents.chat_interface( # Render the full interface
        SessionManager.get_display_messages(session), 
        llm_service.get_model_name(),
        session.get('debug_mode_enabled', False),
        session.get('bot_state', "INIT")
    )


@rt("/toggle_debug")
async def toggle_debug_mode(session: dict):
    current_status = session.get('debug_mode_enabled', False)
    session['debug_mode_enabled'] = not current_status
    print(f"Debug mode toggled to: {session['debug_mode_enabled']}")
    
    updated_toggle_button = UIComponents.debug_status_indicator_and_toggle_button(session['debug_mode_enabled'])
    components_to_return = [updated_toggle_button]

    bot_state = session.get('bot_state')
    if not session['debug_mode_enabled']: # Debug turned OFF
        components_to_return.append(UIComponents.clear_debug_action_area_component())
        # If debug was turned off and bot was waiting, try to proceed automatically
        if bot_state == "WAITING_TO_ASK_PREDEFINED" or \
           bot_state == "EVALUATING_ANSWER" or \
           bot_state == "GENERATING_SUMMARY":
            print(f"Debug off, bot was in {bot_state}. Attempting to auto-proceed.")
            auto_proceed_components = await handle_bot_turn(session, user_message_content=None)
            components_to_return.extend(auto_proceed_components)
            
    elif bot_state not in ["DONE", "INIT"] : # Debug turned ON and bot is in an active state
         components_to_return.append(
            Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true")
        )
        
    return tuple(components_to_return)


async def handle_bot_turn(session: dict, user_message_content: str = None):
    """
    Core logic for handling a bot turn.
    This function MUTATES the session object (bot_state, current_question_id, etc.)
    and appends messages to session['chat_messages'] via SessionManager.add_message_to_display_chat.
    It returns a list of HTMX components for OOB swaps or direct appending to chat-box.
    """
    components = []
    bot_state = session.get('bot_state', "INIT")
    current_q_id = session.get('current_question_id')
    debug_mode = session.get('debug_mode_enabled', False)

    print(f"Handling bot turn. Current State: {bot_state}, Current Q_ID: {current_q_id}, User Msg: '{user_message_content}'")

    if bot_state == "INIT": 
        first_q_id = question_service.get_first_question_id()
        if first_q_id:
            session['current_question_id'] = first_q_id
            session['current_question_text'] = question_service.get_question_text_by_id(first_q_id)
            session['bot_state'] = "WAITING_TO_ASK_PREDEFINED"
            bot_state = "WAITING_TO_ASK_PREDEFINED" 
            print(f"INIT in handle_bot_turn: Set to ask first question '{first_q_id}'. New state: {session['bot_state']}")
            # If not in debug, immediately transition to ask it
            if not debug_mode:
                return await handle_bot_turn(session, user_message_content=None)
            else: # In debug, show continue button
                components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
                return components
        else:
            summary_text = "No questions are configured. End of session."
            msg_data = SessionManager.add_message_to_display_chat(session, "assistant", summary_text)
            components.append(UIComponents.chat_message(msg_data))
            session['bot_state'] = "DONE"
            print("INIT: No questions. Bot state: DONE")
            return components


    if bot_state == "WAITING_TO_ASK_PREDEFINED":
        question_to_ask_id = session.get('current_question_id')
        question_to_ask_text = session.get('current_question_text')

        if not question_to_ask_id or not question_to_ask_text:
            print(f"Error: WAITING_TO_ASK_PREDEFINED but current_question_id ('{question_to_ask_id}') or text is invalid.")
            session['bot_state'] = "DONE" 
            err_msg_data = SessionManager.add_message_to_display_chat(session, "assistant", "I've encountered an issue and cannot proceed with questions.")
            components.append(UIComponents.chat_message(err_msg_data))
            if debug_mode: components.append(UIComponents.clear_debug_action_area_component())
            return components

        # Phase 1: Bot asks predefined question directly
        actual_question_asked_by_bot = question_to_ask_text
        
        msg_data = SessionManager.add_message_to_display_chat(session, "assistant", actual_question_asked_by_bot)
        components.append(UIComponents.chat_message(msg_data))
        
        session['bot_state'] = "EXPECTING_USER_ANSWER"
        session['current_question_follow_up_count'] = 0
        print(f"Bot asked Q_ID: '{question_to_ask_id}'. New state: {session['bot_state']}")
        if debug_mode: 
            components.append(UIComponents.clear_debug_action_area_component())


    elif bot_state == "EXPECTING_USER_ANSWER":
        if user_message_content is None:
            print("EXPECTING_USER_ANSWER but no user_message_content. This happens if /continue_debug is hit before user answers.")
            # Bot remains in this state, waiting for user. Debug button should still be active if debug_mode is on.
            if debug_mode:
                 components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
            return components 

        # User has provided an answer. Add it to display chat and collected answers.
        # This message is added to display chat by the /chat route *before* calling handle_bot_turn.
        # So, we only need to add to collected_answers here.
        SessionManager.add_exchange_to_collected_answers(session, current_q_id, "user", user_message_content)
        
        session['bot_state'] = "EVALUATING_ANSWER"
        print(f"User answer for Q_ID '{current_q_id}' stored: '{user_message_content}'. New state: {session['bot_state']}")

        if debug_mode:
            components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
        else:
            return await handle_bot_turn(session) # Auto-proceed to evaluate


    elif bot_state == "EVALUATING_ANSWER":
        # Phase 1: Simplified logic - Assume answer is sufficient, move to next.
        acknowledgement = f"Okay, thank you." # Generic acknowledgement
        ack_msg_data = SessionManager.add_message_to_display_chat(session, "assistant", acknowledgement)
        components.append(UIComponents.chat_message(ack_msg_data))

        session['current_question_follow_up_count'] = 0 
        
        next_q_id = question_service.get_next_question_id(current_q_id)
        if next_q_id:
            session['current_question_id'] = next_q_id
            session['current_question_text'] = question_service.get_question_text_by_id(next_q_id)
            session['bot_state'] = "WAITING_TO_ASK_PREDEFINED"
            print(f"Q_ID '{current_q_id}' deemed sufficient (Phase 1). Next Q_ID: '{next_q_id}'. New state: {session['bot_state']}")
            if debug_mode:
                components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
            else: 
                return await handle_bot_turn(session) # Auto-proceed to ask next question
        else:
            session['bot_state'] = "GENERATING_SUMMARY"
            print(f"All questions answered for Q_ID '{current_q_id}'. New state: {session['bot_state']}")
            if debug_mode:
                components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
            else: 
                return await handle_bot_turn(session) # Auto-proceed to summarize
                
    elif bot_state == "GENERATING_SUMMARY":
        summary_parts = ["Summary of your answers:"]
        collected_data = session.get('collected_answers', {})
        if not collected_data:
            summary_parts.append("No answers were collected.")
        else:
            for q_id, exchanges in collected_data.items():
                q_text = question_service.get_question_text_by_id(q_id)
                summary_parts.append(f"\nFor \"{q_text}\":")
                user_answers_for_q = [ex['content'] for ex in exchanges if ex['role'] == 'user']
                if user_answers_for_q:
                    summary_parts.append(f"  You said: {' | '.join(user_answers_for_q)}")
                else:
                    summary_parts.append("  No answer recorded.")
        
        final_summary = "\n".join(summary_parts)
        summary_msg_data = SessionManager.add_message_to_display_chat(session, "assistant", final_summary)
        components.append(UIComponents.chat_message(summary_msg_data))
        
        thank_you_msg_data = SessionManager.add_message_to_display_chat(session, "assistant", "Thank you for providing your information. The consultation can now begin.")
        components.append(UIComponents.chat_message(thank_you_msg_data))

        session['bot_state'] = "DONE"
        print(f"Summary generated. New state: {session['bot_state']}")
        if debug_mode: 
            components.append(UIComponents.clear_debug_action_area_component())

    elif bot_state == "DONE":
        print("Bot state is DONE. No further actions.")
        if debug_mode: 
            components.append(UIComponents.clear_debug_action_area_component())

    return components


@rt("/chat")
async def post_chat_message(user_message: str, session: dict):
    """Handles incoming user messages, triggers bot logic, and updates chat via HTMX."""
    components = []
    bot_state = session.get('bot_state', "INIT")
    debug_mode = session.get('debug_mode_enabled', False)

    # Always clear the input field first as an OOB swap
    components.append(UIComponents.clear_input_component())

    if bot_state == "DONE":
        print(f"User message '{user_message}' received but bot is DONE. Ignoring.")
        # Optionally add a message like "Session has ended."
        ended_msg = SessionManager.add_message_to_display_chat(session, "assistant", "This session has ended. Please restart if you wish to begin again.")
        components.append(UIComponents.chat_message(ended_msg))
        return tuple(components)
    
    if bot_state == "GENERATING_SUMMARY" and not debug_mode: # Bot is auto-summarizing
        print(f"User message '{user_message}' received while bot is auto-summarizing. Ignoring.")
        return tuple(components)


    if not user_message or not user_message.strip():
        print("Empty user message received. No action.")
        # If in debug and waiting for user, keep debug button
        if debug_mode and session.get('bot_state') == "EXPECTING_USER_ANSWER":
            components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
        return tuple(components)
    
    # Display user's message first
    user_msg_data = SessionManager.add_message_to_display_chat(session, "user", user_message)
    components.append(UIComponents.chat_message(user_msg_data))

    # Now, let handle_bot_turn decide what to do with this user_message based on state
    if bot_state == "EXPECTING_USER_ANSWER":
        bot_turn_components = await handle_bot_turn(session, user_message_content=user_message)
        components.extend(bot_turn_components)
    elif bot_state == "WAITING_TO_ASK_PREDEFINED" and debug_mode:
        # User typed while bot was waiting for "Next Step" to ask a question.
        # Log this, but the "Next Step" will still ask the predefined question.
        # The user's message is displayed, but not processed as an answer to the *upcoming* question.
        print(f"User message '{user_message}' received while bot in WAITING_TO_ASK_PREDEFINED (debug). Message displayed, bot will ask its question on 'Next Step'.")
        # Ensure "Next Step" button remains if it was there
        components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
    else:
        # User message in other states (e.g. INIT, EVALUATING_ANSWER (if somehow user could submit))
        # This path should ideally not be hit if form is disabled correctly.
        # For now, just log and don't process further if state is not EXPECTING_USER_ANSWER.
        print(f"User message '{user_message}' received in unhandled bot state '{bot_state}'. Displayed but not processed further by bot logic here.")


    return tuple(components)

@rt("/continue_debug_or_next_step") 
async def continue_debug_or_next_step(session: dict):
    """
    Triggered by the 'Process AI Response / Next Step' button in debug mode.
    Advances the bot's state machine.
    """
    components = []
    print(f"'/continue_debug_or_next_step' called. Current bot state: {session.get('bot_state')}")

    # user_message_content is None because this is a button press.
    bot_turn_components = await handle_bot_turn(session, user_message_content=None)
    components.extend(bot_turn_components)
    
    return tuple(components)

@rt("/restart_chat")
async def restart_chat_session(session: dict):
    """Clears the session and tells HTMX to refresh the page."""
    print(f"Restarting chat. Clearing session ID: {session.get('session_id')}")
    session.clear() # Clears all data from the current session
    # Return a response that tells HTMX to refresh the page
    # Using HTMLResponse as it's readily available from fasthtml.common
    return HTMLResponse(content="", status_code=200, headers={"HX-Refresh": "true"})

# -----------------------------------------------------------------------------
# APPLICATION ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Starting QuestionnAIre Chatbot...")
    print(f"LLM Service: Using model '{llm_service.get_model_name()}' on host '{llm_service.host}'")
    print(f"Question Service: Loaded {len(question_service.get_all_question_ids())} questions from '{question_service.filepath}'")
    if not question_service.get_all_question_ids():
        print("Warning: No questions loaded. The chatbot might not function as expected.")
    else:
        print(f"First question ID: {question_service.get_first_question_id()}")

    SessionManager.cleanup() # Cleanup old .sessions files if they exist
    serve(port=5001)