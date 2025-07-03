import json
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
from backend.models import MedicalQuestion, MedicalChatbotConfig

logger = logging.getLogger(__name__)
llm_logger = logging.getLogger("llm_interactions")

class QuestionManager:
    """Manages medical questions with validation criteria loading and parsing"""
    
    def __init__(self, config: MedicalChatbotConfig):
        self.config = config
        self.questions: List[MedicalQuestion] = []
        self.questions_by_id: Dict[str, MedicalQuestion] = {}
        self.questions_by_category: Dict[str, List[MedicalQuestion]] = {}
        self.load_questions()
    
    def load_questions(self) -> bool:
        """Load questions from JSON file with validation criteria"""
        try:
            questions_path = Path(self.config.get_questions_file())
            
            if not questions_path.exists():
                logger.error(f"Questions file not found: {self.config.get_questions_file()}")
                self._create_default_questions()
                return False
            
            with open(questions_path, 'r', encoding='utf-8') as f:
                questions_data = json.load(f)
            
            if not isinstance(questions_data, list):
                logger.error("Questions file must contain a list of questions")
                return False
            
            # Parse and validate each question
            loaded_questions = []
            for i, question_data in enumerate(questions_data):
                try:
                    question = self._parse_question(question_data, i)
                    if question:
                        loaded_questions.append(question)
                except Exception as e:
                    logger.warning(f"Failed to parse question {i}: {e}")
                    continue
            
            if not loaded_questions:
                logger.error("No valid questions found in file")
                self._create_default_questions()
                return False
            
            self.questions = loaded_questions
            self._build_indexes()
            
            logger.info(f"Successfully loaded {len(self.questions)} questions from {self.config.get_questions_file()}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load questions: {e}")
            self._create_default_questions()
            return False
    
    def _parse_question(self, data: Dict[str, Any], index: int) -> Optional[MedicalQuestion]:
        """Parse a single question from JSON data with validation"""
        
        # Validate required fields
        required_fields = ['id', 'question', 'criteria']
        for field in required_fields:
            if field not in data:
                logger.warning(f"Question {index} missing required field: {field}")
                return None
        
        # Validate question ID
        question_id = data['id']
        if not isinstance(question_id, str) or not question_id.strip():
            logger.warning(f"Question {index} has invalid ID: {question_id}")
            return None
        
        # Validate question text
        question_text = data['question']
        if not isinstance(question_text, str) or not question_text.strip():
            logger.warning(f"Question {index} has invalid question text")
            return None
        
        # Validate criteria
        criteria = data['criteria']
        if not isinstance(criteria, list) or len(criteria) == 0:
            logger.warning(f"Question {index} has invalid criteria (must be non-empty list)")
            return None
        
        # Validate each criterion
        valid_criteria = []
        for criterion in criteria:
            if isinstance(criterion, str) and criterion.strip():
                valid_criteria.append(criterion.strip())
            else:
                logger.warning(f"Question {index} has invalid criterion: {criterion}")
        
        if not valid_criteria:
            logger.warning(f"Question {index} has no valid criteria")
            return None
        
        # Create MedicalQuestion object
        try:
            question = MedicalQuestion(
                id=question_id.strip(),
                question=question_text.strip(),
                criteria=valid_criteria,
                category=data.get('category', 'general'),
                required=data.get('required', True)
            )
            
            logger.debug(f"Parsed question: {question.id} with {len(question.criteria)} criteria")
            return question
            
        except Exception as e:
            logger.warning(f"Failed to create MedicalQuestion object for {index}: {e}")
            return None
    
    def _build_indexes(self):
        """Build indexes for quick question lookup"""
        self.questions_by_id = {q.id: q for q in self.questions}
        
        # Build category index
        self.questions_by_category = {}
        for question in self.questions:
            category = question.category
            if category not in self.questions_by_category:
                self.questions_by_category[category] = []
            self.questions_by_category[category].append(question)
        
        logger.debug(f"Built indexes: {len(self.questions_by_id)} questions, {len(self.questions_by_category)} categories")
    
    def _create_default_questions(self):
        """Create default questions as fallback"""
        logger.info("Creating default questions as fallback")
        
        default_questions = [
            MedicalQuestion(
                id="chief_complaint",
                question="What is the main reason for your visit today?",
                criteria=[
                    "Must describe a specific symptom or health concern",
                    "Must be health-related",
                    "Should be clear and specific"
                ],
                category="primary",
                required=True
            ),
            MedicalQuestion(
                id="symptom_onset",
                question="When did your symptoms start?",
                criteria=[
                    "Must include a time period",
                    "Must be specific (not vague)",
                    "Should provide clear timing"
                ],
                category="history",
                required=True
            )
        ]
        
        self.questions = default_questions
        self._build_indexes()
    
    def get_question_by_id(self, question_id: str) -> Optional[MedicalQuestion]:
        """Get a question by its ID"""
        return self.questions_by_id.get(question_id)
    
    def get_questions_by_category(self, category: str) -> List[MedicalQuestion]:
        """Get all questions in a specific category"""
        return self.questions_by_category.get(category, [])
    
    def get_all_questions(self) -> List[MedicalQuestion]:
        """Get all loaded questions"""
        return self.questions.copy()
    
    def get_required_questions(self) -> List[MedicalQuestion]:
        """Get all required questions"""
        return [q for q in self.questions if q.required]
    
    def get_question_at_index(self, index: int) -> Optional[MedicalQuestion]:
        """Get question at specific index"""
        if 0 <= index < len(self.questions):
            return self.questions[index]
        return None
    
    def get_total_questions(self) -> int:
        """Get total number of questions"""
        return len(self.questions)
    
    def get_initial_question(self) -> Optional[MedicalQuestion]:
        """Get the very first question in the list"""
        if self.questions:
            return self.questions[0]
        return None

    def is_last_question(self, index: int) -> bool:
        """Check if the given index is for the last question"""
        return index == len(self.questions) - 1

    def validate_questions_structure(self) -> Dict[str, Any]:
        """Validate the overall structure and consistency of loaded questions"""
        validation_result = {
            "valid": True,
            "total_questions": len(self.questions),
            "required_questions": len(self.get_required_questions()),
            "categories": list(self.questions_by_category.keys()),
            "issues": []
        }
        
        # Check for duplicate IDs
        ids = [q.id for q in self.questions]
        duplicate_ids = set([x for x in ids if ids.count(x) > 1])
        if duplicate_ids:
            validation_result["valid"] = False
            validation_result["issues"].append(f"Duplicate question IDs: {list(duplicate_ids)}")
        
        # Check for questions without criteria
        no_criteria_questions = [q.id for q in self.questions if not q.criteria]
        if no_criteria_questions:
            validation_result["valid"] = False
            validation_result["issues"].append(f"Questions without criteria: {no_criteria_questions}")
        
        # Check for empty question text
        empty_questions = [q.id for q in self.questions if not q.question.strip()]
        if empty_questions:
            validation_result["valid"] = False
            validation_result["issues"].append(f"Questions with empty text: {empty_questions}")
        
        return validation_result
    
    def reload_questions(self) -> bool:
        """Reload questions from file"""
        logger.info("Reloading questions from file")
        return self.load_questions()

# Convenience function for quick question loading
def load_medical_questions(config: Optional[MedicalChatbotConfig] = None) -> QuestionManager:
    """Load medical questions with default or provided configuration"""
    if config is None:
        config = MedicalChatbotConfig()
    
    return QuestionManager(config) 