from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# Configuration for the medical chatbot system
@dataclass
class MedicalChatbotConfig:
    """Configuration settings for the medical history chatbot"""
    conversation_model: str = "gpt-4o-mini"
    evaluation_model: str = "gpt-4o-mini"
    max_retries: int = 3
    questions_file: str = "backend/questions.json"
    database_file: str = "backend/medical_history.db"

# Enhanced State Management for medical conversations
@dataclass
class MedicalChatState:
    """State management for medical history collection conversations"""
    user_id: str = ""
    session_id: Optional[int] = None
    current_question_index: int = 0
    retry_count: int = 0
    questions: List[Dict] = field(default_factory=list)
    current_question: Dict = field(default_factory=dict)
    user_input: str = ""
    last_bot_message: str = ""
    evaluation_result: Dict = field(default_factory=dict)
    conversation_history: List[Dict] = field(default_factory=list)
    is_complete: bool = False
    is_welcome_phase: bool = True  # True for initial welcome/first question
    
    def get_current_question(self) -> Optional[Dict]:
        """Get the current question object"""
        if 0 <= self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None
    
    def advance_to_next_question(self):
        """Move to the next question and reset retry count"""
        self.current_question_index += 1
        self.retry_count = 0
        self.is_welcome_phase = False
        
        # Update current_question
        current = self.get_current_question()
        if current:
            self.current_question = current
        else:
            self.is_complete = True
    
    def increment_retry(self) -> bool:
        """Increment retry count and return True if max retries not exceeded"""
        self.retry_count += 1
        return self.retry_count <= 3  # Allow up to 3 retries
    
    def reset_retry_count(self):
        """Reset retry count for successful answer"""
        self.retry_count = 0
    
    def add_conversation_message(self, role: str, message: str):
        """Add a message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "message": message,
            "timestamp": None  # Will be set by database
        })

# Data model for question evaluation results
@dataclass
class QuestionEvaluation:
    """Result of evaluating a user's answer against question criteria"""
    is_sufficient: bool = False
    score: float = 0.0
    feedback: str = ""
    missing_criteria: List[str] = field(default_factory=list)
    evaluation_reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "is_sufficient": self.is_sufficient,
            "score": self.score,
            "feedback": self.feedback,
            "missing_criteria": self.missing_criteria,
            "evaluation_reasoning": self.evaluation_reasoning
        }

# Data model for medical questions
@dataclass
class MedicalQuestion:
    """Structure for medical questions with evaluation criteria"""
    id: str
    question: str
    criteria: List[str] = field(default_factory=list)
    category: str = ""
    required: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MedicalQuestion':
        """Create MedicalQuestion from dictionary"""
        return cls(
            id=data.get("id", ""),
            question=data.get("question", ""),
            criteria=data.get("criteria", []),
            category=data.get("category", ""),
            required=data.get("required", True)
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "question": self.question,
            "criteria": self.criteria,
            "category": self.category,
            "required": self.required
        } 