# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import uuid
from typing import List, Dict, Any, Union, Optional
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from graph import anamnesis_graph, load_config
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from database import MedicalHistoryDatabase
from models import MedicalChatbotConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global database instance
db: Optional[MedicalHistoryDatabase] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup and cleanup on shutdown"""
    global db
    try:
        # Initialize database on startup
        logger.info("Initializing medical history database...")
        config = MedicalChatbotConfig()
        db = MedicalHistoryDatabase(config.database_file)
        logger.info(f"Database initialized successfully at {config.database_file}")
        
        # Test database connection
        test_session_id = db.create_session("startup_test")
        logger.info(f"Database connection test successful - created session {test_session_id}")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Continue without database for fallback compatibility
        yield
    finally:
        # Cleanup on shutdown
        logger.info("Application shutting down...")

app = FastAPI(lifespan=lifespan)

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
            role = 'user'  # Convert 'human' to 'user' for the frontend
        serialized.append({"role": role, "content": msg.content})
    return serialized

def _determine_bot_state(messages: List[BaseMessage]) -> str:
    """Determines the bot status based on the conversation state."""
    if messages and len(messages) > 0:
        last_message = messages[-1]
        # If the last message comes from the bot, we wait for a user response
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
        "debug_mode_enabled": False, # Disabled by default
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
    
    # Configuration for the graph execution
    config: RunnableConfig = {"configurable": {"thread_id": session_id}}

    # If the session is new (no messages), start with welcome message and first question
    if not session["messages"]:
        # Add the welcome message first (same as old version)
        from langchain_core.messages import AIMessage
        welcome_message = AIMessage(content="Welcome to QuestionnAIre. I'm here to ask a few questions about your health before your appointment. Let's start.")
        
        # Add the specific first question
        first_question = AIMessage(content="What is reason for your consultation? Fever or Cough?")
        
        session["messages"] = [welcome_message, first_question]

    # Load configuration to get the model name
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

    # Configuration for the graph execution
    config: RunnableConfig = {"configurable": {"thread_id": session_id}}

    # Add the new user message to the session history
    session["messages"].append(HumanMessage(content=user_message_content))
    
    # Determine whether the graph should pause
    interrupt_before = "*" if session.get('debug_mode_enabled', False) else None
    
    # Execute the graph. The graph receives the entire history.
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
    
    # Add the welcome message first (same as old version)
    from langchain_core.messages import AIMessage
    welcome_message = AIMessage(content="Welcome to QuestionnAIre. I'm here to ask a few questions about your health before your appointment. Let's start.")
    
    # Add the specific first question
    first_question = AIMessage(content="What is reason for your consultation? Fever or Cough?")
    
    new_session["messages"] = [welcome_message, first_question]

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
    
    # Configuration to continue the graph
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