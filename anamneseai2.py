# chat.py
from fasthtml.common import *
import ollama # ollama python client
import uuid # For unique IDs for messages
# import datetime # Not strictly needed for logic, but good to keep if it was used elsewhere
import os # For creating session directory
import shutil # For removing session directory
import json # For parsing LLM responses

# --- Configuration ---
OLLAMA_HOST = "http://localhost:11434" # Default Ollama API endpoint
MODEL_NAME = "gemma3:4b-it-qat" # Main model for generating chat responses if needed
EVALUATION_MODEL_NAME = "gemma3:2b-it-qat" # Potentially a faster/smaller model for structured evaluation

# --- Predefined Questions and Criteria ---
PREDEFINED_QUESTIONS = [
    {
        "id": "q1_schmerzen",
        "question_text": "Guten Tag! Um Ihre Situation besser einschätzen zu können, beginnen wir mit einigen Fragen. Haben Sie aktuell Schmerzen?",
        "criteria": [
            "Lokalisation der Schmerzen",
            "Zeitpunkt des ersten Auftretens (seit wann)",
            "Dauer und Art der Schmerzen (z.B. dauerhaft, kolikartig, einschießend)",
            "Stärke der Schmerzen (z.B. auf einer Skala von 1-10)",
            "Qualität der Schmerzen (z.B. brennend, stechend, drückend)"
        ],
        "max_follow_ups": 3 # Max follow-up attempts for this question
    },
    {
        "id": "q2_rauchen",
        "question_text": "Vielen Dank. Nun zur nächsten Frage: Rauchen Sie?",
        "criteria": [
            "Menge pro Tag (z.B. Anzahl Zigaretten, Zigarren, Pfeifen)",
            "Zeitpunkt des Rauchbeginns (seit wann rauchen Sie)",
            "Gesamtdauer des Rauchens in Jahren (falls nicht schon aus 'seit wann' klar)"
        ],
        "max_follow_ups": 2
    },
    {
        "id": "q3_allergien",
        "question_text": "Sind bei Ihnen Allergien oder Unverträglichkeiten bekannt?",
        "criteria": [
            "Nennung von spezifischen Allergenen oder Unverträglichkeiten (oder explizite Verneinung)",
            "Art der Reaktion (falls Allergien/Unverträglichkeiten genannt wurden)"
        ],
        "max_follow_ups": 2
    },
    # --- Add more predefined questions here ---
]

# --- System Prompts for LLM Tasks ---
# This general system prompt can be kept for context if desired, but the task-specific ones below are more critical.
SYSTEM_PROMPT_GENERAL = """Sie sind AnamneseAI, ein medizinischer Assistent, der Patienteninformationen sammelt.
Ihre Hauptaufgabe ist es, die Antworten des Patienten zu evaluieren und gezielte Nachfragen zu stellen,
bis alle für eine Frage definierten Kriterien erfüllt sind.
Seien Sie professionell, empathisch und präzise. Stellen Sie keine Diagnosen.
"""

SYSTEM_PROMPT_EVALUATE_CRITERIA = """
Ihre Aufgabe ist es, die Antwort eines Patienten auf eine spezifische medizinische Frage sorgfältig zu bewerten.
Prüfen Sie, welche der vorgegebenen Kriterien durch die Antwort des Patienten, im Kontext des bisherigen Gesprächs zu dieser Frage, abgedeckt sind.

Aktuelle Frage an den Patienten war: "{current_question_text}"

Die Kriterien für eine vollständige Antwort auf diese Frage sind:
{criteria_list_string}

Bisheriger relevanter Chatverlauf zu DIESER FRAGE (die letzte Nachricht ist die aktuellste Antwort des Patienten):
{chat_history_for_current_question}

Letzte Antwort des Patienten: "{patient_answer}"

Bitte analysieren Sie die letzte Antwort des Patienten im Kontext des Chatverlaufs zu dieser Frage.
Geben Sie Ihre Analyse ausschließlich im folgenden JSON-Format zurück:
{{
  "erfuellte_kriterien": ["Name des Kriteriums 1", "Name des Kriteriums 2", ...],
  "offene_kriterien": ["Name des Kriteriums X", "Name des Kriteriums Y", ...],
  "bewertung_gedanke": "Kurze Begründung Ihrer Entscheidung und welche Informationen genau fehlen oder bereits vorhanden sind."
}}
- Listen Sie unter "erfuellte_kriterien" exakt die Bezeichnungen der Kriterien auf, die durch die Antwort und den bisherigen Verlauf ZU DIESER FRAGE klar und eindeutig abgedeckt sind.
- Listen Sie unter "offene_kriterien" exakt die Bezeichnungen der Kriterien auf, die noch nicht oder nicht ausreichend beantwortet wurden.
- Wenn alle Kriterien erfüllt sind, muss "offene_kriterien" eine leere Liste sein ([]).
- Wenn die Antwort des Patienten eine klare Verneinung der Frage ist (z.B. "Nein, ich habe keine Schmerzen"), und dies eine valide Antwort ist, können alle Kriterien als erfüllt betrachtet werden, wenn die Frage dies zulässt (z.B. bei "Haben Sie Schmerzen?" wäre "Nein" ausreichend). In solch einem Fall können "erfuellte_kriterien" alle Kriterien beinhalten oder leer sein, aber "offene_kriterien" muss leer sein. Geben Sie dies im "bewertung_gedanke" an.
Stellen Sie sicher, dass das JSON valide ist.
"""

SYSTEM_PROMPT_ASK_FOLLOW_UP = """
Sie sind ein medizinischer Assistent. Die vorherige Antwort des Patienten auf die Frage "{current_question_text}" war noch nicht vollständig.
Folgende spezifische Informationen fehlen noch, basierend auf diesen offenen Kriterien:
{unmet_criteria_list_string}

Bisheriger relevanter Chatverlauf zu DIESER FRAGE (die letzte Nachricht ist die aktuellste Antwort des Patienten):
{chat_history_for_current_question}

Letzte Antwort des Patienten war: "{patient_answer}"

Formulieren Sie eine höfliche, präzise und kurze Nachfrage an den Patienten, um die noch fehlenden Informationen zu den oben genannten offenen Kriterien für die Frage "{current_question_text}" zu erhalten.
- Fragen Sie NUR nach den Informationen für die offenen Kriterien.
- Wiederholen Sie nicht Informationen, die der Patient bereits gegeben hat.
- Stellen Sie die Frage so, dass sie den Patienten ermutigt, die spezifischen fehlenden Details zu liefern.
- Stellen Sie nur eine konkrete Frage auf einmal, auch wenn mehrere Kriterien offen sind. Konzentrieren Sie sich auf das Wichtigste oder fassen Sie logisch zusammen.
- Beginnen Sie nicht mit Phrasen wie "Entschuldigung, aber..." oder "Ich habe noch eine Frage...". Kommen Sie direkt zur Sache, aber bleiben Sie freundlich.
Beispiel: "Könnten Sie bitte noch genauer beschreiben, wo die Schmerzen auftreten und seit wann Sie diese haben?"
Ihre Antwort soll direkt die Nachfrage an den Patienten sein. KEIN JSON.
"""

# --- Application Setup ---
hdrs = (
    Script(src="https://cdn.tailwindcss.com"),
    Script(src="https://unpkg.com/htmx.org@1.9.10"),
    Script(src="https://unpkg.com/htmx.org@1.9.10/dist/ext/loading-states.js"),
    Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.10.1/dist/full.min.css"),
    Script("""
    tailwind.config = {
      theme: {
        extend: {
          colors: { 'medical-blue': '#0077b6', 'medical-blue-light': '#90e0ef', 'medical-blue-dark': '#03045e' }
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
app = FastHTML(hdrs=hdrs)
rt = app.route

# --- Ollama Client Setup ---
client = None
ACTUAL_MODEL_NAME_USED = MODEL_NAME
ACTUAL_EVALUATION_MODEL_USED = EVALUATION_MODEL_NAME

class MockOllamaClient:
    def list(self): return {'models': []}
    def chat(self, model, messages):
        print(f"\n--- Using Mock Ollama Client (Model: {model}) ---")
        print("Reason: Ollama connection failed or model not found.")
        # Simulate evaluation response
        if "erfuellte_kriterien" in messages[-1]['content']: # Crude check if it's an eval prompt
            return {'message': {'content': json.dumps({
                "erfuellte_kriterien": [],
                "offene_kriterien": ["Simuliertes offenes Kriterium vom Mock"],
                "bewertung_gedanke": "Dies ist eine Mock-Bewertung."
            })}}
        return {'message': {'content': '*(Mock-Antwort: Konnte nicht mit Ollama verbinden. Bitte prüfen Sie die Verbindung und das Modell.)*'}}

try:
    print(f"Attempting to connect to Ollama at {OLLAMA_HOST}")
    client = ollama.Client(host=OLLAMA_HOST)
    models_available = [m.get('name') for m in client.list().get('models', [])]
    print(f"Available models: {models_available}")

    if MODEL_NAME not in models_available:
        print(f"Warning: Main model {MODEL_NAME} not found. Using fallback or mock.")
    ACTUAL_MODEL_NAME_USED = MODEL_NAME

    if EVALUATION_MODEL_NAME not in models_available:
        print(f"Warning: Evaluation model {EVALUATION_MODEL_NAME} not found. Will use main model {MODEL_NAME} for evaluation instead.")
        ACTUAL_EVALUATION_MODEL_USED = MODEL_NAME
    else:
        ACTUAL_EVALUATION_MODEL_USED = EVALUATION_MODEL_NAME
    
    print(f"Successfully connected to Ollama. Using main model: {ACTUAL_MODEL_NAME_USED}, eval model: {ACTUAL_EVALUATION_MODEL_USED}")

except Exception as e:
    print(f"Error connecting to Ollama: {e}. Starting with mock client.")
    client = MockOllamaClient()
    ACTUAL_MODEL_NAME_USED = MODEL_NAME # Keep configured names for display
    ACTUAL_EVALUATION_MODEL_USED = EVALUATION_MODEL_NAME


# --- Components ---
def ChatMessage(message: dict):
    is_user = message.get("role") == "user"
    chat_alignment = "chat-end" if is_user else "chat-start"
    bubble_color = "bg-white text-gray-800" if is_user else "bg-medical-blue text-white"
    border_style = "border-l-4 border-medical-blue" if is_user else ""
    if message.get("role") == "error":
        bubble_color = "bg-red-100 text-red-800"
        border_style = "border-l-4 border-red-500"
    
    message_content = message.get("content", "")
    avatar_initial = "P" if is_user else "A"
    avatar_bg = "bg-medical-blue-dark text-white" if is_user else "bg-white text-medical-blue-dark border border-medical-blue"
    avatar = Div(
        Div(Span(avatar_initial, cls="inline-flex items-center justify-center w-full h-full"), 
            cls=f"w-8 h-8 rounded-full {avatar_bg} flex items-center justify-center text-sm font-semibold shadow-sm"),
        cls="chat-image avatar"
    )
    role_label = "Patient" if is_user else "AnamneseAI"

    return Div(
        avatar,
        Div(role_label, cls="chat-header text-xs font-medium mb-1 text-gray-600"),
        Div(P(message_content), cls=f"chat-bubble shadow-sm {bubble_color} {border_style} break-words prose prose-sm sm:prose-base rounded-lg px-4 py-3"),
        cls=f"chat {chat_alignment}", id=f"message-{message.get('id', uuid.uuid4())}"
    )

def ChatInterface(messages: list = None):
    chat_messages_components = [ChatMessage(msg) for msg in messages] if messages else []
    
    chat_box = Div(*chat_messages_components, id="chat-box",
        cls="p-4 space-y-6 overflow-y-auto h-[calc(100vh-220px)] bg-white rounded-lg shadow-md border border-gray-200")

    user_input = Input(id="user-message-input", type="text", name="user_message",
        placeholder="Ihre Antwort...",
        cls="input bg-white border border-gray-300 focus:border-medical-blue focus:ring-2 focus:ring-medical-blue-light w-full flex-grow mr-2 rounded-lg",
        autofocus=True)
    submit_button = Button("Senden", type="submit",
        cls="bg-medical-blue hover:bg-medical-blue-dark text-white font-medium py-2 px-6 rounded-lg transition-colors duration-200")
    loading_indicator = Div(
        Div(_innerHTML="""<svg class="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>""",
            cls="inline-block"),
        Span("Verarbeite...", cls="text-sm font-medium"),
        id="loading-indicator", cls="htmx-indicator flex items-center text-medical-blue ml-2",
        style="opacity: 0; transition: opacity 200ms ease-in;")

    chat_form = Form(user_input, submit_button, loading_indicator, hx_post="/chat", hx_target="#chat-box",
        hx_swap="beforeend", hx_indicator="#loading-indicator", hx_ext="loading-states",
        data_loading_delay="100", data_loading_target="#loading-indicator", data_loading_class_remove="opacity-0",
        # Ensure chat scrolls to bottom after new messages
        hx_on_htmx_after_on_load="htmx.find('#chat-box').scrollTop = htmx.find('#chat-box').scrollHeight",
        cls="p-4 flex items-center bg-gray-50 rounded-lg shadow-sm mt-4 sticky bottom-0 border border-gray-200")
    
    header = Div(
        Div(
            Div(_innerHTML="""<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-medical-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>""", cls="mr-3"),
            Div(H1("AnamneseAI", cls="text-2xl font-bold text-medical-blue-dark"), P("Patientenbefragung", cls="text-sm text-gray-600"), cls="flex flex-col"),
            cls="flex items-center mb-2"
        ),
        Div(cls="w-full h-px bg-gray-200 mb-4"),
        Div(
            Div(_innerHTML="""<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>""", cls="text-medical-blue"),
            Span(f"Modell: {ACTUAL_MODEL_NAME_USED} (Eval: {ACTUAL_EVALUATION_MODEL_USED})", cls="text-xs text-gray-600"),
            cls="flex items-center justify-end mb-4"
        ),
        cls="bg-white rounded-lg shadow-sm p-4 mb-4 border border-gray-200"
    )
    return Div(header, chat_box, chat_form, cls="container mx-auto max-w-3xl p-4 flex flex-col h-screen font-sans bg-gray-50")

# --- Helper Functions ---
def get_initial_criteria_status(question_index):
    if 0 <= question_index < len(PREDEFINED_QUESTIONS):
        return {criterion: False for criterion in PREDEFINED_QUESTIONS[question_index]["criteria"]}
    return {}

def get_chat_history_for_current_question(session_messages: list, current_question_id: str):
    """Extracts chat history relevant to the current predefined question."""
    relevant_messages = []
    # Find the point where the current question was first asked
    # This is a simplified heuristic; might need refinement if questions can be re-asked non-linearly
    # For now, assume linear progression and messages after current question was asked are relevant
    
    # Find the last time the current question was asked by the assistant
    last_q_ask_index = -1
    for i in range(len(session_messages) -1, -1, -1):
        msg = session_messages[i]
        # This check is heuristic. It's better if the AI message for a predefined question has a specific marker.
        # For now, we check if the content matches the question_text or if it's an assistant message
        # potentially related to the current question.
        # A more robust way would be to store current_question_id with each assistant message.
        if msg.get("role") == "assistant" and msg.get("question_id") == current_question_id:
             last_q_ask_index = i
             break
    
    if last_q_ask_index != -1:
        relevant_messages = session_messages[last_q_ask_index:]
    else: # If not found (e.g. first turn for the question), take last few messages or all
        relevant_messages = session_messages

    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in relevant_messages])
    return history_str


# --- Routes ---
@rt("/")
async def get_chat_ui(session):
    """Serves the main chat page, loading history from session or starting new."""
    session.clear() # Start fresh for each visit for this example's structure

    session['session_id'] = str(uuid.uuid4())
    session['current_question_index'] = 0
    session['chat_messages'] = []
    
    if PREDEFINED_QUESTIONS:
        first_question = PREDEFINED_QUESTIONS[0]
        session['current_question_id'] = first_question['id']
        session['current_criteria_status'] = get_initial_criteria_status(0)
        session['follow_up_attempts'] = 0

        initial_ai_msg = {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": first_question['question_text'],
            "question_id": first_question['id'] # Mark the question ID
        }
        session['chat_messages'].append(initial_ai_msg)
    else:
        # Fallback if no predefined questions
        session['chat_messages'].append({
            "id": "welcome-msg", "role": "assistant",
            "content": "Willkommen! Es sind aktuell keine Fragen konfiguriert."
        })

    return (
        Title("AnamneseAI - Patientenbefragung"),
        Link(rel="icon", href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚕️</text></svg>"),
        Meta(name="description", content="AI Assistent für Anamneseerhebung"),
        Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
        Style("""
            body { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
            ::-webkit-scrollbar { width: 8px; height: 8px; }
            ::-webkit-scrollbar-track { background: #f1f5f9; }
            ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
            #loading-indicator { opacity: 0; transition: opacity 200ms ease-in; }
            #loading-indicator.processing { opacity: 1 !important; }
            .htmx-request .htmx-indicator { opacity: 1 !important; }
        """),
        ChatInterface(session['chat_messages'])
    )

@rt("/chat")
async def post_chat_message(user_message: str, session):
    clear_input_component = Input(id="user-message-input", name="user_message", placeholder="Ihre Antwort...",
        cls="input bg-white border border-gray-300 focus:border-medical-blue focus:ring-2 focus:ring-medical-blue-light w-full flex-grow mr-2 rounded-lg",
        hx_swap_oob="true", value="", autofocus=True)

    if not user_message or not user_message.strip():
        return clear_input_component

    session_chat_messages = session.get('chat_messages', [])
    user_msg_id = str(uuid.uuid4())
    user_msg_data = {"id": user_msg_id, "role": "user", "content": user_message}
    session_chat_messages.append(user_msg_data)
    user_message_component = ChatMessage(user_msg_data)

    current_q_idx = session.get('current_question_index', 0)
    ai_response_content = "Ein Fehler ist aufgetreten." # Default error message
    ai_message_id = str(uuid.uuid4())
    current_q_id_for_ai_msg = session.get('current_question_id', PREDEFINED_QUESTIONS[current_q_idx]['id'] if PREDEFINED_QUESTIONS else None)


    if current_q_idx >= len(PREDEFINED_QUESTIONS):
        ai_response_content = "Vielen Dank für Ihre Antworten. Die Befragung ist abgeschlossen."
        # No more questions, just return
        ai_msg_data = {"id": ai_message_id, "role": "assistant", "content": ai_response_content, "question_id": "completed"}
        session_chat_messages.append(ai_msg_data)
        session['chat_messages'] = session_chat_messages
        return user_message_component, ChatMessage(ai_msg_data), clear_input_component

    current_question_data = PREDEFINED_QUESTIONS[current_q_idx]
    current_criteria = current_question_data["criteria"]
    current_criteria_status = session.get('current_criteria_status', get_initial_criteria_status(current_q_idx))
    
    # --- LLM Evaluation Call ---
    # Prepare context for evaluation (history relevant to current question)
    history_for_eval = get_chat_history_for_current_question(session_chat_messages, current_question_data['id'])
    
    # Construct criteria list string
    criteria_list_str = "\n".join([f"- {c}" for c in current_criteria])

    evaluation_prompt = SYSTEM_PROMPT_EVALUATE_CRITERIA.format(
        current_question_text=current_question_data["question_text"],
        criteria_list_string=criteria_list_str,
        chat_history_for_current_question=history_for_eval,
        patient_answer=user_message
    )
    
    llm_eval_messages = [
        # You might not need SYSTEM_PROMPT_GENERAL if EVALUATE_CRITERIA is comprehensive enough
        # {"role": "system", "content": SYSTEM_PROMPT_GENERAL},
        {"role": "system", "content": evaluation_prompt} # The detailed prompt is the main message
    ]

    print(f"\n--- Sending to EVALUATION LLM ({ACTUAL_EVALUATION_MODEL_USED}) ---")
    # print(f"Evaluation Prompt Content:\n{evaluation_prompt}")

    try:
        response = client.chat(model=ACTUAL_EVALUATION_MODEL_USED, messages=llm_eval_messages)
        llm_eval_raw_content = response.get('message', {}).get('content', '{}')
        print(f"LLM Eval Raw Response: {llm_eval_raw_content}")
        
        # Attempt to find JSON within the response if it's not pure JSON
        # Basic extraction: look for { ... }
        json_start_index = llm_eval_raw_content.find('{')
        json_end_index = llm_eval_raw_content.rfind('}') + 1
        if json_start_index != -1 and json_end_index != -1 and json_end_index > json_start_index:
            json_str = llm_eval_raw_content[json_start_index:json_end_index]
            evaluation_result = json.loads(json_str)
        else:
            evaluation_result = {"erfuellte_kriterien": [], "offene_kriterien": list(current_criteria), "bewertung_gedanke": "Konnte JSON nicht extrahieren."}
            print("Warning: Could not extract JSON from LLM evaluation response. Assuming all criteria open.")

    except json.JSONDecodeError as e:
        print(f"JSON Decode Error from LLM eval: {e}")
        print(f"Problematic LLM eval raw content: {llm_eval_raw_content}")
        evaluation_result = {"erfuellte_kriterien": [], "offene_kriterien": list(current_criteria), "bewertung_gedanke": "Fehler beim Parsen der LLM-Bewertung."}
    except Exception as e:
        print(f"Error in LLM evaluation call: {e}")
        evaluation_result = {"erfuellte_kriterien": [], "offene_kriterien": list(current_criteria), "bewertung_gedanke": "Allgemeiner Fehler bei LLM-Bewertung."}

    erfuellte_kriterien_namen = evaluation_result.get("erfuellte_kriterien", [])
    offene_kriterien_namen = evaluation_result.get("offene_kriterien", list(current_criteria)) # Default to all open if key missing
    
    # Update current_criteria_status based on names
    for crit_name in current_criteria:
        if crit_name in erfuellte_kriterien_namen:
            current_criteria_status[crit_name] = True
        elif crit_name in offene_kriterien_namen: # Ensure it's explicitly marked as open
             current_criteria_status[crit_name] = False
        # If a criterion is not mentioned in either, its status remains unchanged or defaults to False if new.

    all_criteria_met = all(current_criteria_status.get(c, False) for c in current_criteria)
    
    # Handle simple "No" answers for questions like "Haben Sie Schmerzen?"
    # This is a heuristic and might need refinement based on specific question types.
    if not all_criteria_met and len(current_criteria) > 0: # Only if criteria exist
        normalized_user_message = user_message.strip().lower()
        # Example: if question asks "Haben Sie Schmerzen?" and user says "Nein" or "Keine"
        if "schmerzen" in current_question_data["question_text"].lower() and \
           (normalized_user_message == "nein" or normalized_user_message == "keine"):
            if evaluation_result.get("bewertung_gedanke", "").lower().startswith("patient verneint"): # LLM confirms negation
                 all_criteria_met = True
                 offene_kriterien_namen = []
                 print("Detected valid negation by patient, considering criteria met.")


    session['current_criteria_status'] = current_criteria_status
    session['follow_up_attempts'] = session.get('follow_up_attempts', 0)

    if all_criteria_met or len(offene_kriterien_namen) == 0:
        print("All criteria met for current question or LLM indicates completion.")
        current_q_idx += 1
        session['current_question_index'] = current_q_idx
        session['follow_up_attempts'] = 0 # Reset for next question

        if current_q_idx < len(PREDEFINED_QUESTIONS):
            next_question_data = PREDEFINED_QUESTIONS[current_q_idx]
            ai_response_content = next_question_data['question_text']
            session['current_question_id'] = next_question_data['id']
            current_q_id_for_ai_msg = next_question_data['id']
            session['current_criteria_status'] = get_initial_criteria_status(current_q_idx)
        else:
            ai_response_content = "Vielen Dank für Ihre Antworten. Die Befragung ist nun abgeschlossen."
            current_q_id_for_ai_msg = "completed"
    else:
        # Criteria not met, ask follow-up
        session['follow_up_attempts'] += 1
        if session['follow_up_attempts'] > current_question_data.get("max_follow_ups", 3):
            print(f"Max follow-up attempts reached for question {current_question_data['id']}. Moving to next question.")
            current_q_idx += 1
            session['current_question_index'] = current_q_idx
            session['follow_up_attempts'] = 0
            if current_q_idx < len(PREDEFINED_QUESTIONS):
                next_question_data = PREDEFINED_QUESTIONS[current_q_idx]
                ai_response_content = f"(Die vorherige Frage konnte nicht vollständig geklärt werden.) {next_question_data['question_text']}"
                session['current_question_id'] = next_question_data['id']
                current_q_id_for_ai_msg = next_question_data['id']
                session['current_criteria_status'] = get_initial_criteria_status(current_q_idx)
            else:
                ai_response_content = "Vielen Dank für Ihre Antworten, auch wenn nicht alle Details geklärt werden konnten. Die Befragung ist nun abgeschlossen."
                current_q_id_for_ai_msg = "completed_with_issues"

        else: # Proceed with follow-up
            unmet_criteria_list_str = "\n".join([f"- {c}" for c in offene_kriterien_namen if not current_criteria_status.get(c,True)]) # Get actual unmet based on status
            if not unmet_criteria_list_str: # Fallback if list is empty but all_criteria_met is false
                unmet_criteria_list_str = "\n".join([f"- {c}" for c in offene_kriterien_namen])


            follow_up_prompt = SYSTEM_PROMPT_ASK_FOLLOW_UP.format(
                current_question_text=current_question_data["question_text"],
                unmet_criteria_list_string=unmet_criteria_list_str,
                chat_history_for_current_question=history_for_eval, # Use same history slice
                patient_answer=user_message
            )
            llm_follow_up_messages = [
                {"role": "system", "content": follow_up_prompt}
            ]
            print(f"\n--- Sending to FOLLOW-UP LLM ({ACTUAL_MODEL_NAME_USED}) ---")
            # print(f"Follow-up Prompt Content:\n{follow_up_prompt}")
            try:
                response = client.chat(model=ACTUAL_MODEL_NAME_USED, messages=llm_follow_up_messages) # Use main model or eval
                ai_response_content = response.get('message', {}).get('content', 'Könnten Sie das bitte genauer erklären?')
            except Exception as e:
                print(f"Error in LLM follow-up call: {e}")
                ai_response_content = "Entschuldigung, es gab einen Fehler. Könnten Sie Ihre vorherige Antwort bitte wiederholen oder umformulieren?"
            current_q_id_for_ai_msg = current_question_data['id'] # Still the same question

    ai_msg_data = {"id": ai_message_id, "role": "assistant", "content": ai_response_content, "question_id": current_q_id_for_ai_msg}
    session_chat_messages.append(ai_msg_data)
    session['chat_messages'] = session_chat_messages
    
    # Scroll chat to bottom
    # htmx.trigger(htmx.find('#chat-box'), 'htmx:afterSettle', {}) # Alternative way to trigger scroll if hx-on doesn't work as expected

    return user_message_component, ChatMessage(ai_msg_data), clear_input_component


# --- Clean up any session data directories ---
def clean_session_data():
    try:
        session_dir = ".sessions"
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            print(f"Removed session data directory: {session_dir}")
    except Exception as e:
        print(f"Error cleaning session data: {e}")

# --- Main ---
if __name__ == "__main__":
    print("Starting FastHTML Ollama Chatbot with structured questions...")
    print(f"Using Ollama host: {OLLAMA_HOST}")
    print(f"Main Model: {ACTUAL_MODEL_NAME_USED}, Evaluation Model: {ACTUAL_EVALUATION_MODEL_USED}")
    
    clean_session_data()
    serve(port=5001)