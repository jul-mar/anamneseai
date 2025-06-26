# app.py
from fasthtml.common import *
import uuid
import os
import shutil

# Import from our refactored modules
import ui_components 
import anamnesis_engine

# --- Application Setup ---
# hdrs are now in ui_components
app = FastHTML(hdrs=ui_components.hdrs)
rt = app.route

# --- Routes ---
@rt("/")
async def get_chat_ui(session):
    """Serves the main chat page, loading history from session or starting new."""
    # session.clear() # Clear session on each visit for this example.
                     # For persistent sessions, manage this differently.
    
    if 'session_id' not in session: # Initialize session only if new
        print("Initializing new session.")
        session['session_id'] = str(uuid.uuid4())
        
        initial_ai_msg_dict, initial_engine_state = anamnesis_engine.initialize_session_state()
        
        session['chat_messages'] = [initial_ai_msg_dict]
        session['engine_state'] = initial_engine_state
    else:
        print(f"Resuming session: {session['session_id']}")
        # Ensure engine_state and chat_messages exist, could be an old session
        if 'engine_state' not in session or 'chat_messages' not in session:
            print("Session data missing, re-initializing.")
            initial_ai_msg_dict, initial_engine_state = anamnesis_engine.initialize_session_state()
            session['chat_messages'] = [initial_ai_msg_dict]
            session['engine_state'] = initial_engine_state


    # Page metadata
    page_title = Title("AnamneseAI - Patientenbefragung")
    favicon = Link(rel="icon", href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚕️</text></svg>")
    meta_desc = Meta(name="description", content="AI Assistent für Anamneseerhebung")
    meta_viewport = Meta(name="viewport", content="width=device-width, initial-scale=1.0")

    # Retrieve model names from the engine module for display
    model_name = anamnesis_engine.ACTUAL_MODEL_NAME_USED
    eval_model_name = anamnesis_engine.ACTUAL_EVALUATION_MODEL_USED
    
    return (
        page_title,
        favicon,
        meta_desc,
        meta_viewport,
        # Style block is now part of hdrs in ui_components
        ui_components.ChatInterface(
            messages=session.get('chat_messages', []),
            actual_model_name=model_name,
            actual_eval_model_name=eval_model_name
        )
    )

@rt("/chat")
async def post_chat_message(user_message: str, session):
    """Handles incoming chat messages, processes them, and returns new messages."""
    clear_input_component = ui_components.InputToClear()

    if not user_message or not user_message.strip():
        return clear_input_component # Only return the component to clear input

    # Retrieve current state from session
    session_chat_messages = session.get('chat_messages', [])
    current_engine_state = session.get('engine_state', {})
    
    if not current_engine_state: # Should not happen if session is initialized correctly
        print("Error: Engine state not found in session. Re-initializing.")
        # Fallback: re-initialize (though this might lose context if it happens mid-conversation)
        initial_ai_msg_dict, initial_engine_state = anamnesis_engine.initialize_session_state()
        session['chat_messages'] = [initial_ai_msg_dict] # Start fresh messages
        session['engine_state'] = initial_engine_state
        current_engine_state = initial_engine_state
        # Optionally, return an error message to the user here
        # For now, we'll just proceed with a reset state.

    # Add user message to chat history
    user_msg_id = str(uuid.uuid4())
    user_msg_data = {"id": user_msg_id, "role": "user", "content": user_message}
    session_chat_messages.append(user_msg_data)
    user_message_component = ui_components.ChatMessage(user_msg_data)

    # Process user answer using the engine
    ai_response_content, updated_engine_state, ai_question_id = \
        anamnesis_engine.process_user_answer(
            engine_state=current_engine_state,
            user_message_content=user_message,
            all_session_messages=session_chat_messages # Pass the full history including the latest user message
        )

    # Update session with new state from the engine
    session['engine_state'] = updated_engine_state

    # Add AI response to chat history
    ai_message_id = str(uuid.uuid4())
    ai_msg_data = {
        "id": ai_message_id, 
        "role": "assistant", 
        "content": ai_response_content,
        "question_id": ai_question_id # Store the question_id with the AI message
    }
    session_chat_messages.append(ai_msg_data)
    ai_message_component = ui_components.ChatMessage(ai_msg_data)

    # Persist updated chat messages in session
    session['chat_messages'] = session_chat_messages
    
    # The hx_on_htmx_after_settle in ChatInterface should handle scrolling
    return user_message_component, ai_message_component, clear_input_component


# --- Clean up any session data directories ---
def clean_session_data():
    """Removes the .sessions directory if it exists."""
    try:
        session_dir = ".sessions" # Default FastHTML session directory
        if os.path.exists(session_dir):
            shutil.rmtree(session_dir)
            print(f"Removed session data directory: {session_dir}")
    except Exception as e:
        print(f"Error cleaning session data: {e}")

# --- Main ---
if __name__ == "__main__":
    print("Starting FastHTML Ollama Chatbot with structured questions (Refactored)...")
    print(f"Using Ollama host: {anamnesis_engine.OLLAMA_HOST}")
    print(f"Main Model: {anamnesis_engine.ACTUAL_MODEL_NAME_USED}, Evaluation Model: {anamnesis_engine.ACTUAL_EVALUATION_MODEL_USED}")
    
    # clean_session_data() # Optional: clean sessions on every start
    # By default, FastHTML uses file-based sessions in .sessions directory.
    # Clearing them means no persistence across server restarts.
    # Comment out if you want sessions to persist.
    
    serve(port=5001)
