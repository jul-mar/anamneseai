# chat.py
from fasthtml.common import *
import ollama  # ollama python client
import uuid  # For unique IDs for messages
import datetime  # Not strictly needed for logic, but good to keep if it was used elsewhere
import os  # For creating session directory
import shutil  # For removing session directory
import json # For loading questions from JSON file
from starlette.responses import RedirectResponse, Response # Ensure Response is imported
from huggingface_hub import InferenceClient
from abc import ABC, abstractmethod
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
            base_dir = os.path.dirname(os.path.abspath(__file__))
            absolute_filepath = os.path.join(base_dir, self.filepath)

            if not os.path.exists(absolute_filepath):
                print(f"Error: Questions file not found at {absolute_filepath}")
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
            
            self._questions_by_id = {} 
            self._ordered_ids = []     
            for index, question_data in enumerate(self._questions_list):
                if "id" not in question_data or "text" not in question_data:
                    print(f"Warning: Question at index {index} in '{self.filepath}' is missing 'id' or 'text'. Skipping.")
                    continue
                q_id = question_data["id"]
                # Ensure criteria is always a list, even if missing or null in JSON
                criteria = question_data.get("criteria", [])
                if not isinstance(criteria, list):
                    criteria = []
                question_data["criteria"] = criteria
                self._questions_by_id[q_id] = question_data
                self._ordered_ids.append(q_id)
            
            if not self._ordered_ids: 
                 print(f"Warning: No valid questions loaded from {self.filepath}. The question list is empty.")
        except FileNotFoundError:
            print(f"Error: Questions file not found at {absolute_filepath}. Please create it.")
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
        return self._questions_by_id.get(question_id)

    def get_first_question_id(self):
        return self._ordered_ids[0] if self._ordered_ids else None

    def get_next_question_id(self, current_question_id):
        try:
            current_index = self._ordered_ids.index(current_question_id)
            if current_index < len(self._ordered_ids) - 1:
                return self._ordered_ids[current_index + 1]
            else:
                return None 
        except ValueError:
            return None 

    def get_all_question_ids(self):
        return list(self._ordered_ids)

    def get_question_text_by_id(self, question_id):
        question = self.get_question_by_id(question_id)
        return question.get("text") if question else None
    
    def get_question_criteria_by_id(self, question_id):
        question = self.get_question_by_id(question_id)
        return question.get("criteria", []) if question else []

# -----------------------------------------------------------------------------
# LLM PROVIDERS
# -----------------------------------------------------------------------------
class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def chat(self, messages: list, **kwargs) -> str:
        """Send messages to the LLM and return the response."""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name being used."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available."""
        pass

class HuggingFaceProvider(LLMProvider):
    """Provider for Hugging Face Inference API."""
    
    def __init__(self, model_name: str, config: dict):
        self.model_name = model_name
        self.config = config
        self.client = None
        self.hf_token = os.getenv("HF_TOKEN")
        self.initialize_client()
    
    def initialize_client(self):
        try:
            if not self.hf_token:
                print("Warning: HF_TOKEN environment variable not set. Using mock client.")
                self.client = self._create_mock_client()
                return
                
            self.client = InferenceClient(
                model=self.model_name,
                token=self.hf_token
            )
            print(f"Successfully initialized Hugging Face client with model: {self.model_name}")
        except Exception as e:
            print(f"Error initializing Hugging Face client: {e}. Using mock client.")
            self.client = self._create_mock_client()
    
    def _create_mock_client(self):
        class MockHFClient:
            def chat_completion(self, messages, max_tokens=None, temperature=None):
                print("--- Using Mock Hugging Face Client ---")
                return type('obj', (object,), {
                    'choices': [type('obj', (object,), {
                        'message': type('obj', (object,), {
                            'content': 'Mock response from Hugging Face. Please set HF_TOKEN environment variable.'
                        })()
                    })()]
                })()
        return MockHFClient()
    
    def chat(self, messages: list, **kwargs) -> str:
        try:
            if self.client is None:
                return "Error: Hugging Face client not initialized."
            
            # Convert messages to HuggingFace format
            hf_messages = []
            for msg in messages:
                hf_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            response = self.client.chat_completion(
                messages=hf_messages,
                max_tokens=self.config.get("max_tokens", 1000),
                temperature=self.config.get("temperature", 0.7)
            )
            
            if hasattr(response, 'choices') and response.choices and hasattr(response.choices[0], 'message'):
                content = response.choices[0].message.content
                return content if content is not None else "Empty response from Hugging Face API."
            else:
                return "Invalid response format from Hugging Face API."
        except Exception as e:
            print(f"Error in Hugging Face chat: {e}")
            return "Sorry, there was an error communicating with the Hugging Face API."
    
    def get_model_name(self) -> str:
        return self.model_name
    
    def is_available(self) -> bool:
        return self.hf_token is not None

class OllamaProvider(LLMProvider):
    """Provider for Ollama API."""
    
    def __init__(self, model_name: str, config: dict):
        self.model_name = model_name
        self.config = config
        self.host = config.get("host", "http://localhost:11434")
        self.client = None
        self.initialize_client()
    
    def initialize_client(self):
        try:
            print(f"Attempting to connect to Ollama at {self.host}")
            self.client = ollama.Client(host=self.host)
            models_response = self.client.list() 
            models = models_response.get('models', []) if isinstance(models_response, dict) else []
            available_models = [m.get('name', '') for m in models if isinstance(m, dict) and 'name' in m]
            if self.model_name in available_models:
                print(f"Successfully connected to Ollama. Using model: {self.model_name}")
            else:
                print(f"[ERROR] Model '{self.model_name}' not found in available models: {available_models}")
        except Exception as e:
            print(f"Error connecting to Ollama: {e}. Starting with mock client.")
            self.client = self._create_mock_client()
    
    def _create_mock_client(self):
        class MockOllamaClient:
            _call_count = 0
            
            def list(self): return {'models': []}
            
            def chat(self, model, messages, format=None, options=None):
                MockOllamaClient._call_count += 1
                print("--- Using Mock Ollama Client ---")
                
                last_user_message_content = ""
                if messages and messages[-1]['role'] == 'user':
                    content = messages[-1]['content']
                    if "The patient's latest answer to this question (or my follow-up) is: \"" in content:
                        answer_part = content.split("The patient's latest answer to this question (or my follow-up) is: \"")[-1]
                        if answer_part:
                            last_user_message_content = answer_part.split("\"")[0]
                
                print(f"Mock client processing based on (extracted) user answer: '{last_user_message_content}' and call count {MockOllamaClient._call_count}")

                if "The current predefined question is:" in messages[-1]['content']:
                    if "sufficient" in last_user_message_content.lower() or \
                       "yes" in last_user_message_content.lower() or \
                       MockOllamaClient._call_count % 3 == 0 :
                         print("Mock client: Simulating 'question_sufficiently_answered'")
                         return {'message': {'content': '{ "action": "question_sufficiently_answered" }'}}
                    else:
                        print("Mock client: Simulating a follow-up question.")
                        return {'message': {'content': f'Mocked follow-up based on "{last_user_message_content[:20]}...": Could you please clarify that a bit more for me?'}}
                
                if "Please provide a concise summary" in messages[-1]['content']:
                    print("Mock client: Simulating summary generation.")
                    return {'message': {'content': 'This is a mocked summary of the patient\'s answers, focusing on key details provided. (Mocked by LLMService)'}}

                print("Mock client: Simulating a generic response or initial question asking.")
                return {'message': {'content': 'What would you like to discuss next? (Mocked generic from LLMService)'}}
        return MockOllamaClient()
    
    def chat(self, messages: list, **kwargs) -> str:
        try:
            if self.client is None:
                return "Error: Ollama client not initialized."
            
            print("\n----- SENDING PROMPT TO LLM -----")
            print(f"Model: {self.model_name}")
            for i, msg in enumerate(messages):
                print(f"\n[Message {i}] Role: {msg['role']}")
                content_to_log = msg['content']
                print(f"Content: {content_to_log[:400]}..." if len(content_to_log) > 400 else f"Content: {content_to_log}")
            print("----- END OF PROMPT -----\n")
            
            request_params = { "model": self.model_name, "messages": messages }
            response = self.client.chat(**request_params)
            response_content = response.get('message', {}).get('content', 'No response from AI')
            
            print(f"\n----- RECEIVED RESPONSE FROM LLM -----\nRaw Content: {response_content}\n-----------------------------------\n")
            return response_content
        except Exception as e:
            print(f"Error in Ollama chat call: {e}")
            return "Sorry, there was an error communicating with the AI."
    
    def get_model_name(self) -> str:
        return self.model_name
    
    def is_available(self) -> bool:
        return self.client is not None

# -----------------------------------------------------------------------------
# LLM SERVICE LAYER
# -----------------------------------------------------------------------------
class LLMService:
    """
    Service for interacting with LLMs through different providers.
    
    Args:
        provider (str, optional): The LLM provider to use ("huggingface" or "ollama").
        model_name (str, optional): The name of the model to use.
        config (dict, optional): Provider-specific configuration.
    """
    DEFAULT_PROVIDER = "ollama"
    DEFAULT_MODEL = "gemma3:4b-it-qat"
    
    SYSTEM_PROMPT = """You are QuestionnAIre, a highly capable and empathetic AI medical assistant. Your primary role is to meticulously gather patient information by asking a series of predefined questions. You will be provided with one predefined question at a time, potentially with some criteria or examples for a good answer, and the patient's response to it.

Your core responsibilities are:

1.  **Evaluate Patient Answers:**
    * Carefully assess the patient's answer specifically in relation to the predefined question that was just asked and any provided criteria.
    * Determine if the answer is complete and sufficient to understand the patient's situation concerning THAT specific predefined question.

2.  **Ask Clarifying Follow-up Questions (If Necessary):**
    * If the patient's answer to the current predefined question is vague, incomplete, or doesn't fully address the question or its criteria, you MUST ask a polite and targeted follow-up question.
    * This follow-up question should be designed to elicit the missing information FOR THE CURRENT PREDEFINED QUESTION ONLY. Do not move on to a new topic or a new predefined question.
    * Your follow-up questions should be in plain text. For example: "Could you tell me a bit more about when that started?" or "You mentioned it's frequent, could you describe what 'frequent' means for you in terms of how many times a day?"
    * Ask only ONE follow-up question at a time and wait for the response.

3.  **Signal Sufficiency (When a Predefined Question is Fully Answered):**
    * ONLY when you are confident that you have gathered sufficient and clear information for the CURRENT PREDEFINED QUESTION (this might be after the initial answer, or after one or more of your follow-up questions for it), you MUST signal this to the application.
    * To do this, your ENTIRE response MUST be a single JSON object in the following EXACT format:
        ```json
        { "action": "question_sufficiently_answered" }
        ```
    * IMPORTANT: Do NOT output any other text or explanation before or after this JSON object when you are signaling sufficiency. Your entire response must be this JSON object. The application will then handle acknowledging the patient and moving to the next step.

4.  **General Conduct:**
    * Maintain a professional, empathetic, and respectful tone at all times.
    * Do NOT use Markdown in any of your responses.
    * Do NOT provide medical diagnoses, advice, or treatment recommendations. Your role is information gathering.
    * Be clear and precise in your questions.
    * Respect patient privacy and be sensitive to personal health issues.

**Summary of Output Types:**
* If asking a follow-up question for the current predefined question: Output plain text.
* If the current predefined question is fully answered: Output the specific JSON object: `{ "action": "question_sufficiently_answered" }`.

You will be guided by the application on when to ask the *next* predefined question from the list. Your focus is on thoroughly completing the *current* one.
"""

    def __init__(self, provider=None, model_name=None, config=None):
        self.provider_name = provider or self.DEFAULT_PROVIDER
        self.model_name = model_name or self.DEFAULT_MODEL
        self.config = config or {}
        self.provider = None
        self.initialize_provider()
    
    def initialize_provider(self):
        """Initialize the appropriate LLM provider based on configuration."""
        try:
            if self.provider_name == "huggingface":
                hf_config = self.config.get("huggingface", {})
                self.provider = HuggingFaceProvider(self.model_name, hf_config)
            elif self.provider_name == "ollama":
                ollama_config = self.config.get("ollama", {"host": "http://localhost:11434"})
                self.provider = OllamaProvider(self.model_name, ollama_config)
            else:
                print(f"Unknown provider: {self.provider_name}. Falling back to Ollama.")
                ollama_config = self.config.get("ollama", {"host": "http://localhost:11434"})
                self.provider = OllamaProvider(self.model_name, ollama_config)
            
            print(f"[Startup] LLMService initialized with provider: {self.provider_name}, model: {self.model_name}")
        except Exception as e:
            print(f"Error initializing provider: {e}. Using Ollama fallback.")
            ollama_config = {"host": "http://localhost:11434"}
            self.provider = OllamaProvider(self.DEFAULT_MODEL, ollama_config)
    
    def get_model_name(self) -> str:
        """Get the current model name."""
        return self.provider.get_model_name() if self.provider else self.model_name
    
    def get_system_prompt(self) -> str:
        """Get the system prompt."""
        return self.SYSTEM_PROMPT
    
    def chat(self, messages_for_llm: list) -> str:
        """Send messages to the LLM and return the response."""
        if not self.provider:
            return "Error: No LLM provider available."
        
        return self.provider.chat(messages_for_llm)

# -----------------------------------------------------------------------------
# SESSION MANAGEMENT
# -----------------------------------------------------------------------------
class SessionManager:
    @staticmethod
    def initialize_session(session, first_question_id=None, first_question_text=None):
        existing_session_id = session.get('session_id')
        existing_debug_mode = session.get('debug_mode_enabled', False) 
        session.clear() 
        if existing_session_id: session['session_id'] = existing_session_id
        else: session['session_id'] = str(uuid.uuid4())
        session['debug_mode_enabled'] = existing_debug_mode 
        welcome_msg = {"id": "welcome-msg", "role": "assistant", "content": "Welcome to QuestionnAIre. I'm here to ask a few questions about your health before your appointment. Let's start."}
        session['chat_messages'] = [welcome_msg] 
        session['current_question_id'] = None 
        session['current_question_text'] = "" 
        session['current_question_criteria'] = [] 
        session['collected_answers'] = {} 
        session['current_question_follow_up_count'] = 0
        session['bot_state'] = "INIT" 
        print(f"Session initialized/re-initialized. ID: {session['session_id']}, Debug: {session['debug_mode_enabled']}")

    @staticmethod
    def add_message_to_display_chat(session, role, content, msg_id=None):
        if not msg_id: msg_id = str(uuid.uuid4())
        message = {"id": msg_id, "role": role, "content": content}
        if 'chat_messages' not in session: session['chat_messages'] = []
        session['chat_messages'].append(message)
        return message 
    
    @staticmethod
    def add_exchange_to_collected_answers(session, question_id, role, content):
        if question_id not in session['collected_answers']: session['collected_answers'][question_id] = []
        session['collected_answers'][question_id].append({"role": role, "content": content})

    @staticmethod
    def get_display_messages(session): return session.get('chat_messages', [])
    
    @staticmethod
    def cleanup():
        try:
            session_dir = ".sessions"
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                print(f"Removed session data directory: {session_dir}")
        except Exception as e: print(f"Error cleaning session data: {e}")

# -----------------------------------------------------------------------------
# UI COMPONENTS
# -----------------------------------------------------------------------------
class UIComponents:
    @staticmethod
    def get_headers():
        return (
            Script(src="https://cdn.tailwindcss.com"),
            Script(src="https://unpkg.com/htmx.org@1.9.10"),
            Script(src="https://unpkg.com/htmx.org@1.9.10/dist/ext/loading-states.js"),
            Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.10.1/dist/full.min.css"),
            Script("""
            tailwind.config = {
              theme: { extend: { colors: { 'medical-blue': '#0077b6', 'medical-blue-light': '#90e0ef', 'medical-blue-dark': '#03045e' } } }
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
        return (
            Title("QuestionnAIre - Professional Medical Assistant"),
            Link(rel="icon", href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚕️</text></svg>"),
            Meta(name="description", content="Professional AI assistant for taking a patients history"),
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            Style("""
                body { background-color: #f8fafc; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
                ::-webkit-scrollbar { width: 8px; height: 8px; } ::-webkit-scrollbar-track { background: #f1f5f9; }
                ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; } ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
                #loading-indicator { opacity: 0; transition: opacity 200ms ease-in; }
                #loading-indicator.processing { opacity: 1 !important; } .htmx-request .htmx-indicator { opacity: 1 !important; }
            """),
        )
    
    @staticmethod
    def chat_message(message):
        is_user = message.get("role") == "user"
        chat_alignment = "chat-end" if is_user else "chat-start"
        if message.get("role") == "error": bubble_color, border_style = "bg-red-100 text-red-800", "border-l-4 border-red-500"
        elif is_user: bubble_color, border_style = "bg-white text-gray-800", "border-l-4 border-medical-blue"
        else: bubble_color, border_style = "bg-medical-blue text-white", ""
        message_content = message.get("content", "")
        avatar_initial = "P" if is_user else "A" 
        avatar_bg = "bg-medical-blue-dark text-white" if is_user else "bg-white text-medical-blue-dark border border-medical-blue"
        avatar = Div(Div(Span(avatar_initial, cls="inline-flex items-center justify-center w-full h-full"), cls=f"w-8 h-8 rounded-full {avatar_bg} flex items-center justify-center text-sm font-semibold shadow-sm"), cls="chat-image avatar")
        role_label = "Patient" if is_user else "Assistant"
        return Div(avatar, Div(role_label, cls="chat-header text-xs font-medium mb-1 text-gray-600"), Div(P(message_content, cls="whitespace-pre-wrap"), cls=f"chat-bubble shadow-sm {bubble_color} {border_style} break-words prose prose-sm sm:prose-base rounded-lg px-4 py-3"), cls=f"chat {chat_alignment}", id=f"message-{message.get('id', uuid.uuid4())}")

    @staticmethod
    def input_field(disabled=False): 
        attrs = {"id": "user-message-input", "type": "text", "name": "user_message", "placeholder": "Type your medical query...", "cls": "input bg-white border border-gray-300 focus:border-medical-blue focus:ring-2 focus:ring-medical-blue-light w-full flex-grow mr-2 rounded-lg", "autofocus": True}
        if disabled: attrs["disabled"], attrs["placeholder"] = True, "Conversation ended or bot is processing..."
        return Input(**attrs)
    
    @staticmethod
    def loading_indicator():
        # The indicator must be a direct child of the form and have the htmx-indicator class
        return Div(
            Div(_innerHTML="""<svg class=\"animate-spin h-5 w-5 mr-2\" xmlns=\"http://www.w3.org/2000/svg\" fill=\"none\" viewBox=\"0 0 24 24\"><circle class=\"opacity-25\" cx=\"12\" cy=\"12\" r=\"10\" stroke=\"currentColor\" stroke-width=\"4\"></circle><path class=\"opacity-75\" fill=\"currentColor\" d=\"M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z\"></path></svg>""", cls="inline-block"),
            Span("Processing...", cls="text-sm font-medium"),
            id="loading-indicator",
            cls="htmx-indicator flex items-center text-medical-blue ml-2",
            style="opacity: 0; transition: opacity 200ms ease-in;"
        )
    
    @staticmethod
    def submit_button(disabled=False): 
        attrs = {"type": "submit", "cls": "bg-medical-blue hover:bg-medical-blue-dark text-white font-medium py-2 px-6 rounded-lg transition-colors duration-200", "data_loading_disable": True }
        if disabled: attrs["disabled"] = True
        return Button("Send", **attrs)
    
    @staticmethod
    def header(model_name):
        return Div(Div(Div(_innerHTML="""<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-medical-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>""", cls="mr-3"), Div(H1("QuestionnAIre", cls="text-2xl font-bold text-medical-blue-dark"), P("Patient history Chatbot", cls="text-sm text-gray-600"), cls="flex flex-col"), cls="flex items-center mb-2"), Div(cls="w-full h-px bg-gray-200 mb-4"), Div(Div(_innerHTML="""<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>""", cls="text-medical-blue"), Span(f"Powered by: {model_name}", cls="text-xs text-gray-600"), cls="flex items-center justify-end mb-4"), cls="bg-white rounded-lg shadow-sm p-4 mb-4 border border-gray-200")

    @staticmethod
    def debug_status_indicator_and_toggle_button(is_enabled: bool):
        status_text, button_text, button_cls = ("ON", "Disable Debug Mode", "btn-warning") if is_enabled else ("OFF", "Enable Debug Mode", "btn-outline btn-info")
        return Div(Span(f"Debug Mode: {status_text}", cls="mr-2 text-sm font-medium align-middle"), Button(button_text, hx_post="/toggle_debug", hx_target="#debug-status-container", hx_swap="outerHTML", cls=f"btn btn-xs {button_cls} align-middle"), id="debug-status-container", cls="py-1 text-center")

    @staticmethod
    def continue_debug_button(): return Button("Process AI Response / Next Step", hx_post="/continue_debug_or_next_step", hx_target="#chat-box", hx_swap="beforeend", cls="btn btn-sm btn-accent mt-1")
    @staticmethod
    def clear_debug_action_area_component(): return Div(id="debug-action-area", hx_swap_oob="true")
    @staticmethod
    def restart_button(): return Button("Restart Chat", hx_post="/restart_chat", cls="btn btn-sm btn-error btn-outline mt-1")

    @staticmethod
    def chat_interface(messages, model_name, debug_mode_enabled: bool, bot_state: str):
        if messages is None: messages = []
        chat_box_height = "h-[calc(100vh-320px)]" 
        chat_box = Div(*[UIComponents.chat_message(msg) for msg in messages], id="chat-box", cls=f"p-4 space-y-6 overflow-y-auto {chat_box_height} bg-white rounded-lg shadow-md border border-gray-200")
        form_is_disabled = bot_state in ["GENERATING_SUMMARY", "DONE", "WAITING_TO_ASK_PREDEFINED"] and not (debug_mode_enabled and bot_state == "WAITING_TO_ASK_PREDEFINED")
        chat_form_classes = "p-4 flex items-center bg-gray-50 rounded-lg shadow-sm mt-4 sticky bottom-0 border border-gray-200" + (" opacity-50" if form_is_disabled else "")
        # Ensure the loading indicator is a direct child of the form and only use hx_indicator for reliable spinner
        chat_form = Form(
            UIComponents.input_field(disabled=form_is_disabled),
            UIComponents.submit_button(disabled=form_is_disabled),
            UIComponents.loading_indicator(),
            hx_post="/chat", hx_target="#chat-box", hx_swap="beforeend", hx_indicator="#loading-indicator",
            # Remove hx_ext, data_loading_delay, data_loading_class, data_loading_target, data_loading_class_remove for reliability
            hx_on_htmx_after_on_load="this.closest('.container').querySelector('#chat-box').scrollTop = this.closest('.container').querySelector('#chat-box').scrollHeight; if(document.activeElement.tagName === 'BUTTON' && !document.getElementById('user-message-input').disabled) { document.getElementById('user-message-input').focus(); }",
            cls=chat_form_classes
        )
        controls_container = Div(Div(id="debug-action-area", cls="text-center mt-1 mb-1"), UIComponents.debug_status_indicator_and_toggle_button(debug_mode_enabled), UIComponents.restart_button(), cls="mt-1 space-y-2")
        return Div(UIComponents.header(model_name), chat_box, chat_form, controls_container, cls="container mx-auto max-w-3xl p-4 flex flex-col h-screen font-sans bg-gray-50")
    
    @staticmethod
    def clear_input_component(): return Input(id="user-message-input", name="user_message", placeholder="Type your medical query...", cls="input bg-white border border-gray-300 focus:border-medical-blue focus:ring-2 focus:ring-medical-blue-light w-full flex-grow mr-2 rounded-lg", hx_swap_oob="true", value="", autofocus=True)

# -----------------------------------------------------------------------------
# MAIN APPLICATION
# -----------------------------------------------------------------------------
question_service = QuestionService() 

# --- Load configuration from config.json ---
def load_config():
    """Load the complete configuration from config.json."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "config.json")
        with open(config_path, "r") as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"Error loading config.json: {e}. Using defaults.")
        return {}

def create_llm_service_from_config():
    """Create LLMService instance from configuration."""
    config = load_config()
    
    provider = config.get("provider", LLMService.DEFAULT_PROVIDER)
    model_name = config.get("model_name", LLMService.DEFAULT_MODEL)
    
    # Extract provider-specific configs
    provider_configs = {}
    if "huggingface" in config:
        provider_configs["huggingface"] = config["huggingface"]
    if "ollama" in config:
        provider_configs["ollama"] = config["ollama"]
    
    return LLMService(provider=provider, model_name=model_name, config=provider_configs)

llm_service = create_llm_service_from_config()
app = FastHTML(hdrs=UIComponents.get_headers())
rt = app.route

async def _trigger_initial_bot_action(session: dict):
    components = []
    if session.get('bot_state') == "INIT":
        first_q_id = question_service.get_first_question_id()
        if first_q_id:
            session['current_question_id'] = first_q_id
            session['current_question_text'] = question_service.get_question_text_by_id(first_q_id)
            session['current_question_criteria'] = question_service.get_question_criteria_by_id(first_q_id)
            session['bot_state'] = "WAITING_TO_ASK_PREDEFINED" 
            print(f"INIT: Set to ask first question: {first_q_id}. Bot state: {session['bot_state']}")
            if session.get('debug_mode_enabled', False): 
                components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
        else:
            SessionManager.add_message_to_display_chat(session, "assistant", "No questions were configured for this session.")
            session['bot_state'] = "DONE"
            print("INIT: No questions. Bot state: DONE")
    return components

@rt("/")
async def get_chat_ui(session: dict):
    SessionManager.initialize_session(session) 
    await _trigger_initial_bot_action(session) 
    if not session.get('debug_mode_enabled') and session.get('bot_state') == "WAITING_TO_ASK_PREDEFINED":
        await handle_bot_turn(session, user_message_content=None)
    return UIComponents.chat_interface(SessionManager.get_display_messages(session), llm_service.get_model_name(), session.get('debug_mode_enabled', False), session.get('bot_state', "INIT"))

@rt("/toggle_debug")
async def toggle_debug_mode(session: dict):
    session['debug_mode_enabled'] = not session.get('debug_mode_enabled', False)
    print(f"Debug mode toggled to: {session['debug_mode_enabled']}")
    components = [UIComponents.debug_status_indicator_and_toggle_button(session['debug_mode_enabled'])]
    bot_state = session.get('bot_state')
    if not session['debug_mode_enabled']: 
        components.append(UIComponents.clear_debug_action_area_component())
        if bot_state in ["WAITING_TO_ASK_PREDEFINED", "EVALUATING_ANSWER", "GENERATING_SUMMARY"]:
            print(f"Debug off, bot was in {bot_state}. Attempting to auto-proceed.")
            components.extend(await handle_bot_turn(session, user_message_content=None))
    elif bot_state not in ["DONE", "INIT", "EXPECTING_USER_ANSWER"] : 
         components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
    elif bot_state == "EXPECTING_USER_ANSWER" and session.get('debug_mode_enabled', False):
        # If user has answered and debug is on, the continue button should already be there or re-added if toggling.
        pass 
    return tuple(components)

async def handle_bot_turn(session: dict, user_message_content: str | None = None):
    MAX_FOLLOW_UPS = 3 # Define max follow-ups for a single predefined question
    components = []
    bot_state = session.get('bot_state', "INIT")
    current_q_id = session.get('current_question_id')
    debug_mode = session.get('debug_mode_enabled', False)
    print(f"Handling bot turn. State: {bot_state}, Q_ID: {current_q_id}, User Msg: '{user_message_content}'")

    if bot_state == "INIT": 
        first_q_id = question_service.get_first_question_id()
        if first_q_id:
            session['current_question_id'] = first_q_id
            session['current_question_text'] = question_service.get_question_text_by_id(first_q_id)
            session['current_question_criteria'] = question_service.get_question_criteria_by_id(first_q_id)
            session['bot_state'] = "WAITING_TO_ASK_PREDEFINED"
            print(f"INIT -> WAITING_TO_ASK_PREDEFINED for Q_ID: '{first_q_id}'")
            if not debug_mode: return await handle_bot_turn(session) # Auto-proceed
            else: components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
        else: 
            msg_data = SessionManager.add_message_to_display_chat(session, "assistant", "No questions are configured. End of session.")
            components.append(UIComponents.chat_message(msg_data))
            session['bot_state'] = "DONE"
            print("INIT -> DONE (no questions)")
        return components

    if bot_state == "WAITING_TO_ASK_PREDEFINED":
        q_id_to_ask = session.get('current_question_id')
        q_text_to_ask = session.get('current_question_text')
        if not q_id_to_ask or not q_text_to_ask:
            print(f"Error: WAITING_TO_ASK_PREDEFINED but Q_ID ('{q_id_to_ask}') or text is invalid.")
            session['bot_state'] = "DONE" 
            err_msg = SessionManager.add_message_to_display_chat(session, "assistant", "System error: Cannot find the next question.")
            components.append(UIComponents.chat_message(err_msg))
            if debug_mode: components.append(UIComponents.clear_debug_action_area_component())
            return components
        
        # For Phase 2, we could have LLM rephrase. For now, direct ask.
        actual_question_text_from_llm = q_text_to_ask
        # Optional: Add criteria to the displayed question for user context
        # q_criteria_for_display = session.get('current_question_criteria', [])
        # if q_criteria_for_display:
        #    actual_question_text_from_llm += "\n(Consider: " + "; ".join(q_criteria_for_display) + ")"


        msg_data = SessionManager.add_message_to_display_chat(session, "assistant", actual_question_text_from_llm)
        components.append(UIComponents.chat_message(msg_data))
        session['bot_state'] = "EXPECTING_USER_ANSWER"
        session['current_question_follow_up_count'] = 0 # Reset for new question
        print(f"WAITING_TO_ASK_PREDEFINED -> EXPECTING_USER_ANSWER for Q_ID: '{q_id_to_ask}'")
        if debug_mode: components.append(UIComponents.clear_debug_action_area_component())

    elif bot_state == "EXPECTING_USER_ANSWER":
        if user_message_content is None: 
            print("EXPECTING_USER_ANSWER but no user_message_content (likely from 'continue debug' too early). Waiting.")
            if debug_mode: components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
            return components 
        
        SessionManager.add_exchange_to_collected_answers(session, current_q_id, "user", user_message_content)
        session['bot_state'] = "EVALUATING_ANSWER"
        print(f"EXPECTING_USER_ANSWER -> EVALUATING_ANSWER for Q_ID '{current_q_id}'. User answer: '{user_message_content}'")
        if debug_mode: components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
        else: return await handle_bot_turn(session) # Auto-proceed to evaluate

    elif bot_state == "EVALUATING_ANSWER":
        q_text = session.get('current_question_text', "the current question")
        q_criteria = session.get('current_question_criteria', [])
        user_exchanges = [ex['content'] for ex in session['collected_answers'].get(current_q_id, []) if ex['role'] == 'user']
        last_user_answer = user_exchanges[-1] if user_exchanges else "No answer provided by user."

        criteria_prompt_text = ""
        if q_criteria:
            criteria_prompt_text = "When evaluating, consider these criteria or examples for a good answer to the question:\n" + "\n".join([f"- {c}" for c in q_criteria])
        
        evaluation_prompt_messages = [
            {"role": "system", "content": llm_service.get_system_prompt()},
            {"role": "user", "content": f"The current predefined question is: \"{q_text}\"\n{criteria_prompt_text}\nThe patient's latest answer to this question (or to one of my follow-ups for this question) is: \"{last_user_answer}\"\n\nPlease evaluate this answer. If it's sufficient for THIS predefined question, respond with ONLY the JSON object {{ \"action\": \"question_sufficiently_answered\" }}. Otherwise, ask a single, targeted plain text follow-up question to get the missing information FOR THIS predefined question."}
        ]
        
        llm_response_raw = llm_service.chat(evaluation_prompt_messages)
        
        try:
            llm_response_data = json.loads(llm_response_raw)
            if isinstance(llm_response_data, dict) and llm_response_data.get("action") == "question_sufficiently_answered":
                print(f"LLM signaled sufficiency for Q_ID '{current_q_id}'.")
                ack_text = "Okay, thank you for that information." 
                ack_msg = SessionManager.add_message_to_display_chat(session, "assistant", ack_text)
                components.append(UIComponents.chat_message(ack_msg))
                SessionManager.add_exchange_to_collected_answers(session, current_q_id, "assistant", ack_text) 

                session['current_question_follow_up_count'] = 0 
                next_q_id = question_service.get_next_question_id(current_q_id)
                if next_q_id:
                    session['current_question_id'] = next_q_id
                    session['current_question_text'] = question_service.get_question_text_by_id(next_q_id)
                    session['current_question_criteria'] = question_service.get_question_criteria_by_id(next_q_id)
                    session['bot_state'] = "WAITING_TO_ASK_PREDEFINED"
                    print(f"EVALUATING_ANSWER (sufficient) -> WAITING_TO_ASK_PREDEFINED for Q_ID: '{next_q_id}'")
                    if debug_mode: components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
                    else: return await handle_bot_turn(session)
                else: 
                    session['bot_state'] = "GENERATING_SUMMARY"
                    print(f"EVALUATING_ANSWER (sufficient, last q) -> GENERATING_SUMMARY")
                    if debug_mode: components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
                    else: return await handle_bot_turn(session)
            else: 
                raise ValueError("JSON from LLM was not the expected action signal.")
        except (json.JSONDecodeError, ValueError) as e: 
            print(f"LLM response not a valid action signal (Error: {e}). Treating as follow-up: '{llm_response_raw}'")
            follow_up_question_text = llm_response_raw.strip() # Ensure no leading/trailing whitespace
            
            if not follow_up_question_text: # Handle case where LLM might return empty or whitespace
                follow_up_question_text = "Could you please provide a bit more detail?"
                print("LLM returned empty follow-up, using generic one.")

            session['current_question_follow_up_count'] += 1
            if session['current_question_follow_up_count'] > MAX_FOLLOW_UPS:
                print(f"Max follow-ups ({session['current_question_follow_up_count']}) reached for Q_ID '{current_q_id}'. Forcing move.")
                forced_ack_text = "Okay, let's move on to the next point for now."
                forced_ack_msg = SessionManager.add_message_to_display_chat(session, "assistant", forced_ack_text)
                components.append(UIComponents.chat_message(forced_ack_msg))
                SessionManager.add_exchange_to_collected_answers(session, current_q_id, "assistant", forced_ack_text)
                
                session['current_question_follow_up_count'] = 0
                next_q_id = question_service.get_next_question_id(current_q_id)
                if next_q_id:
                    session['current_question_id'] = next_q_id
                    session['current_question_text'] = question_service.get_question_text_by_id(next_q_id)
                    session['current_question_criteria'] = question_service.get_question_criteria_by_id(next_q_id)
                    session['bot_state'] = "WAITING_TO_ASK_PREDEFINED"
                    if debug_mode: components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
                    else: return await handle_bot_turn(session)
                else:
                    session['bot_state'] = "GENERATING_SUMMARY"
                    if debug_mode: components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
                    else: return await handle_bot_turn(session)
            else: 
                follow_up_msg = SessionManager.add_message_to_display_chat(session, "assistant", follow_up_question_text)
                components.append(UIComponents.chat_message(follow_up_msg))
                SessionManager.add_exchange_to_collected_answers(session, current_q_id, "assistant", follow_up_question_text)
                session['bot_state'] = "EXPECTING_USER_ANSWER" 
                print(f"EVALUATING_ANSWER (follow-up #{session['current_question_follow_up_count']}) -> EXPECTING_USER_ANSWER for Q_ID '{current_q_id}'")
                if debug_mode: components.append(UIComponents.clear_debug_action_area_component()) 

    elif bot_state == "GENERATING_SUMMARY":
        summary_prompt_parts = [
            llm_service.get_system_prompt(), # Provide full system context
            "\n\nThe following is a transcript of the patient's answers to a series of predefined questions. Please provide a concise, well-structured clinical summary of this information. Focus on the key medical details provided by the patient."
        ]
        collected_data = session.get('collected_answers', {})
        if not collected_data:
            summary_prompt_parts.append("\n\nNo specific answers were collected from the patient during this session.")
        else:
            for q_id, exchanges in collected_data.items():
                q_text = question_service.get_question_text_by_id(q_id)
                summary_prompt_parts.append(f"\n\nRegarding the question: \"{q_text}\"")
                full_exchange_text_for_q = []
                for ex in exchanges:
                    role_label = "Patient" if ex['role'] == 'user' else "Assistant (clarification/ack)"
                    full_exchange_text_for_q.append(f"  {role_label}: {ex['content']}")
                summary_prompt_parts.append("\n".join(full_exchange_text_for_q))
        
        summary_llm_messages = [{"role": "user", "content": "\n".join(summary_prompt_parts)}] # Changed to user role for the content part
        final_summary_from_llm = llm_service.chat(summary_llm_messages)

        summary_msg_data = SessionManager.add_message_to_display_chat(session, "assistant", "Here is a summary of our conversation:\n\n" + final_summary_from_llm)
        components.append(UIComponents.chat_message(summary_msg_data))
        
        thank_you_msg_data = SessionManager.add_message_to_display_chat(session, "assistant", "Thank you for providing your information. The consultation can now begin.")
        components.append(UIComponents.chat_message(thank_you_msg_data))

        session['bot_state'] = "DONE"
        print(f"GENERATING_SUMMARY -> DONE")
        if debug_mode: components.append(UIComponents.clear_debug_action_area_component())

    elif bot_state == "DONE":
        print("Bot state is DONE. No further actions.")
        if debug_mode: components.append(UIComponents.clear_debug_action_area_component())
    return components

@rt("/chat")
async def post_chat_message(user_message: str, session: dict):
    components = [UIComponents.clear_input_component()]
    bot_state = session.get('bot_state', "INIT")
    debug_mode = session.get('debug_mode_enabled', False)

    if bot_state == "DONE":
        print(f"User message '{user_message}' received but bot is DONE. Ignoring.")
        ended_msg = SessionManager.add_message_to_display_chat(session, "assistant", "This session has ended. Please restart if you wish to begin again.")
        components.append(UIComponents.chat_message(ended_msg))
        return tuple(components)
    
    if bot_state == "GENERATING_SUMMARY" and not debug_mode: 
        print(f"User message '{user_message}' received while bot is auto-summarizing. Ignoring.")
        return tuple(components)

    if not user_message or not user_message.strip():
        print("Empty user message received. No action.")
        if debug_mode and session.get('bot_state') == "EXPECTING_USER_ANSWER":
            components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
        return tuple(components)
    
    user_msg_data = SessionManager.add_message_to_display_chat(session, "user", user_message)
    components.append(UIComponents.chat_message(user_msg_data))

    if bot_state == "EXPECTING_USER_ANSWER":
        components.extend(await handle_bot_turn(session, user_message_content=user_message))
    elif bot_state == "WAITING_TO_ASK_PREDEFINED" and debug_mode:
        print(f"User message '{user_message}' received while bot WAITING_TO_ASK_PREDEFINED (debug). Displayed. Bot asks on 'Next Step'.")
        components.append(Div(UIComponents.continue_debug_button(), id="debug-action-area", hx_swap_oob="true"))
    else:
        print(f"User message '{user_message}' received in unhandled bot state '{bot_state}'. Displayed, not processed by bot.")
    return tuple(components)

@rt("/continue_debug_or_next_step") 
async def continue_debug_or_next_step(session: dict):
    print(f"'/continue_debug_or_next_step' called. Current bot state: {session.get('bot_state')}")
    return tuple(await handle_bot_turn(session, user_message_content=None))

@rt("/restart_chat")
async def restart_chat_session(session: dict):
    print(f"Restarting chat. Clearing session ID: {session.get('session_id')}")
    session.clear() 
    return HTMLResponse(content="", status_code=200, headers={"HX-Refresh": "true"})

# -----------------------------------------------------------------------------
# APPLICATION ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Starting QuestionnAIre Chatbot...")
    print(f"LLM Service: Using provider '{llm_service.provider_name}' with model '{llm_service.get_model_name()}'")
    print(f"Question Service: Loaded {len(question_service.get_all_question_ids())} questions from '{question_service.filepath}'")
    if not question_service.get_all_question_ids(): print("Warning: No questions loaded.")
    else: print(f"First question ID: {question_service.get_first_question_id()}")
    SessionManager.cleanup() 
    serve(port=5001)
