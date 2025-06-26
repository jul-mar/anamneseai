# chat.py (renamed to questionnAIre.py by user)
from fasthtml.common import *
import ollama
import uuid
import datetime # Kept for now
import os
import shutil
import json # For parsing LLM's JSON output

# -----------------------------------------------------------------------------
# QUESTION SETS DEFINITION (NEW)
# -----------------------------------------------------------------------------
QUESTION_SETS = {
    "respiratory_assessment_v3": { 
        "name": "Respiratory Symptom Assessment (Free-Form with Criteria Guidance)",
        "description": "Standard questions for patients presenting with cough, sputum, or dyspnea. All answers are free-form text, guided by criteria for LLM interpretation.",
        "questions": [
            # --- Cough Section ---
            {
                "id": "cough_present",
                "text": "To start, are you currently experiencing any coughing?",
                "criteria": [
                    "Yes, I have a cough.", "No, I do not have a cough.", "A little bit.",
                    "Yes, quite a lot.", "Not really, no."
                ],
                "follow_up_condition": "if_yes",
                "sub_questions": [
                    {"id": "cough_onset", "text": "When did the cough start?", "criteria": ["Example: About 3 days ago", "Example: Last Monday", "Example: For roughly 2 weeks", "A specific date or duration is helpful."]},
                    {"id": "cough_frequency", "text": "How often do you find yourself coughing?", "criteria": ["Constantly", "Frequently throughout the day (e.g., several times an hour)", "Occasionally (e.g., a few times a day)", "Rarely (e.g., only once or twice a day)", "Mostly in the mornings", "It's an all day long thing"]},
                    {"id": "cough_character", "text": "How would you describe the cough? For example, is it dry, or are you coughing anything up? Is it a tickling cough, or more of a deep cough?", "criteria": ["Dry (no phlegm)", "Chesty (with phlegm)", "Hacking cough", "Barking sound", "Tickling in the throat", "Deep from the chest", "Example: It's a dry, irritating cough.", "Example: I cough up some phlegm sometimes."]},
                    {"id": "cough_triggers", "text": "Is there anything specific that seems to trigger your cough or make it worse?", "criteria": ["Lying down", "Exercise or physical activity", "Cold air", "After eating certain foods", "Dust or other irritants", "Specific times of day (e.g., mornings, nights)", "Example: It gets worse when I lie down at night."]},
                    {"id": "cough_relievers", "text": "Does anything make your cough better or provide some relief?", "criteria": ["Drinking water or warm fluids", "Specific medication or lozenges", "Sitting upright", "Avoiding known triggers", "Example: Warm tea seems to help a bit."]},
                    {"id": "cough_severity_impact", "text": "How much would you say the cough is affecting your daily life or your sleep?", "criteria": ["Not at all, it's just minor", "Mildly, a bit annoying but manageable", "Moderately, it interferes with some activities or sleep", "Severely, it significantly disrupts my activities and/or sleep", "Example: It keeps me up at night.", "Example: It's mostly just a nuisance during the day."]}
                ]
            },
            # --- Sputum Section ---
            {
                "id": "sputum_present",
                "text": "When you cough, are you producing or coughing up any sputum, which is also known as phlegm?",
                "criteria": ["Yes, I am producing sputum.", "No, I am not producing sputum.", "Yes, sometimes when I cough hard.", "No, my cough is completely dry."],
                "follow_up_condition": "if_yes",
                "sub_questions": [
                    {"id": "sputum_color", "text": "What is the color of the sputum?", "criteria": ["Clear", "White", "Yellow", "Green", "Brown", "Rust-colored", "Pink-tinged or Frothy (can indicate fluid)", "Red (contains blood)", "Example: Mostly clear, sometimes a bit yellowish."]},
                    {"id": "sputum_amount", "text": "Approximately how much sputum are you producing in a 24-hour period?", "criteria": ["Very little (just a bit on a tissue)", "About a teaspoonful total", "Around a tablespoonful total", "Roughly a quarter of a cup throughout the day", "More than half a cup", "Example: Just a small amount in the morning."]},
                    {"id": "sputum_consistency", "text": "What is the consistency of the sputum? Is it thin, thick, frothy?", "criteria": ["Watery or Thin", "Frothy", "Thick or Sticky", "Jelly-like", "Example: It's quite thick and hard to cough up."]},
                    {"id": "sputum_blood_presence", "text": "Have you noticed any blood in your sputum? This might look like red streaks, pink froth, or more obvious blood.", "criteria": ["Yes, I've seen blood.", "No, I have not seen any blood.", "I think I saw a tiny speck once.", "It was pinkish this morning."],
                     "follow_up_condition": "if_yes", "sub_questions": [
                         {"id": "sputum_blood_details", "text": "Could you describe the blood you saw? For instance, how much was there and how often have you seen it?", "criteria": ["Example: Just a few red streaks once.", "Example: A tiny bit mixed in this morning.", "Example: About a teaspoonful of bright red blood.", "How much (e.g., streaks, teaspoon, tablespoon)?", "How often (e.g., once, multiple times, with every cough)?"]}
                    ]},
                    {"id": "sputum_odor", "text": "Does the sputum have any unusual or foul odor?", "criteria": ["Yes, it has an odor.", "No, it does not have an odor.", "Example: No, not that I've noticed.", "Example: Yes, it smells a bit off/musty/foul."]}
                ]
            },
            # --- Dyspnea (formerly Shortness of Breath) Section ---
            {
                "id": "dyspnea_present",
                "text": "Have you been experiencing any dyspnea (which is the medical term for shortness of breath)?",
                "criteria": ["Yes, I have experienced dyspnea.", "No, I have not experienced dyspnea.", "Yes, I've been feeling breathless.", "No, my breathing feels normal."],
                "follow_up_condition": "if_yes",
                "sub_questions": [
                    {"id": "dyspnea_onset_timing", "text": "Regarding the dyspnea, when did it first start, and would you say it came on suddenly or more gradually?", "criteria": ["Example: It started suddenly yesterday evening.", "Example: It's been coming on slowly over the past few weeks.", "Did it start suddenly or gradually?", "When did you first notice the dyspnea?"]},
                    {"id": "dyspnea_triggers_activity", "text": "What level of physical activity tends to bring on your dyspnea?", "criteria": ["Only with strenuous activity (like running or heavy work)", "With moderate activity (like brisk walking or climbing a couple of flights of stairs)", "With mild activity (like walking around the house or getting dressed)", "Even when I am at rest", "Example: When I climb stairs.", "Example: Just walking to the kitchen can make me breathless."]},
                    {"id": "dyspnea_other_triggers", "text": "Are there any other situations or factors that seem to trigger your dyspnea?", "criteria": ["Lying flat in bed", "Exposure to cold air or allergens", "When I feel stressed or anxious", "Specific times of day", "Example: It's worse when I lie down."]},
                    {"id": "dyspnea_relievers", "text": "Is there anything that helps to relieve your dyspnea?", "criteria": ["Resting for a few minutes", "Sitting upright", "Using an inhaler (if prescribed)", "Avoiding known triggers", "Example: Resting usually helps."]},
                    {"id": "dyspnea_severity_impact", "text": "How much is this dyspnea affecting your daily activities or routine?", "criteria": ["Not at all, it's barely noticeable", "Mildly, I can mostly do what I need to but I'm aware of it", "Moderately, it limits some of my usual activities", "Severely, it significantly limits what I can do", "Example: I have to stop often when walking due to dyspnea."]},
                    {"id": "dyspnea_accompanying_symptoms", "text": "When you experience dyspnea, do you notice any other symptoms at the same time?", "criteria": ["Chest tightness or pain", "Wheezing", "A racing heart or palpitations", "Dizziness or lightheadedness", "Swelling in your feet or ankles", "Example: I also get some chest tightness with the dyspnea.", "Example: My heart feels like it's racing when I experience dyspnea."]},
                    {"id": "dyspnea_orthopnea", "text": "Do you experience dyspnea or find it harder to breathe when you lie flat? For instance, do you need to use extra pillows to prop yourself up to breathe comfortably at night?", "criteria": ["Yes, I need to use extra pillows (e.g., 2, 3, or more) due to dyspnea.", "No, lying flat does not cause dyspnea for me.", "Example: Yes, I use three pillows to sleep to avoid dyspnea.", "Example: I haven't noticed any difference in my breathing when lying flat."]},
                    {"id": "dyspnea_pnd", "text": "Have you ever woken up at night suddenly experiencing dyspnea or as if you are gasping for air?", "criteria": ["Yes, that has happened.", "No, that has not happened.", "Example: Yes, a few times last week I woke up gasping.", "Example: No, never."]}
                ]
            }
        ]
    }
}

# -----------------------------------------------------------------------------
# QUESTION NAVIGATOR (NEW / REFINED)
# -----------------------------------------------------------------------------
class QuestionNavigator:
    def __init__(self, question_sets_data):
        self.question_sets = question_sets_data

    def _get_question_obj_from_path(self, set_id, path_to_parent_list, current_index):
        """Helper to retrieve a specific question object."""
        if set_id not in self.question_sets: return None
        
        current_list = self.question_sets[set_id]["questions"]
        for q_id_in_path in path_to_parent_list:
            found_parent = False
            for q_obj in current_list:
                if q_obj["id"] == q_id_in_path:
                    current_list = q_obj.get("sub_questions", [])
                    found_parent = True
                    break
            if not found_parent: return None # Invalid path

        if 0 <= current_index < len(current_list):
            return current_list[current_index]
        return None

    def start_question_set(self, session, set_id):
        if set_id not in self.question_sets or not self.question_sets[set_id]["questions"]:
            session['active_question_set_id'] = None
            return None # Set not found or empty

        session['active_question_set_id'] = set_id
        session['current_question_path'] = []  # Path of parent IDs to the current list of questions
        session['current_question_index'] = 0  # Index in that list
        session['structured_answers'] = {}     # Store structured answers here

        first_question_obj = self._get_question_obj_from_path(set_id, [], 0)
        if first_question_obj:
            session['active_question_obj'] = first_question_obj # Store the full current question object
            return first_question_obj["text"]
        return None

    def get_next_question(self, session, llm_interpretation_of_last_answer):
        """
        Determines the next question based on the last answer's interpretation.
        llm_interpretation_of_last_answer is a dict:
        {"is_adequate": bool, "interpreted_choice_or_category": str, 
         "answer_summary": str, "clarifying_question": str|None}
        """
        active_set_id = session.get('active_question_set_id')
        current_q_obj = session.get('active_question_obj') # Question just answered

        if not active_set_id or not current_q_obj:
            return None # No active set or question

        # Store the summary of the last answer
        session.setdefault('structured_answers', {})[current_q_obj['id']] = llm_interpretation_of_last_answer['answer_summary']

        if not llm_interpretation_of_last_answer['is_adequate'] and llm_interpretation_of_last_answer['clarifying_question']:
            # Stay on the current question, ask for clarification
            session['active_question_obj'] = current_q_obj # Re-affirm current question
            return llm_interpretation_of_last_answer['clarifying_question']

        # Current question was answered adequately, try to find next
        path = list(session.get('current_question_path', []))
        index = session.get('current_question_index', 0)

        # 1. Check for sub-questions based on condition
        follow_up_triggered = False
        if current_q_obj.get("sub_questions") and current_q_obj.get("follow_up_condition"):
            condition = current_q_obj["follow_up_condition"]
            interpreted_choice = llm_interpretation_of_last_answer.get("interpreted_choice_or_category", "").lower()
            if condition == "if_yes" and interpreted_choice == "yes":
                follow_up_triggered = True
            # Add more conditions here if needed (e.g., "if_no", specific category matches)
        
        if follow_up_triggered:
            new_path = path + [current_q_obj["id"]]
            new_index = 0
            next_q_obj = self._get_question_obj_from_path(active_set_id, new_path, new_index)
            if next_q_obj:
                session['current_question_path'] = new_path
                session['current_question_index'] = new_index
                session['active_question_obj'] = next_q_obj
                return next_q_obj["text"]

        # 2. No sub-questions to ask (or condition not met), try to advance to next sibling
        new_path = list(path) # Keep current path
        new_index = index + 1
        next_q_obj = self._get_question_obj_from_path(active_set_id, new_path, new_index)
        if next_q_obj:
            session['current_question_path'] = new_path
            session['current_question_index'] = new_index
            session['active_question_obj'] = next_q_obj
            return next_q_obj["text"]

        # 3. No more siblings, try to go up to parent and ask parent's next sibling
        while new_path: # While we have a parent in the path
            # Pop from current path to get to parent's level
            # The index we need is parent's index in *its* sibling list
            # This logic is simplified: assumes parent was at 'parent_index'
            
            # To correctly find the parent's index and then try its next sibling:
            # The 'path' variable before this loop started points to the list where the current exhausted sub-list lived.
            # We need to find the index of the last element of 'path' within *its* parent's list of questions.
            
            # Simplified "go up":
            # The current path and index point to the list that was just exhausted.
            # We need to effectively get the parent of that list, and increment *its* index.
            
            # This simplified "go up" logic might just end the current branch and try next top-level if not careful.
            # For a more robust "go up and find uncle":
            # 1. Get the parent object that contained the list we just finished.
            # 2. Find that parent object's index in *its* own list of siblings.
            # 3. Increment that index and try to get the "uncle".
            # This requires careful state tracking of indices at each level of the path.
            
            # Current simplified approach:
            # If a sub-question list is exhausted, we effectively go back to the parent's level
            # and try to get the next question from where the parent was.
            # This means we need to pop from path and retrieve the index of the *parent* in *its* list.

            # Let's adjust state to point to the parent of the current list, then try to get *its* next sibling.
            # This requires a more sophisticated path and index management than simple list appends.
            # For now, we'll end the branch if no direct sibling or sub-question.
            # A full "go up and find next" is a more complex graph traversal.
            
            # To implement full "go up":
            # We would need session['question_path_indices'] = [idx_at_level0, idx_at_level1, ...]
            # And session['current_path_ids'] = [id_at_level0, id_at_level1, ...]
            # When a list is exhausted at current_path_ids[-1], pop both, increment question_path_indices[-1],
            # then try to get question at new indices from new current_path_ids.

            # Temporary simplification: if sub-list ends, and main list had more, it will find them.
            # If a deep sub-list ends, this simplified logic will likely jump to next top-level.
            # For now, let's assume we only go one level deep for "next sibling" after sub-questions.
             session['active_question_obj'] = None # Mark as no current Q
             return None # Signal end of this branch / needs better "go up" logic for full traversal.


        # 4. No more top-level questions in the set
        session['active_question_set_id'] = None
        session['active_question_obj'] = None
        return None # Signal end of set

# Instantiate navigator globally
question_navigator = QuestionNavigator(QUESTION_SETS)

# -----------------------------------------------------------------------------
# LLM SERVICE LAYER (Modified to add interpretation capability)
# -----------------------------------------------------------------------------
class LLMService:
    DEFAULT_HOST = "http://localhost:11434"
    DEFAULT_MODEL = "gemma3:4b-it-qat" # User's preferred model
    GENERAL_SYSTEM_PROMPT = """You are QuestionnAIre, a medical assistant chatbot... (Your existing general prompt)""" # Shortened for brevity

    INTERPRETATION_SYSTEM_PROMPT_TEMPLATE = """
    You are an expert medical information interpreter. Your task is to analyze a patient's response to a specific question.
    The patient was asked the following question by a chatbot:
    Question: "{question_text}"
    The following criteria or examples were associated with this question to guide the expected type of answer:
    Criteria: {question_criteria}

    The patient responded: "{patient_answer}"

    Based on the patient's response and the provided criteria:
    1. Is the question adequately and clearly answered for a medical intake? (Respond with true or false)
    2. If the question implied a choice or category suggested by the criteria (e.g., Yes/No, a specific option from the criteria, a type of duration), what is your interpretation of the patient's choice or the main category their answer falls into? If no clear choice or category, or if not applicable, state "N/A" or "unclear". (Examples for choice: "Yes", "No", "Constantly", "About 3 days ago")
    3. Provide a concise summary of the key information from the patient's answer relevant to the question that was asked. This summary will be stored.
    4. If the answer is not adequate or clear, what specific clarifying question should the chatbot ask to get the necessary information FOR THE ORIGINAL QUESTION? If the answer is adequate, this should be null. The clarifying question should be natural and empathetic.

    Return your analysis STRICTLY as a JSON object with the following keys: "is_adequate" (boolean), "interpreted_choice_or_category" (string), "answer_summary" (string), "clarifying_question" (string or null).
    Example of a valid JSON output:
    {{"is_adequate": true, "interpreted_choice_or_category": "Yes", "answer_summary": "Patient confirms having a cough.", "clarifying_question": null}}
    Another example:
    {{"is_adequate": false, "interpreted_choice_or_category": "unclear", "answer_summary": "Patient mentioned feeling 'a bit off'.", "clarifying_question": "Could you please tell me a bit more about what 'a bit off' means regarding the cough?"}}
    """


    def __init__(self, host=None, model_name=None):
        self.host = host or self.DEFAULT_HOST
        self.model_name = model_name or self.DEFAULT_MODEL # This will be used for interpretation
        self.general_chat_model = model_name or self.DEFAULT_MODEL # Could be different for general chat
        self.client = None
        self.initialize_client()

    def initialize_client(self):
        try:
            # ... (same as your existing initialize_client) ...
            print(f"Attempting to connect to Ollama at {self.host}") # Included for completeness
            self.client = ollama.Client(host=self.host)
            models = self.client.list().get('models', [])
            available_models = [m.get('name', '') for m in models if isinstance(m, dict) and 'name' in m]
            if self.model_name not in available_models:
                print(f"Warning: Model {self.model_name} for interpretation not found. Proceeding anyway.")
            if self.general_chat_model not in available_models and self.general_chat_model != self.model_name:
                 print(f"Warning: Model {self.general_chat_model} for general chat not found. Proceeding anyway.")
            print(f"Ollama client initialized. Interpretation model: {self.model_name}, General chat model: {self.general_chat_model}")

        except Exception as e:
            print(f"Error connecting to Ollama: {e}. Starting with mock client.")
            self.client = self._create_mock_client()


    def _create_mock_client(self):
        # ... (same as your existing mock client) ...
        class MockOllamaClient: # Included for completeness
            def list(self): return {'models': []}
            def chat(self, model, messages):
                print("\n--- Using Mock Ollama Client ---") # ...
                # Simplified mock response for interpretation
                if "expert medical information interpreter" in messages[0]["content"]:
                     # Try to provide a somewhat valid JSON for interpretation mock
                    return {'message': {'content': json.dumps({
                        "is_adequate": True,
                        "interpreted_choice_or_category": "N/A (mock)",
                        "answer_summary": "Mocked adequate answer.",
                        "clarifying_question": None
                    })}}
                return {'message': {'content': '*(Error: Mock Ollama - General Chat)*'}}
        return MockOllamaClient()

    def get_model_name(self): # For general display if needed
        return self.general_chat_model
    
    def get_general_system_prompt(self):
        return self.GENERAL_SYSTEM_PROMPT

    def interpret_answer(self, question_obj, patient_answer_text):
        """Sends patient's answer to LLM for interpretation against question criteria."""
        prompt_text = self.INTERPRETATION_SYSTEM_PROMPT_TEMPLATE.format(
            question_text=question_obj["text"],
            question_criteria=json.dumps(question_obj.get("criteria", [])), # Send criteria as JSON string within prompt
            patient_answer=patient_answer_text
        )
        
        messages = [{"role": "system", "content": prompt_text}]
        # Note: For this interpretation task, we might not need prior chat history,
        # just the specific question, criteria, and the user's immediate answer.
        # Or, we could send the last user message as {"role": "user", "content": patient_answer_text}
        # with the system prompt being the template *before* the patient_answer part.
        # Let's try with a single system message containing all context.

        print(f"\n----- SENDING PROMPT TO LLM FOR INTERPRETATION (Model: {self.model_name}) -----")
        print(prompt_text[:500] + "..." if len(prompt_text) > 500 else prompt_text) # Log snippet
        print("----- END OF INTERPRETATION PROMPT -----\n")

        try:
            response = self.client.chat(
                model=self.model_name, # Use interpretation model
                messages=messages,
                # options={"temperature": 0.3} # Lower temp for more deterministic JSON
                format="json" # Request JSON output if Ollama server/model supports it
            )
            llm_output_str = response.get('message', {}).get('content', '{}')
            print(f"LLM Interpretation Raw Output: {llm_output_str}")
            # Ensure the output is valid JSON
            try:
                parsed_json = json.loads(llm_output_str)
                # Validate expected keys
                if not all(k in parsed_json for k in ["is_adequate", "interpreted_choice_or_category", "answer_summary", "clarifying_question"]):
                    print("LLM interpretation JSON missing required keys. Falling back.")
                    raise ValueError("Missing keys in LLM interpretation response")
                return parsed_json
            except json.JSONDecodeError as je:
                print(f"LLM interpretation output was not valid JSON: {je}")
                print(f"LLM raw output: {llm_output_str}")
                 # Fallback if JSON parsing fails - treat as inadequate, ask to rephrase
                return {
                    "is_adequate": False,
                    "interpreted_choice_or_category": "unclear (parsing_error)",
                    "answer_summary": patient_answer_text, # Store raw answer
                    "clarifying_question": "I'm having a little trouble understanding that. Could you please try phrasing it differently?"
                }

        except Exception as e:
            print(f"Error during LLM interpretation call: {e}")
            return { # Fallback on error
                "is_adequate": False, # Assume not adequate if interpretation fails
                "interpreted_choice_or_category": "N/A (error)",
                "answer_summary": patient_answer_text, # Store raw answer
                "clarifying_question": "I encountered a technical issue. Could you please repeat your answer?"
            }

    def general_chat(self, messages_history):
        """Handles general chat conversation using the main system prompt."""
        ollama_messages = [{"role": "system", "content": self.GENERAL_SYSTEM_PROMPT}]
        for msg in messages_history:
            if msg["role"] != "system":
                ollama_messages.append({"role": msg["role"], "content": msg["content"]})
        
        print(f"\n----- SENDING PROMPT TO LLM FOR GENERAL CHAT (Model: {self.general_chat_model}) -----")
        # ... (optional logging of general chat prompt) ...
        print("----- END OF GENERAL CHAT PROMPT -----\n")

        try:
            response = self.client.chat(
                model=self.general_chat_model,
                messages=ollama_messages
            )
            return response.get('message', {}).get('content', 'No response from AI')
        except Exception as e:
            print(f"Error in general_chat: {e}")
            return "Sorry, there was an error processing your request."

# -----------------------------------------------------------------------------
# SESSION MANAGEMENT (Potentially add questionnaire state methods)
# -----------------------------------------------------------------------------
class SessionManager:
    @staticmethod
    def initialize_session(session, start_question_set_id=None):
        session.clear() # Ensure fresh session
        session['session_id'] = str(uuid.uuid4())
        session['chat_messages'] = [] # Start with no messages, first will be from navigator or welcome
        session['structured_answers'] = {}
        session['active_question_set_id'] = None
        session['active_question_obj'] = None
        session['current_question_path'] = []
        session['current_question_index'] = 0

        welcome_text = "Welcome to QuestionnAIre. I'm a chatbot here to ask some initial questions."
        
        if start_question_set_id:
            first_q_text = question_navigator.start_question_set(session, start_question_set_id)
            if first_q_text:
                # The navigator has set active_question_obj, path, index in session
                # The first AI message will be this question
                SessionManager.add_message(session, "assistant", first_q_text)
            else:
                SessionManager.add_message(session, "assistant", f"{welcome_text} However, I couldn't load the initial questions right now.")
        else:
            # Default welcome if no specific question set is started
            SessionManager.add_message(session, "assistant", f"{welcome_text} How can I help you today?")


    @staticmethod
    def add_message(session, role, content):
        # ... (same as your existing add_message) ...
        message_id = str(uuid.uuid4()) # Included for completeness
        message = {"id": message_id, "role": role, "content": content}
        session.setdefault('chat_messages', []).append(message)
        return message


    @staticmethod
    def get_messages(session):
        return session.get('chat_messages', [])

    @staticmethod
    def cleanup():
        # ... (same as your existing cleanup) ...
        pass # Included for completeness

# -----------------------------------------------------------------------------
# UI COMPONENTS (No major changes needed here from your existing class)
# -----------------------------------------------------------------------------
class UIComponents:
    # ... (Keep your existing UIComponents class methods: get_headers, get_head_components, chat_message, etc.) ...
    # Make sure header() uses llm_service.get_model_name() for display if it shows model name.
    @staticmethod # Included for completeness
    def get_headers(): return (Script(src="..."),) # Placeholder for your actual headers
    @staticmethod
    def get_head_components(model_name): return (Title("QuestionnAIre"),) # Placeholder
    @staticmethod
    def chat_message(message): return Div(P(message["content"]), cls=message["role"]) # Placeholder
    @staticmethod
    def input_field(): return Input(id="user-message-input") # Placeholder
    @staticmethod
    def loading_indicator(): return Div("Loading...", id="loading-indicator") # Placeholder
    @staticmethod
    def submit_button(): return Button("Send") # Placeholder
    @staticmethod
    def header(model_name): return Div(H1(f"Chat (Model: {model_name})")) # Placeholder
    @staticmethod
    def chat_interface(messages, model_name): return Div(UIComponents.header(model_name), *[UIComponents.chat_message(m) for m in messages], Form(UIComponents.input_field(), UIComponents.submit_button(), UIComponents.loading_indicator(), id="chat-form", hx_post="/chat", hx_target="#chat-box", hx_swap="beforeend")) # Placeholder
    @staticmethod
    def clear_input_component(): return Input(id="user-message-input", hx_swap_oob="true", value="") # Placeholder


# -----------------------------------------------------------------------------
# MAIN APPLICATION
# -----------------------------------------------------------------------------
llm_service = LLMService() # Uses DEFAULT_MODEL for interpretation by default
app = FastHTML(hdrs=UIComponents.get_headers()) # Ensure headers are passed
rt = app.route

# Lifespan events for LLM client init (if not handled by LLMService constructor robustly for workers)
# For now, assuming LLMService constructor called globally is sufficient if Uvicorn workers inherit.
# If issues persist with "client not initialized" in workers, add @app.on_event("startup") to call llm_service.initialize_client()

@rt("/")
async def get_chat_ui(session):
    # Start with a specific question set, e.g., "respiratory_assessment_v3"
    # The first question will be the initial message from the assistant.
    SessionManager.initialize_session(session, start_question_set_id="respiratory_assessment_v3")
    
    return (
        *UIComponents.get_head_components(llm_service.get_model_name()),
        UIComponents.chat_interface(session['chat_messages'], llm_service.get_model_name())
    )

@rt("/chat")
async def post_chat_message(user_message: str, session):
    clear_input_component = UIComponents.clear_input_component()
    if not user_message or not user_message.strip():
        return clear_input_component

    # Add user's message to visible chat history
    user_msg_data = SessionManager.add_message(session, "user", user_message)
    
    ai_response_text = ""
    active_set_id = session.get('active_question_set_id')
    active_q_obj = session.get('active_question_obj')

    if active_set_id and active_q_obj:
        print(f"Processing answer for structured question: {active_q_obj['id']} - {active_q_obj['text']}")
        # 1. Interpret the user's answer using LLM
        llm_interpretation = llm_service.interpret_answer(active_q_obj, user_message)
        
        # (Optional: log llm_interpretation for debugging)
        print(f"LLM Interpretation Result: {llm_interpretation}")

        # 2. Get next question or clarification using QuestionNavigator
        next_q_or_clarification_text = question_navigator.get_next_question(session, llm_interpretation)
        
        if next_q_or_clarification_text:
            ai_response_text = next_q_or_clarification_text
        else:
            # Questionnaire finished or branch ended
            ai_response_text = "Thank you for answering these questions. Is there anything else I can help you with today?"
            # Consider transitioning to general chat mode here
            session['active_question_set_id'] = None 
            session['active_question_obj'] = None 
            # Fall through to general chat if we want an LLM response after this "Thank you"
            # For now, let's make this the final message of the structured part.
            # If you want general chat immediately after, the logic needs to call llm_service.general_chat
            # if ai_response_text contains this "Thank you..." message.

    else: # No active question set, so use general LLM chat
        print("No active question set. Using general LLM chat.")
        # Prepare chat history for general LLM
        chat_history_for_llm = SessionManager.get_messages(session) # Already includes latest user message
        ai_response_text = llm_service.general_chat(chat_history_for_llm)

    # Add AI's response to session and create UI component
    ai_msg_data = SessionManager.add_message(session, "assistant", ai_response_text)
    
    user_message_component_html = UIComponents.chat_message(user_msg_data)
    ai_message_component_html = UIComponents.chat_message(ai_msg_data)
    
    return user_message_component_html, ai_message_component_html, clear_input_component

# -----------------------------------------------------------------------------
# APPLICATION ENTRY POINT
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("Starting QuestionnAIre Chatbot...")
    # LLM Service is already initialized globally when the script is loaded.
    # Its initialize_client method handles connection attempt / mock client.
    print(f"LLM Service initialized. Interpretation Model: {llm_service.model_name}, General Chat Model: {llm_service.general_chat_model}")
    print(f"System prompt for general chat: {len(llm_service.get_general_system_prompt())} characters")
    
    SessionManager.cleanup()
    serve(port=5001)