# backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import uuid
from typing import List, Dict, Any, Union, Optional
import logging
import sqlite3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from graph import build_medical_graph
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from database import MedicalHistoryDatabase
from models import MedicalChatbotConfig, MedicalChatState
from question_manager import QuestionManager

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Set default level to WARNING to hide INFO logs
# Create a specific logger for LLM interactions
llm_logger = logging.getLogger("llm_interactions")
llm_logger.setLevel(logging.INFO)

# Configure a handler for the LLM logger to ensure its messages are visible
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
llm_logger.addHandler(handler)
llm_logger.propagate = False # Prevent llm_interactions from propagating to the root logger

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Keep main app logger at INFO

# Global database and component instances
db: Optional[MedicalHistoryDatabase] = None
question_manager: Optional[QuestionManager] = None
medical_graph = None
current_config: Optional[MedicalChatbotConfig] = None

def generate_session_id() -> str:
    """Generate a unique session identifier"""
    return str(uuid.uuid4())

def get_session_from_request(request: Request) -> Optional[str]:
    """Extract session ID from request cookies"""
    return request.cookies.get("session_id")

def validate_session(session_id: Optional[str]) -> bool:
    """Validate if a session ID exists and is active"""
    if not session_id:
        return False
    return session_id in sessions

def get_or_create_session_state(session_id: str, user_id: str) -> MedicalChatState:
    """Get existing session state or create a new one"""
    if session_id in sessions:
        return sessions[session_id]
    
    # Create new session state with safe database operation
    db_session_id = safe_create_session(user_id)
    if db_session_id:
        logger.info(f"Created database session {db_session_id} for user {user_id}")
    else:
        logger.warning(f"Failed to create database session for user {user_id}, continuing without persistence")
    
    # Convert questions to dict format for state
    questions_list = []
    if question_manager:
        questions_list = [q.to_dict() for q in question_manager.get_all_questions()]
    
    # Initialize the medical chat state
    state = MedicalChatState(
        user_id=user_id,
        session_id=db_session_id,
        questions=questions_list,
        current_question_index=0,
        is_welcome_phase=True,
        max_retries=3
    )
    
    # Get the first question
    if question_manager:
        first_question = question_manager.get_initial_question()
        if first_question:
            state.current_question = first_question.to_dict()
    
    # Store session state in memory
    sessions[session_id] = state
    return state

def set_session_cookie(response: JSONResponse, session_id: str):
    """Set session cookie on response"""
    response.set_cookie(
        key="session_id", 
        value=session_id, 
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=3600 * 24  # 24 hours
    )

def safe_db_operation(operation_name: str, db_operation, *args, **kwargs):
    """
    Safely execute a database operation with comprehensive error handling.
    
    Args:
        operation_name: Description of the operation for logging
        db_operation: The database function to call
        *args, **kwargs: Arguments to pass to the database function
    
    Returns:
        Result of the operation or None if it failed
    """
    if not db:
        logger.warning(f"Database not available for operation: {operation_name}")
        return None
    
    try:
        result = db_operation(*args, **kwargs)
        logger.debug(f"Database operation '{operation_name}' completed successfully")
        return result
    except sqlite3.Error as e:
        logger.error(f"SQLite error during '{operation_name}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during '{operation_name}': {e}")
        return None

def safe_create_session(user_id: str) -> Optional[int]:
    """Safely create a database session with error handling"""
    if not db:
        logger.warning(f"Database not available for create_session for user {user_id}")
        return None
    return safe_db_operation(
        f"create_session for user {user_id}",
        db.create_session,
        user_id
    )

def safe_save_conversation_message(session_id: int, role: str, message: str) -> bool:
    """Safely save a conversation message with error handling"""
    if not db:
        logger.warning(f"Database not available for save_conversation_message for session {session_id}")
        return False
    result = safe_db_operation(
        f"save_conversation_message for session {session_id}",
        db.save_conversation_message,
        session_id, role, message
    )
    return result is not None

def safe_save_answered_question(session_id: int, question_id: str, question_text: str, 
                               user_response: str, summary: str) -> bool:
    """Safely save an answered question with error handling"""
    if not db:
        logger.warning(f"Database not available for save_answered_question for session {session_id}")
        return False
    result = safe_db_operation(
        f"save_answered_question for session {session_id}",
        db.save_answered_question,
        session_id, question_id, question_text, user_response, summary
    )
    return result is not None

def safe_complete_session(session_id: int) -> bool:
    """Safely mark a session as complete with error handling"""
    if not db:
        logger.warning(f"Database not available for complete_session {session_id}")
        return False
    result = safe_db_operation(
        f"complete_session {session_id}",
        db.complete_session,
        session_id
    )
    return result is not None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and components on startup and cleanup on shutdown"""
    global db, question_manager, medical_graph, current_config
    try:
        # Initialize configuration and components
        logger.info("Initializing medical history system...")
        config = MedicalChatbotConfig()
        current_config = config
        
        # Initialize database
        db = MedicalHistoryDatabase(config.database_file)
        logger.info(f"Database initialized successfully at {config.database_file}")
        
        # Initialize question manager
        question_manager = QuestionManager(config)
        logger.info(f"Question manager initialized with {question_manager.get_total_questions()} questions")
        
        # Initialize medical graph
        medical_graph = build_medical_graph()
        logger.info("Medical conversation graph initialized")
        
        # Test database connection
        test_session_id = db.create_session("startup_test")
        logger.info(f"Database connection test successful - created session {test_session_id}")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        # Continue without database for fallback compatibility
        yield
    finally:
        # Cleanup on shutdown
        logger.info("Application shutting down...")

app = FastAPI(lifespan=lifespan)

# Global dictionary to store session states in memory
# Key: session_id (str), Value: MedicalChatState
sessions: Dict[str, MedicalChatState] = {}

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
        # Convert MedicalChatState to dict for backward compatibility
        state = sessions[session_id]
        return {
            "session_id": session_id,
            "messages": [],  # Will be populated from conversation history
            "debug_mode_enabled": False,
            "state": state
        }
    # Create a new session if one doesn't exist
    new_session_id = str(uuid.uuid4())
    return {
        "session_id": new_session_id,
        "messages": [],
        "debug_mode_enabled": False,
    }

def save_session(session: dict, response: JSONResponse):
    if "session_id" in session:
        session_id = session["session_id"]
        # For backward compatibility, only save if we have a state object
        if "state" in session and isinstance(session["state"], MedicalChatState):
            sessions[session_id] = session["state"]
        response.set_cookie(key="session_id", value=session_id, httponly=True)

@app.post("/api/session/start")
async def start_session(request: Request):
    """
    Starts a new medical history session with database persistence.
    """
    # Generate a unique session identifier
    session_id = generate_session_id()
    user_id = f"user_{session_id[:8]}"  # Simple user ID based on session
    
    try:
        # Get or create session state using helper function
        state = get_or_create_session_state(session_id, user_id)
        
        # Invoke the graph to get the initial welcome message and first question
        if medical_graph is not None:
            config: RunnableConfig = {"configurable": {"thread_id": session_id}}
            result = medical_graph.invoke(state, config=config)
            
            # Update state with graph result
            for key, value in result.items():
                if hasattr(state, key):
                    setattr(state, key, value)
        else:
            # Fallback if graph is not available
            logger.warning("Medical graph not available, using fallback welcome message")
            state.last_bot_message = "Welcome to QuestionnAIre! I am your medical assistant. What is the reason for your consultation? Fever or cough?"
        
        # Save conversation messages to database if available
        if state.session_id:
            welcome_message = state.last_bot_message or "Welcome to QuestionnAIre!"
            if safe_save_conversation_message(state.session_id, "assistant", welcome_message):
                logger.debug(f"Saved welcome message for session {state.session_id}")
            else:
                logger.warning(f"Failed to save welcome message for session {state.session_id}")
        
        # Prepare chat messages for frontend compatibility
        chat_messages = []
        if state.last_bot_message:
            chat_messages.append({
                "role": "assistant",
                "content": state.last_bot_message
            })
        
        # Prepare response with both old and new format fields for backward compatibility
        response_data = {
            # Old frontend-compatible format
            "chat_messages": chat_messages,
            "bot_state": "EXPECTING_USER_ANSWER",
            "debug_mode": False,  # Default debug mode
            "model_name": "gpt-4o-mini",  # From config
            
            # New enhanced format (for future frontend updates)
            "session_id": session_id,
            "message": state.last_bot_message or "Welcome to QuestionnAIre!",
            "question_index": state.current_question_index,
            "total_questions": question_manager.get_total_questions() if question_manager else 0
        }
        
        response = JSONResponse(content=response_data)
        set_session_cookie(response, session_id)
        
        logger.info(f"Started new session {session_id} for user {user_id}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to start session: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize session")

@app.post("/api/chat")
async def chat(request: Request):
    """
    Processes user messages and returns bot responses with database persistence.
    """
    # Get and validate session
    session_id = get_session_from_request(request)
    if not validate_session(session_id):
        raise HTTPException(status_code=400, detail="Session not found. Please start a new session.")

    # Type assertion: session_id is guaranteed to be not None after validation
    assert session_id is not None
    
    # Get the current state
    state = sessions[session_id]
    
    try:
        # Parse the user message
        data = await request.json()
        user_message = data.get("message", "").strip()

        if not user_message:
            raise HTTPException(status_code=422, detail="Message cannot be empty.")

        # Update state with user input
        state.user_input = user_message
        
        # Save user message to database if available
        if db and state.session_id:
            db.save_conversation_message(state.session_id, "user", user_message)
            logger.info(f"Saved user message to database for session {state.session_id}")
        
        # Add user message to conversation history in state
        state.add_conversation_message("user", user_message)
        
        # Process through the medical graph
        if medical_graph is not None:
            config: RunnableConfig = {"configurable": {"thread_id": session_id}}
            result = medical_graph.invoke(state, config=config)
            
            # Update state with graph result
            for key, value in result.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            
            # Clear user input after processing
            state.user_input = ""
        else:
            # Fallback if graph is not available
            logger.warning("Medical graph not available, using fallback response")
            state.last_bot_message = "Sorry, the system is currently unavailable. Please try again later."
        
        # Check if answer was sufficient and save to answered_questions table
        if (state.evaluation_result and 
            state.evaluation_result.get("is_sufficient", False) and 
            db and state.session_id):
            
            # Get the current question details
            current_question = state.current_question
            if current_question:
                try:
                    # Create a simple summary of the answer
                    answer_summary = f"User response: {user_message[:100]}{'...' if len(user_message) > 100 else ''}"
                    if state.evaluation_result.get("score"):
                        answer_summary += f" (Score: {state.evaluation_result.get('score', 0):.2f})"
                    
                    # Save the answered question to database
                    db.save_answered_question(
                        session_id=state.session_id,
                        question_id=current_question.get("id", "unknown"),
                        question_text=current_question.get("question", ""),
                        user_response=user_message,
                        summary=answer_summary
                    )
                    
                    logger.info(f"Saved answered question {current_question.get('id')} for session {state.session_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to save answered question: {e}")
        
        # Get the bot response - check for retry with guidance first
        if (state.evaluation_result and 
            not state.evaluation_result.get("is_sufficient", False) and 
            state.retry_count > 0 and 
            state.evaluation_result.get("guidance")):
            # For insufficient answers with guidance, use the guidance instead of the original question
            guidance = state.evaluation_result.get("guidance")
            bot_message = guidance if isinstance(guidance, str) else "Could you please provide more details?"
        else:
            # Default bot message from graph or fallback
            bot_message = state.last_bot_message or "Sorry, there was a problem. Could you please repeat that?"
        
        # Save bot message to database if available
        if db and state.session_id:
            db.save_conversation_message(state.session_id, "assistant", bot_message)
            logger.info(f"Saved bot message to database for session {state.session_id}")
        
        # Add bot message to conversation history in state
        state.add_conversation_message("assistant", bot_message)
        
        # Update the stored session
        sessions[session_id] = state
        
        # Build chat_messages for frontend compatibility
        chat_messages = []
        for msg in state.conversation_history:
            chat_messages.append({
                "role": msg["role"],
                "content": msg["message"]
            })
        
        # Determine bot state for frontend
        bot_state = "COMPLETE" if state.is_complete else "EXPECTING_USER_ANSWER"
        
        # Prepare response with both old and new format fields for backward compatibility
        response_data = {
            # Old frontend-compatible format
            "chat_messages": chat_messages,
            "bot_state": bot_state,
            
            # New enhanced format (for future frontend updates)
            "message": bot_message,
            "question_index": state.current_question_index,
            "total_questions": len(state.questions),
            "is_complete": state.is_complete,
            "retry_count": state.retry_count,
            "retries_remaining": state.retries_remaining()
        }
        
        # Include evaluation feedback if available
        if state.evaluation_result:
            eval_dict = state.evaluation_result
            response_data["evaluation"] = {
                "is_sufficient": eval_dict.get("is_sufficient", False),
                "score": eval_dict.get("score", 0.0),
                "feedback": eval_dict.get("feedback", ""),
                "guidance": eval_dict.get("guidance", "")
            }
        
        response = JSONResponse(content=response_data)
        set_session_cookie(response, session_id)
        
        logger.info(f"Processed message for session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Chat processing failed for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process message")

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

    # Get the current state from sessions
    if session_id in sessions:
        state = sessions[session_id]
        # Trigger the next graph turn with current state
        if medical_graph is not None:
            graph_response = medical_graph.invoke(state, config=config)
            # Update state with result
            for key, value in graph_response.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            sessions[session_id] = state

    response_data = {
        "chat_messages": _serialize_messages(session.get('messages', [])),
        "debug_mode": session.get('debug_mode_enabled'),
        "bot_state": _determine_bot_state(session.get('messages', []))
    }
    response = JSONResponse(content=response_data)
    save_session(session, response)
    return response

@app.get("/api/session/summary")
async def get_session_summary(request: Request):
    """Generate and return a comprehensive medical summary for the current session"""
    session_id = get_session_from_request(request)
    
    if not session_id or not validate_session(session_id):
        raise HTTPException(status_code=400, detail="Valid session required")
    
    # Get session state
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = sessions[session_id]
    
    # Check if session is complete
    if not state.is_complete:
        raise HTTPException(status_code=400, detail="Session must be completed before generating summary")
    
    try:
        # Import summary generator
        from backend.summary_generator import MedicalSummaryGenerator
        from backend.models import MedicalChatbotConfig
        
        config = MedicalChatbotConfig()
        summary_generator = MedicalSummaryGenerator(config)
        
        # Prepare session data for comprehensive summary
        session_data = {
            "answered_questions": [],
            "conversation_history": state.conversation_history,
            "session_metadata": {
                "session_id": state.session_id,
                "total_questions": len(state.questions),
                "completed_questions": state.current_question_index,
                "user_id": state.user_id
            }
        }
        
        # Add individual question summaries to session data
        for question_index, summary_data in state.question_summaries.items():
            session_data["answered_questions"].append(summary_data)
        
        # Generate comprehensive session summary
        comprehensive_summary = await summary_generator.generate_session_summary(session_data)
        
        # Mark session as completed in database if available
        if db and state.session_id:
            safe_complete_session(state.session_id)
            logger.info(f"Marked session {state.session_id} as completed")
        
        # Prepare response
        response_data = {
            "session_id": state.session_id,
            "user_id": state.user_id,
            "is_complete": state.is_complete,
            "total_questions": len(state.questions),
            "answered_questions_count": len(state.question_summaries),
            "comprehensive_summary": comprehensive_summary,
            "individual_summaries": list(state.question_summaries.values()),
            "session_metadata": session_data["session_metadata"]
        }
        
        response = JSONResponse(content=response_data)
        set_session_cookie(response, session_id)
        
        logger.info(f"Generated comprehensive summary for session {session_id}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to generate session summary for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate session summary")

@app.post("/api/question-set/switch")
async def switch_question_set(request: Request):
    """Switch between different question sets (medical, smoking)"""
    global question_manager, medical_graph, current_config
    
    try:
        data = await request.json()
        question_set = data.get("question_set", "medical")
        
        # Validate question set
        valid_sets = ["medical", "smoking"]
        if question_set not in valid_sets:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid question set. Valid options: {valid_sets}"
            )
        
        # Create new config with selected question set
        from backend.models import MedicalChatbotConfig
        config = MedicalChatbotConfig(question_set=question_set)
        current_config = config  # Update global config
        
        # Reload question manager with new question set
        question_manager = QuestionManager(config)
        
        # Rebuild medical graph with new question manager
        medical_graph = build_medical_graph()
        
        logger.info(f"Switched to question set: {question_set}")
        
        response_data = {
            "question_set": question_set,
            "total_questions": question_manager.get_total_questions(),
            "questions_file": config.get_questions_file(),
            "message": f"Successfully switched to {question_set} question set"
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Failed to switch question set: {e}")
        raise HTTPException(status_code=500, detail="Failed to switch question set")

@app.get("/api/question-set/current")
async def get_current_question_set():
    """Get information about the current question set"""
    try:
        # Use global config or create default
        global current_config
        from backend.models import MedicalChatbotConfig
        config = current_config or MedicalChatbotConfig()
        
        response_data = {
            "question_set": config.question_set,
            "total_questions": question_manager.get_total_questions() if question_manager else 0,
            "questions_file": config.get_questions_file(),
            "available_sets": ["medical", "smoking"]
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Failed to get current question set: {e}")
        raise HTTPException(status_code=500, detail="Failed to get question set information")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 