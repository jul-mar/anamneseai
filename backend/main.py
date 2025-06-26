# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from backend.core import SessionManager, handle_bot_turn, _trigger_initial_bot_action, question_service

app = FastAPI()

# Global dictionary to store session data in memory
# Key: session_id (str), Value: session_data (dict)
sessions = {}

# CORS (Cross-Origin Resource Sharing)
# Allow requests from our frontend development server
origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

def get_session(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        return sessions[session_id]
    return {}

def save_session(session: dict, response: JSONResponse):
    if "session_id" in session:
        session_id = session["session_id"]
        sessions[session_id] = session
        response.set_cookie(key="session_id", value=session_id, httponly=True)

@app.post("/api/session/start")
async def start_session(request: Request):
    session = get_session(request)
    SessionManager.initialize_session(session)
    await _trigger_initial_bot_action(session)
    
    # In non-debug mode, the bot should immediately ask the first question
    if not session.get('debug_mode_enabled', False):
        await handle_bot_turn(session)

    response_data = {
        "chat_messages": session.get('chat_messages', []),
        "bot_state": session.get('bot_state'),
        "debug_mode": session.get('debug_mode_enabled')
    }
    response = JSONResponse(content=response_data)
    save_session(session, response)
    return response

@app.post("/api/chat")
async def chat(request: Request):
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=400, detail="Session not started.")

    data = await request.json()
    user_message = data.get("message")

    if not user_message:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    # Add user message to chat history
    SessionManager.add_message_to_display_chat(session, 'user', user_message)
    
    # Let the bot handle the turn
    await handle_bot_turn(session, user_message_content=user_message)

    response_data = {
        "chat_messages": session.get('chat_messages', []),
        "bot_state": session.get('bot_state'),
    }
    response = JSONResponse(content=response_data)
    save_session(session, response)
    return response

@app.post("/api/session/restart")
async def restart_session(request: Request):
    session = get_session(request)
    session_id = session.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]
    
    # Start a new session
    new_session = {}
    SessionManager.initialize_session(new_session)
    await _trigger_initial_bot_action(new_session)
    if not new_session.get('debug_mode_enabled', False):
        await handle_bot_turn(new_session)

    response_data = {
        "chat_messages": new_session.get('chat_messages', []),
        "bot_state": new_session.get('bot_state'),
        "debug_mode": new_session.get('debug_mode_enabled')
    }
    response = JSONResponse(content=response_data)
    save_session(new_session, response)
    return response

@app.post("/api/debug/toggle")
async def toggle_debug(request: Request):
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=400, detail="Session not started.")
    
    session['debug_mode_enabled'] = not session.get('debug_mode_enabled', False)
    
    # If debug mode was just turned OFF, and the bot is in a waiting state, proceed
    if not session['debug_mode_enabled']:
        bot_state = session.get('bot_state')
        if bot_state in ["WAITING_TO_ASK_PREDEFINED", "EVALUATING_ANSWER", "GENERATING_SUMMARY"]:
            await handle_bot_turn(session)

    response_data = {
        "chat_messages": session.get('chat_messages', []),
        "bot_state": session.get('bot_state'),
        "debug_mode": session.get('debug_mode_enabled')
    }
    response = JSONResponse(content=response_data)
    save_session(session, response)
    return response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 