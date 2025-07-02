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

# Data model for a single conversation turn
@dataclass
class ConversationTurn:
    question: str
    answer: str
    evaluation: Dict[str, Any]
    guidance: Optional[str] = None

# Data model for the overall conversation state
@dataclass
class ConversationState:
    """Represents the complete state of a conversation."""
    current_question_id: Optional[str] = None
    retries_left: int = 3
    history: List[Dict] = field(default_factory=list)
    is_finished: bool = False
    next_question_or_eval: str = ""

    def __post_init__(self):
        # Ensure max_retries is correctly initialized from config if needed
        # For now, we hardcode it but could pass a config object.
        self.max_retries = 3 
        self.retries_left = self.max_retries

    def can_retry(self) -> bool:
        """Check if retries are available for the current question."""
        return self.retries_left > 0

    def decrement_retries(self):
        """Decrement the count of available retries."""
        if self.retries_left > 0:
            self.retries_left -= 1
    
    def reset_retries(self):
        """Reset the retry counter for a new question."""
        self.retries_left = self.max_retries

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