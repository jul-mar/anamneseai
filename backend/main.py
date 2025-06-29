# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
from typing import List, Dict, Any, Union

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from graph import anamnesis_graph, load_config
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig

app = FastAPI()

# Global dictionary to store session data in memory
# Key: session_id (str), Value: session_data (dict)
sessions: Dict[str, Dict[str, Any]] = {}

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

def _serialize_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """Serializes a list of LangChain message objects to a list of dicts."""
    serialized = []
    for msg in messages:
        role = msg.type
        if role == 'human':
            role = 'user'  # Konvertiere 'human' zu 'user' für das Frontend
        serialized.append({"role": role, "content": msg.content})
    return serialized

def _determine_bot_state(messages: List[BaseMessage]) -> str:
    """Bestimmt den Bot-Status basierend auf dem Gesprächsstand."""
    if messages and len(messages) > 0:
        last_message = messages[-1]
        # Wenn die letzte Nachricht vom Bot kommt, warten wir auf eine Benutzerantwort
        return "EXPECTING_USER_ANSWER" if isinstance(last_message, AIMessage) else "PROCESSING"
    else:
        return "INIT"

def get_session(request: Request) -> Dict[str, Any]:
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        return sessions[session_id]
    # Create a new session if one doesn't exist
    new_session_id = str(uuid.uuid4())
    sessions[new_session_id] = {
        "session_id": new_session_id,
        "messages": [],
        "debug_mode_enabled": False, # Standardmäßig deaktiviert
    }
    return sessions[new_session_id]

def save_session(session: dict, response: JSONResponse):
    if "session_id" in session:
        session_id = session["session_id"]
        sessions[session_id] = session
        response.set_cookie(key="session_id", value=session_id, httponly=True)

@app.post("/api/session/start")
async def start_session(request: Request):
    session = get_session(request)
    session_id = session["session_id"]
    
    # Konfiguration für den Graphen-Lauf
    config: RunnableConfig = {"configurable": {"thread_id": session_id}}

    # Wenn die Session neu ist (keine Nachrichten), starte den Graphen
    if not session["messages"]:
        initial_message = HumanMessage(content="Beginne die Anamnese.")
        
        # Lege fest, ob der Graph pausieren soll
        interrupt_before = "*" if session.get('debug_mode_enabled', False) else None

        graph_response = anamnesis_graph.invoke(
            {"messages": [initial_message]}, 
            config=config,
            interrupt_before=interrupt_before
        )
        session["messages"] = graph_response["messages"]

    # Lade Konfiguration, um den Modellnamen zu erhalten
    config_data = load_config()
    model_name = config_data.get("model_name", "N/A")

    response_data = {
        "chat_messages": _serialize_messages(session.get('messages', [])),
        "debug_mode": session.get('debug_mode_enabled', False),
        "model_name": model_name,
        "bot_state": _determine_bot_state(session.get('messages', []))
    }
    response = JSONResponse(content=response_data)
    save_session(session, response)
    return response

@app.post("/api/chat")
async def chat(request: Request):
    session = get_session(request)
    session_id = session["session_id"]
    if not session:
        # This case should technically not be reached due to get_session creating one
        raise HTTPException(status_code=400, detail="Session not started.")

    data = await request.json()
    user_message_content = data.get("message")

    if not user_message_content:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    # Konfiguration für den Graphen-Lauf
    config: RunnableConfig = {"configurable": {"thread_id": session_id}}

    # Füge die neue Benutzernachricht zum Verlauf in der Session hinzu
    session["messages"].append(HumanMessage(content=user_message_content))
    
    # Lege fest, ob der Graph pausieren soll
    interrupt_before = "*" if session.get('debug_mode_enabled', False) else None
    
    # Führe den Graphen aus. Der Graph erhält den gesamten Verlauf.
    graph_response = anamnesis_graph.invoke(
        {"messages": session["messages"]},
        config=config,
        interrupt_before=interrupt_before
    )
    
    # Add AI response to history
    session["messages"] = graph_response["messages"]

    response_data = {
        "chat_messages": _serialize_messages(session.get('messages', [])),
        "bot_state": _determine_bot_state(session.get('messages', []))
    }
    response = JSONResponse(content=response_data)
    save_session(session, response)
    return response

@app.post("/api/session/restart")
async def restart_session(request: Request):
    session = get_session(request)
    session_id = session.get("session_id")
    
    # Clear old session data
    if session_id and session_id in sessions:
        del sessions[session_id]
    
    # Start a new session by creating a new empty session
    # and then letting the start_session logic handle the initialization
    new_session = get_session(request) # This will create a new one
    session_id = new_session["session_id"]
    config: RunnableConfig = {"configurable": {"thread_id": session_id}}
    
    initial_message = HumanMessage(content="Beginne die Anamnese.")
    graph_response = anamnesis_graph.invoke(
        {"messages": [initial_message]},
        config=config
    )
    new_session["messages"] = graph_response["messages"]

    response_data = {
        "chat_messages": _serialize_messages(new_session.get('messages', [])),
        "debug_mode": new_session.get('debug_mode_enabled', False),
        "bot_state": _determine_bot_state(new_session.get('messages', []))
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
    
    response_data = {
        "debug_mode": session.get('debug_mode_enabled'),
        "bot_state": _determine_bot_state(session.get('messages', []))
    }
    response = JSONResponse(content=response_data)
    save_session(session, response)
    return response

@app.post("/api/debug/continue")
async def debug_continue(request: Request):
    session = get_session(request)
    session_id = session["session_id"]
    if not session:
        raise HTTPException(status_code=400, detail="Session not started.")
    
    # Konfiguration, um den Graphen fortzusetzen
    config: RunnableConfig = {"configurable": {"thread_id": session_id}}

    # Trigger the next graph turn by invoking with no new messages
    graph_response = anamnesis_graph.invoke({"messages": []}, config=config)
    session["messages"] = graph_response["messages"]

    response_data = {
        "chat_messages": _serialize_messages(session.get('messages', [])),
        "debug_mode": session.get('debug_mode_enabled'),
        "bot_state": _determine_bot_state(session.get('messages', []))
    }
    response = JSONResponse(content=response_data)
    save_session(session, response)
    return response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 