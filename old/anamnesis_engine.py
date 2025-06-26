# anamnesis_engine.py
import ollama
import uuid
import json
import os # For potential future use, not strictly needed by current engine logic

# --- Configuration ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434") # Allow override via env var
MODEL_NAME = "gemma3:4b-it-qat"
EVALUATION_MODEL_NAME = "gemma3:2b-it-qat"

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
        "max_follow_ups": 3
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
]

# --- System Prompts for LLM Tasks ---
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

# --- Ollama Client Setup ---
client = None
ACTUAL_MODEL_NAME_USED = MODEL_NAME
ACTUAL_EVALUATION_MODEL_USED = EVALUATION_MODEL_NAME

class MockOllamaClient:
    def list(self): return {'models': []}
    def chat(self, model, messages):
        print(f"\n--- Using Mock Ollama Client (Model: {model}) ---")
        print("Reason: Ollama connection failed or model not found.")
        if "erfuellte_kriterien" in messages[-1]['content']: # Crude check for eval prompt
            # Simulate a case where one criterion is still open
            current_q_text_line = next((line for line in messages[-1]['content'].splitlines() if "Aktuelle Frage an den Patienten war:" in line), "")
            current_q_text = current_q_text_line.split(":")[-1].strip().replace('"', '')
            
            # Find the question to get its criteria
            mock_open_criteria = ["Simuliertes offenes Kriterium vom Mock"]
            for q_data in PREDEFINED_QUESTIONS:
                if q_data["question_text"] == current_q_text:
                    if q_data["criteria"]:
                         mock_open_criteria = [q_data["criteria"][0]] # Take the first criterion as open for mock
                    else: # Question has no criteria, so it's fulfilled by any answer
                        mock_open_criteria = []
                    break
            
            return {'message': {'content': json.dumps({
                "erfuellte_kriterien": [],
                "offene_kriterien": mock_open_criteria,
                "bewertung_gedanke": "Dies ist eine Mock-Bewertung. Ein Kriterium ist noch offen."
            })}}
        return {'message': {'content': '*(Mock-Antwort: Konnte nicht mit Ollama verbinden. Bitte nennen Sie weitere Details.)*'}}

try:
    print(f"Attempting to connect to Ollama at {OLLAMA_HOST}")
    client = ollama.Client(host=OLLAMA_HOST)
    models_available = [m.get('name') for m in client.list().get('models', [])]
    print(f"Available models: {models_available}")

    if MODEL_NAME not in models_available:
        print(f"Warning: Main model {MODEL_NAME} not found. Using fallback or mock.")
    ACTUAL_MODEL_NAME_USED = MODEL_NAME # Keep configured name

    if EVALUATION_MODEL_NAME not in models_available:
        print(f"Warning: Evaluation model {EVALUATION_MODEL_NAME} not found. Will use main model {MODEL_NAME} for evaluation instead.")
        ACTUAL_EVALUATION_MODEL_USED = MODEL_NAME
    else:
        ACTUAL_EVALUATION_MODEL_USED = EVALUATION_MODEL_NAME
    
    print(f"Successfully connected to Ollama. Using main model: {ACTUAL_MODEL_NAME_USED}, eval model: {ACTUAL_EVALUATION_MODEL_USED}")

except Exception as e:
    print(f"Error connecting to Ollama: {e}. Starting with mock client.")
    client = MockOllamaClient()
    # ACTUAL_MODEL_NAME_USED and ACTUAL_EVALUATION_MODEL_USED remain as configured for display

# --- Helper Functions ---
def get_initial_criteria_status(question_index: int) -> dict:
    """
    Initializes the criteria status for a given question index.
    Args:
        question_index (int): The index of the predefined question.
    Returns:
        dict: A dictionary with criteria names as keys and False as values.
    """
    if 0 <= question_index < len(PREDEFINED_QUESTIONS):
        return {criterion: False for criterion in PREDEFINED_QUESTIONS[question_index]["criteria"]}
    return {}

def get_chat_history_for_current_question(session_messages: list, current_question_id: str) -> str:
    """
    Extracts chat history relevant to the current predefined question.
    Args:
        session_messages (list): The entire list of chat messages in the session.
        current_question_id (str): The ID of the current question being asked.
    Returns:
        str: A string formatted representation of the relevant chat history.
    """
    relevant_messages = []
    last_q_ask_index = -1
    for i in range(len(session_messages) - 1, -1, -1):
        msg = session_messages[i]
        if msg.get("role") == "assistant" and msg.get("question_id") == current_question_id:
            last_q_ask_index = i
            break
    
    if last_q_ask_index != -1:
        relevant_messages = session_messages[last_q_ask_index:]
    else: # Fallback if the exact question start isn't found (e.g., very first interaction)
        relevant_messages = session_messages 

    history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in relevant_messages])
    return history_str

# --- Core Anamnesis Logic ---
def initialize_session_state() -> tuple[dict, dict]:
    """
    Initializes the state for a new chat session.
    Returns:
        tuple[dict, dict]: 
            - initial_ai_message_dict: The first message from the AI.
            - initial_engine_state_dict: The initial state for the anamnesis engine.
    """
    initial_engine_state = {
        'current_question_index': 0,
        'current_question_id': None,
        'current_criteria_status': {},
        'follow_up_attempts': 0
    }
    initial_ai_message = {
        "id": str(uuid.uuid4()),
        "role": "assistant",
        "content": "Willkommen! Es sind aktuell keine Fragen konfiguriert.",
        "question_id": "welcome_no_questions"
    }

    if PREDEFINED_QUESTIONS:
        first_question = PREDEFINED_QUESTIONS[0]
        initial_engine_state['current_question_id'] = first_question['id']
        initial_engine_state['current_criteria_status'] = get_initial_criteria_status(0)
        
        initial_ai_message["content"] = first_question['question_text']
        initial_ai_message["question_id"] = first_question['id']
        
    return initial_ai_message, initial_engine_state

def process_user_answer(engine_state: dict, user_message_content: str, all_session_messages: list) -> tuple[str, dict, str]:
    """
    Processes the user's answer, evaluates criteria, and determines the next AI response.
    Args:
        engine_state (dict): The current state of the anamnesis engine.
        user_message_content (str): The text of the user's latest message.
        all_session_messages (list): The complete history of chat messages in the session.
    Returns:
        tuple[str, dict, str]:
            - ai_response_content_string: The text for the AI's next message.
            - updated_engine_state_dict: The new state for the anamnesis engine.
            - ai_question_id_string: The question ID associated with the AI's response.
    """
    current_q_idx = engine_state.get('current_question_index', 0)
    current_criteria_status = engine_state.get('current_criteria_status', {})
    follow_up_attempts = engine_state.get('follow_up_attempts', 0)

    ai_response_content = "Ein interner Fehler ist aufgetreten. Bitte versuchen Sie es später erneut."
    ai_question_id = "error"

    if current_q_idx >= len(PREDEFINED_QUESTIONS):
        ai_response_content = "Vielen Dank für Ihre Antworten. Die Befragung ist abgeschlossen."
        ai_question_id = "completed"
        return ai_response_content, engine_state, ai_question_id

    current_question_data = PREDEFINED_QUESTIONS[current_q_idx]
    current_criteria = current_question_data["criteria"]
    ai_question_id = current_question_data['id'] # Default for follow-ups on current question

    # --- LLM Evaluation Call ---
    history_for_eval = get_chat_history_for_current_question(all_session_messages, current_question_data['id'])
    criteria_list_str = "\n".join([f"- {c}" for c in current_criteria])
    evaluation_prompt = SYSTEM_PROMPT_EVALUATE_CRITERIA.format(
        current_question_text=current_question_data["question_text"],
        criteria_list_string=criteria_list_str,
        chat_history_for_current_question=history_for_eval,
        patient_answer=user_message_content
    )
    llm_eval_messages = [{"role": "system", "content": evaluation_prompt}]

    print(f"\n--- Sending to EVALUATION LLM ({ACTUAL_EVALUATION_MODEL_USED}) ---")
    # print(f"Evaluation Prompt Content:\n{evaluation_prompt}") # For debugging
    
    evaluation_result = {"erfuellte_kriterien": [], "offene_kriterien": list(current_criteria), "bewertung_gedanke": "Fehler bei LLM-Bewertung (Default)."}
    try:
        response = client.chat(model=ACTUAL_EVALUATION_MODEL_USED, messages=llm_eval_messages)
        llm_eval_raw_content = response.get('message', {}).get('content', '{}')
        print(f"LLM Eval Raw Response: {llm_eval_raw_content}")
        
        json_start_index = llm_eval_raw_content.find('{')
        json_end_index = llm_eval_raw_content.rfind('}') + 1
        if json_start_index != -1 and json_end_index != -1 and json_end_index > json_start_index:
            json_str = llm_eval_raw_content[json_start_index:json_end_index]
            evaluation_result = json.loads(json_str)
        else:
            print("Warning: Could not extract JSON from LLM evaluation response. Assuming all criteria open.")
            # evaluation_result remains default: all criteria open

    except json.JSONDecodeError as e:
        print(f"JSON Decode Error from LLM eval: {e}. Raw content: {llm_eval_raw_content}")
        # evaluation_result remains default
    except Exception as e:
        print(f"Error in LLM evaluation call: {e}")
        # evaluation_result remains default

    erfuellte_kriterien_namen = evaluation_result.get("erfuellte_kriterien", [])
    offene_kriterien_namen = evaluation_result.get("offene_kriterien", list(current_criteria))

    # Update current_criteria_status based on names from LLM
    # Re-initialize to ensure only explicitly fulfilled criteria are marked True
    current_criteria_status = {crit: False for crit in current_criteria} 
    for crit_name in erfuellte_kriterien_namen:
        if crit_name in current_criteria_status:
            current_criteria_status[crit_name] = True
    
    # Determine if all criteria are met based on the *updated* status
    all_criteria_met = all(current_criteria_status.get(c, False) for c in current_criteria) if current_criteria else True

    # Handle simple "No" answers for questions like "Haben Sie Schmerzen?"
    if not all_criteria_met and current_criteria: # Only if criteria exist and not all met
        normalized_user_message = user_message_content.strip().lower()
        # Example: if question asks "Haben Sie Schmerzen?" and user says "Nein" or "Keine"
        # And LLM confirms negation in its thought process
        if "schmerzen" in current_question_data["question_text"].lower() and \
           (normalized_user_message == "nein" or normalized_user_message == "keine"):
            if "verneint" in evaluation_result.get("bewertung_gedanke", "").lower() or \
               "keine schmerzen" in evaluation_result.get("bewertung_gedanke", "").lower():
                all_criteria_met = True
                offene_kriterien_namen = [] # No open criteria if negation is valid
                print("Detected valid negation by patient for pain, considering criteria met.")
        # Similar logic for "Rauchen Sie?" -> "Nein"
        if "rauchen sie?" in current_question_data["question_text"].lower() and \
           (normalized_user_message == "nein"):
            if "verneint" in evaluation_result.get("bewertung_gedanke", "").lower() or \
               "raucht nicht" in evaluation_result.get("bewertung_gedanke", "").lower():
                all_criteria_met = True
                offene_kriterien_namen = []
                print("Detected valid negation by patient for smoking, considering criteria met.")
        # Similar logic for "Allergien?" -> "Nein"
        if "allergien" in current_question_data["question_text"].lower() and \
           (normalized_user_message == "nein" or "keine bekannt" in normalized_user_message):
             if "verneint" in evaluation_result.get("bewertung_gedanke", "").lower() or \
               "keine allergien" in evaluation_result.get("bewertung_gedanke", "").lower():
                all_criteria_met = True
                offene_kriterien_namen = []
                print("Detected valid negation by patient for allergies, considering criteria met.")


    engine_state['current_criteria_status'] = current_criteria_status
    
    if all_criteria_met or not offene_kriterien_namen: # If LLM says all open criteria are now empty, it's also complete
        print(f"All criteria met for question '{current_question_data['id']}' or LLM indicates completion.")
        current_q_idx += 1
        follow_up_attempts = 0 

        if current_q_idx < len(PREDEFINED_QUESTIONS):
            next_question_data = PREDEFINED_QUESTIONS[current_q_idx]
            ai_response_content = next_question_data['question_text']
            ai_question_id = next_question_data['id']
            engine_state['current_question_id'] = next_question_data['id']
            engine_state['current_criteria_status'] = get_initial_criteria_status(current_q_idx)
        else:
            ai_response_content = "Vielen Dank für Ihre Antworten. Die Befragung ist nun abgeschlossen."
            ai_question_id = "completed"
    else:
        # Criteria not met, ask follow-up
        follow_up_attempts += 1
        if follow_up_attempts > current_question_data.get("max_follow_ups", 3):
            print(f"Max follow-up attempts reached for question {current_question_data['id']}. Moving to next question.")
            current_q_idx += 1
            follow_up_attempts = 0
            if current_q_idx < len(PREDEFINED_QUESTIONS):
                next_question_data = PREDEFINED_QUESTIONS[current_q_idx]
                ai_response_content = f"(Die vorherige Frage '{current_question_data['question_text']}' konnte nicht vollständig geklärt werden.) {next_question_data['question_text']}"
                ai_question_id = next_question_data['id']
                engine_state['current_question_id'] = next_question_data['id']
                engine_state['current_criteria_status'] = get_initial_criteria_status(current_q_idx)
            else:
                ai_response_content = "Vielen Dank für Ihre Antworten, auch wenn nicht alle Details geklärt werden konnten. Die Befragung ist nun abgeschlossen."
                ai_question_id = "completed_with_issues"
        else: # Proceed with follow-up
            # Use offene_kriterien_namen directly from the LLM's JSON output for the follow-up prompt
            unmet_criteria_list_str = "\n".join([f"- {c}" for c in offene_kriterien_namen])
            if not unmet_criteria_list_str: # Should not happen if all_criteria_met is False and offene_kriterien_namen is not empty
                 unmet_criteria_list_str = "fehlende Details" # Fallback

            follow_up_prompt = SYSTEM_PROMPT_ASK_FOLLOW_UP.format(
                current_question_text=current_question_data["question_text"],
                unmet_criteria_list_string=unmet_criteria_list_str,
                chat_history_for_current_question=history_for_eval,
                patient_answer=user_message_content
            )
            llm_follow_up_messages = [{"role": "system", "content": follow_up_prompt}]
            print(f"\n--- Sending to FOLLOW-UP LLM ({ACTUAL_MODEL_NAME_USED}) ---")
            # print(f"Follow-up Prompt Content:\n{follow_up_prompt}") # For debugging
            try:
                response = client.chat(model=ACTUAL_MODEL_NAME_USED, messages=llm_follow_up_messages)
                ai_response_content = response.get('message', {}).get('content', 'Könnten Sie das bitte genauer erklären?')
            except Exception as e:
                print(f"Error in LLM follow-up call: {e}")
                ai_response_content = "Entschuldigung, es gab einen Fehler bei der Verarbeitung Ihrer Antwort. Könnten Sie bitte mehr Details nennen?"
            ai_question_id = current_question_data['id'] # Still the same question

    engine_state['current_question_index'] = current_q_idx
    engine_state['follow_up_attempts'] = follow_up_attempts
    
    return ai_response_content, engine_state, ai_question_id

