# chat.py
import ollama
import uuid
import datetime
import os
import shutil
import json
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
        class MockMessage:
            def __init__(self, content):
                self.content = content

        class MockChoice:
            def __init__(self, content):
                self.message = MockMessage(content)

        class MockHFResponse:
            def __init__(self, content):
                self.choices = [MockChoice(content)]

        class MockHFClient:
            def chat_completion(self, messages, max_tokens=None, temperature=None):
                print("--- Using Mock Hugging Face Client ---")
                return MockHFResponse('Mock response from Hugging Face. Please set HF_TOKEN environment variable.')
        
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
# MAIN APPLICATION LOGIC (Refaktorisiert)
# -----------------------------------------------------------------------------
question_service = QuestionService() 

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
    
    provider_configs = {}
    if "huggingface" in config:
        provider_configs["huggingface"] = config["huggingface"]
    if "ollama" in config:
        provider_configs["ollama"] = config["ollama"]
    
    return LLMService(provider=provider, model_name=model_name, config=provider_configs)

llm_service = create_llm_service_from_config()

async def _trigger_initial_bot_action(session: dict):
    if session.get('bot_state') == "INIT":
        first_q_id = question_service.get_first_question_id()
        if first_q_id:
            session['current_question_id'] = first_q_id
            session['current_question_text'] = question_service.get_question_text_by_id(first_q_id)
            session['current_question_criteria'] = question_service.get_question_criteria_by_id(first_q_id)
            session['bot_state'] = "WAITING_TO_ASK_PREDEFINED" 
            print(f"INIT: Set to ask first question: {first_q_id}. Bot state: {session['bot_state']}")
        else:
            SessionManager.add_message_to_display_chat(session, "assistant", "No questions were configured for this session.")
            session['bot_state'] = "DONE"
            print("INIT: No questions. Bot state: DONE")

async def handle_bot_turn(session: dict, user_message_content: str | None = None):
    MAX_FOLLOW_UPS = 3
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
            if not debug_mode: await handle_bot_turn(session)
        else: 
            SessionManager.add_message_to_display_chat(session, "assistant", "No questions are configured. End of session.")
            session['bot_state'] = "DONE"
            print("INIT -> DONE (no questions)")

    elif bot_state == "WAITING_TO_ASK_PREDEFINED":
        q_id_to_ask = session.get('current_question_id')
        q_text_to_ask = session.get('current_question_text')
        if not q_id_to_ask or not q_text_to_ask:
            print(f"Error: WAITING_TO_ASK_PREDEFINED but Q_ID ('{q_id_to_ask}') or text is invalid.")
            session['bot_state'] = "DONE" 
            SessionManager.add_message_to_display_chat(session, "assistant", "System error: Cannot find the next question.")
            return

        SessionManager.add_message_to_display_chat(session, "assistant", q_text_to_ask)
        session['bot_state'] = "EXPECTING_USER_ANSWER"
        session['current_question_follow_up_count'] = 0
        print(f"WAITING_TO_ASK_PREDEFINED -> EXPECTING_USER_ANSWER for Q_ID: '{q_id_to_ask}'")

    elif bot_state == "EXPECTING_USER_ANSWER":
        if user_message_content is None: 
            print("EXPECTING_USER_ANSWER but no user_message_content. Waiting.")
            return 
        
        SessionManager.add_exchange_to_collected_answers(session, current_q_id, "user", user_message_content)
        session['bot_state'] = "EVALUATING_ANSWER"
        print(f"EXPECTING_USER_ANSWER -> EVALUATING_ANSWER for Q_ID '{current_q_id}'. User answer: '{user_message_content}'")
        if not debug_mode: await handle_bot_turn(session)

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
                SessionManager.add_message_to_display_chat(session, "assistant", ack_text)
                SessionManager.add_exchange_to_collected_answers(session, current_q_id, "assistant", ack_text) 

                session['current_question_follow_up_count'] = 0 
                next_q_id = question_service.get_next_question_id(current_q_id)
                if next_q_id:
                    session['current_question_id'] = next_q_id
                    session['current_question_text'] = question_service.get_question_text_by_id(next_q_id)
                    session['current_question_criteria'] = question_service.get_question_criteria_by_id(next_q_id)
                    session['bot_state'] = "WAITING_TO_ASK_PREDEFINED"
                    print(f"EVALUATING_ANSWER (sufficient) -> WAITING_TO_ASK_PREDEFINED for Q_ID: '{next_q_id}'")
                    if not debug_mode: await handle_bot_turn(session)
                else: 
                    session['bot_state'] = "GENERATING_SUMMARY"
                    print(f"EVALUATING_ANSWER (sufficient, last q) -> GENERATING_SUMMARY")
                    if not debug_mode: await handle_bot_turn(session)
            else: 
                raise ValueError("JSON from LLM was not the expected action signal.")
        except (json.JSONDecodeError, ValueError) as e: 
            print(f"LLM response not a valid action signal (Error: {e}). Treating as follow-up: '{llm_response_raw}'")
            follow_up_question_text = llm_response_raw.strip()
            
            if not follow_up_question_text:
                follow_up_question_text = "Could you please provide a bit more detail?"
                print("LLM returned empty follow-up, using generic one.")

            session['current_question_follow_up_count'] += 1
            if session['current_question_follow_up_count'] > MAX_FOLLOW_UPS:
                print(f"Max follow-ups ({session['current_question_follow_up_count']}) reached for Q_ID '{current_q_id}'. Forcing move.")
                forced_ack_text = "Okay, let's move on to the next point for now."
                SessionManager.add_message_to_display_chat(session, "assistant", forced_ack_text)
                SessionManager.add_exchange_to_collected_answers(session, current_q_id, "assistant", forced_ack_text)
                
                session['current_question_follow_up_count'] = 0
                next_q_id = question_service.get_next_question_id(current_q_id)
                if next_q_id:
                    session['current_question_id'] = next_q_id
                    session['current_question_text'] = question_service.get_question_text_by_id(next_q_id)
                    session['current_question_criteria'] = question_service.get_question_criteria_by_id(next_q_id)
                    session['bot_state'] = "WAITING_TO_ASK_PREDEFINED"
                    if not debug_mode: await handle_bot_turn(session)
                else:
                    session['bot_state'] = "GENERATING_SUMMARY"
                    if not debug_mode: await handle_bot_turn(session)
            else: 
                SessionManager.add_message_to_display_chat(session, "assistant", follow_up_question_text)
                SessionManager.add_exchange_to_collected_answers(session, current_q_id, "assistant", follow_up_question_text)
                session['bot_state'] = "EXPECTING_USER_ANSWER" 
                print(f"EVALUATING_ANSWER (follow-up #{session['current_question_follow_up_count']}) -> EXPECTING_USER_ANSWER for Q_ID '{current_q_id}'")

    elif bot_state == "GENERATING_SUMMARY":
        summary_prompt_parts = [
            llm_service.get_system_prompt(),
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
        
        summary_llm_messages = [{"role": "user", "content": "\n".join(summary_prompt_parts)}]
        final_summary_from_llm = llm_service.chat(summary_llm_messages)

        SessionManager.add_message_to_display_chat(session, "assistant", "Here is a summary of our conversation:\n\n" + final_summary_from_llm)
        SessionManager.add_message_to_display_chat(session, "assistant", "Thank you for providing your information. The consultation can now begin.")

        session['bot_state'] = "DONE"
        print(f"GENERATING_SUMMARY -> DONE")

    elif bot_state == "DONE":
        print("Bot state is DONE. No further actions.")

