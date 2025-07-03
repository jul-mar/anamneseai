import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda

# Configuration
@dataclass
class MedicalChatbotConfig:
    conversation_model: str = "gpt-4-turbo"
    evaluation_model: str = "gpt-3.5-turbo"
    max_retries: int = 3
    questions_file: str = "medical_questions.json"
    database_file: str = "medical_history.db"

# Enhanced State Management
@dataclass
class MedicalChatState:
    user_id: str = ""
    current_question_index: int = 0
    retry_count: int = 0
    questions: List[Dict] = field(default_factory=list)
    current_question: Dict = field(default_factory=dict)
    user_input: str = ""
    last_bot_message: str = ""
    evaluation_result: Dict = field(default_factory=dict)
    conversation_history: List[Dict] = field(default_factory=list)
    is_complete: bool = False

class MedicalHistoryDatabase:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS medical_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                is_complete BOOLEAN DEFAULT FALSE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS answered_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                question_id TEXT NOT NULL,
                question_text TEXT NOT NULL,
                user_response TEXT NOT NULL,
                summary TEXT,
                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES medical_sessions (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES medical_sessions (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_session(self, user_id: str) -> int:
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO medical_sessions (user_id) VALUES (?)', (user_id,))
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id
    
    def save_answered_question(self, session_id: int, question_id: str, 
                             question_text: str, user_response: str, summary: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO answered_questions 
            (session_id, question_id, question_text, user_response, summary)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, question_id, question_text, user_response, summary))
        conn.commit()
        conn.close()
    
    def save_conversation_message(self, session_id: int, role: str, message: str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO conversation_history (session_id, role, message)
            VALUES (?, ?, ?)
        ''', (session_id, role, message))
        conn.commit()
        conn.close()
    
    def complete_session(self, session_id: int):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE medical_sessions 
            SET completed_at = CURRENT_TIMESTAMP, is_complete = TRUE
            WHERE id = ?
        ''', (session_id,))
        conn.commit()
        conn.close()

class MedicalHistoryChatbot:
    def __init__(self, config: MedicalChatbotConfig):
        self.config = config
        self.llm_conversation = ChatOpenAI(model=config.conversation_model, temperature=0.7)
        self.llm_evaluation = ChatOpenAI(model=config.evaluation_model, temperature=0)
        self.database = MedicalHistoryDatabase(config.database_file)
        self.questions = self.load_questions()
        self.memory = ConversationBufferMemory(return_messages=True, memory_key="history")
        self.conversation_chain = ConversationChain(llm=self.llm_conversation, memory=self.memory)
        self.session_id = None
        
    def load_questions(self) -> List[Dict]:
        """Load medical questions from JSON file"""
        try:
            with open(self.config.questions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # Return sample questions if file doesn't exist
            return [
                {
                    "id": "demographics",
                    "question": "Could you please tell me your age and gender?",
                    "criteria": [
                        "Must include age (number)",
                        "Must include gender (male/female/other)"
                    ]
                },
                {
                    "id": "chief_complaint",
                    "question": "What is the main reason for your visit today? Please describe your primary concern or symptom.",
                    "criteria": [
                        "Must describe a specific symptom or concern",
                        "Must be health-related"
                    ]
                },
                {
                    "id": "symptom_duration",
                    "question": "How long have you been experiencing this symptom?",
                    "criteria": [
                        "Must include a time period (days, weeks, months)",
                        "Must be specific (not vague terms like 'recently')"
                    ]
                }
            ]
    
    def start_conversation(self, user_id: str) -> str:
        """Initialize a new medical history session"""
        self.session_id = self.database.create_session(user_id)
        
        state = MedicalChatState(
            user_id=user_id,
            questions=self.questions,
            current_question=self.questions[0] if self.questions else {}
        )
        
        # Build and run the graph
        graph = self.build_graph()
        result = graph.invoke(state)
        
        return result.get("last_bot_message", "")
    
    def process_user_input(self, user_input: str) -> str:
        """Process user input and return bot response"""
        if not self.session_id:
            return "Please start a new conversation first."
        
        # Save user message to database
        self.database.save_conversation_message(self.session_id, "user", user_input)
        
        # Get current state and update with user input
        state = MedicalChatState(
            user_id="current_user",  # You'll need to track this
            current_question_index=0,  # You'll need to track this
            questions=self.questions,
            current_question=self.questions[0] if self.questions else {},
            user_input=user_input
        )
        
        # Process through graph
        graph = self.build_graph()
        result = graph.invoke(state)
        
        # Save bot response to database
        bot_response = result.get("last_bot_message", "")
        self.database.save_conversation_message(self.session_id, "assistant", bot_response)
        
        return bot_response
    
    def build_graph(self) -> StateGraph:
        """Build the conversation graph"""
        
        def ask_question(state: MedicalChatState) -> Dict:
            """Ask the current question"""
            if state.current_question_index >= len(state.questions):
                state.is_complete = True
                if self.session_id:
                    self.database.complete_session(self.session_id)
                return {
                    "last_bot_message": "Thank you! We have completed your medical history intake.",
                    "is_complete": True
                }
            
            question = state.questions[state.current_question_index]
            state.current_question = question
            
            if state.retry_count == 0:
                # First time asking this question
                bot_message = f"Question {state.current_question_index + 1}: {question['question']}"
            else:
                # Retry with guidance
                missing_criteria = state.evaluation_result.get("missing_criteria", [])
                guidance = f"I need a bit more information. Please make sure to include: {', '.join(missing_criteria)}"
                bot_message = f"{guidance}\n\nLet me ask again: {question['question']}"
            
            state.last_bot_message = bot_message
            return {"last_bot_message": bot_message, "current_question": question}
        
        def evaluate_response(state: MedicalChatState) -> Dict:
            """Evaluate if user response meets criteria"""
            user_input = state.user_input
            question = state.current_question
            criteria = question.get("criteria", [])
            
            evaluation_prompt = f"""
            Evaluate if the following user response adequately answers the medical question according to the given criteria.
            
            Question: {question['question']}
            
            Criteria that must be met:
            {chr(10).join(f"- {criterion}" for criterion in criteria)}
            
            User Response: {user_input}
            
            Respond with a JSON object containing:
            - "is_sufficient": true/false
            - "missing_criteria": list of criteria not met (empty if sufficient)
            - "explanation": brief explanation of the evaluation
            """
            
            response = self.llm_evaluation.invoke([
                {"role": "system", "content": "You are a medical intake evaluation assistant. Respond only with valid JSON."},
                {"role": "user", "content": evaluation_prompt}
            ])
            
            try:
                evaluation = json.loads(response.content)
            except json.JSONDecodeError:
                evaluation = {"is_sufficient": False, "missing_criteria": criteria, "explanation": "Could not parse evaluation"}
            
            state.evaluation_result = evaluation
            return {"evaluation_result": evaluation}
        
        def handle_sufficient_response(state: MedicalChatState) -> Dict:
            """Handle when response is sufficient - save and move to next question"""
            # Generate summary
            summary_prompt = f"""
            Create a concise medical summary of the following question and answer:
            
            Question: {state.current_question['question']}
            Patient Response: {state.user_input}
            
            Provide a brief, clinical summary suitable for medical records.
            """
            
            summary_response = self.llm_evaluation.invoke([
                {"role": "system", "content": "You are a medical documentation assistant."},
                {"role": "user", "content": summary_prompt}
            ])
            
            summary = summary_response.content.strip()
            
            # Save to database
            if self.session_id:
                self.database.save_answered_question(
                    self.session_id,
                    state.current_question['id'],
                    state.current_question['question'],
                    state.user_input,
                    summary
                )
            
            # Move to next question
            state.current_question_index += 1
            state.retry_count = 0
            
            # Acknowledge and transition
            if state.current_question_index < len(state.questions):
                bot_message = "Thank you for that information. Let's move on to the next question."
            else:
                bot_message = "Thank you! We have completed your medical history intake."
                state.is_complete = True
                if self.session_id:
                    self.database.complete_session(self.session_id)
            
            state.last_bot_message = bot_message
            return {
                "current_question_index": state.current_question_index,
                "retry_count": 0,
                "last_bot_message": bot_message,
                "is_complete": state.is_complete
            }
        
        def handle_insufficient_response(state: MedicalChatState) -> Dict:
            """Handle when response is insufficient"""
            state.retry_count += 1
            
            if state.retry_count >= self.config.max_retries:
                # Max retries reached, move to next question
                bot_message = "I understand. Let's move on to the next question for now."
                state.current_question_index += 1
                state.retry_count = 0
                state.last_bot_message = bot_message
                return {
                    "current_question_index": state.current_question_index,
                    "retry_count": 0,
                    "last_bot_message": bot_message
                }
            
            # Will retry with guidance in ask_question
            return {"retry_count": state.retry_count}
        
        def route_evaluation(state: MedicalChatState) -> str:
            """Route based on evaluation result"""
            if state.evaluation_result.get("is_sufficient", False):
                return "handle_sufficient"
            else:
                return "handle_insufficient"
        
        def check_completion(state: MedicalChatState) -> str:
            """Check if all questions are completed"""
            if state.is_complete or state.current_question_index >= len(state.questions):
                return END
            else:
                return "ask_question"
        
        # Build the graph
        builder = StateGraph(dict)
        
        # Add nodes
        builder.add_node("ask_question", RunnableLambda(ask_question))
        builder.add_node("evaluate_response", RunnableLambda(evaluate_response))
        builder.add_node("handle_sufficient", RunnableLambda(handle_sufficient_response))
        builder.add_node("handle_insufficient", RunnableLambda(handle_insufficient_response))
        
        # Set entry point
        builder.set_entry_point("ask_question")
        
        # Add edges
        builder.add_edge("ask_question", "evaluate_response")
        builder.add_conditional_edges("evaluate_response", route_evaluation)
        builder.add_conditional_edges("handle_sufficient", check_completion)
        builder.add_conditional_edges("handle_insufficient", check_completion)
        
        return builder.compile()

# Example usage and sample questions JSON
def create_sample_questions_file():
    """Create a sample questions file"""
    sample_questions = [
        {
            "id": "demographics",
            "question": "Could you please tell me your age and gender?",
            "criteria": [
                "Must include age (number)",
                "Must include gender (male/female/other)"
            ]
        },
        {
            "id": "chief_complaint",
            "question": "What is the main reason for your visit today? Please describe your primary concern or symptom.",
            "criteria": [
                "Must describe a specific symptom or concern",
                "Must be health-related"
            ]
        },
        {
            "id": "symptom_duration",
            "question": "How long have you been experiencing this symptom?",
            "criteria": [
                "Must include a time period (days, weeks, months)",
                "Must be specific (not vague terms like 'recently')"
            ]
        },
        {
            "id": "pain_scale",
            "question": "On a scale of 1-10, how would you rate your pain or discomfort level?",
            "criteria": [
                "Must include a number between 1-10",
                "Must relate to pain or discomfort level"
            ]
        },
        {
            "id": "medications",
            "question": "Are you currently taking any medications? If yes, please list them.",
            "criteria": [
                "Must clearly state yes or no",
                "If yes, must list specific medications or state 'none'"
            ]
        },
        {
            "id": "allergies",
            "question": "Do you have any known allergies to medications, foods, or other substances?",
            "criteria": [
                "Must clearly state yes or no",
                "If yes, must specify what allergies"
            ]
        }
    ]
    
    with open("medical_questions.json", "w", encoding="utf-8") as f:
        json.dump(sample_questions, f, indent=2, ensure_ascii=False)

# Initialize and run the chatbot
if __name__ == "__main__":
    # Create sample questions file
    create_sample_questions_file()
    
    # Initialize chatbot
    config = MedicalChatbotConfig()
    chatbot = MedicalHistoryChatbot(config)
    
    # Example usage
    user_id = "user123"
    
    # Start conversation
    first_message = chatbot.start_conversation(user_id)
    print("Bot:", first_message)
    
    # Simulate conversation
    while True:
        user_input = input("You: ")
        if user_input.lower() in ['quit', 'exit', 'bye']:
            break
        
        response = chatbot.process_user_input(user_input)
        print("Bot:", response)
        
        if "completed your medical history" in response:
            break