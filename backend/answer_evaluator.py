import json
import logging
from typing import Dict, List, Optional, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from backend.models import MedicalQuestion, QuestionEvaluation, MedicalChatbotConfig

logger = logging.getLogger(__name__)

class AnswerEvaluator:
    """LLM-based medical answer evaluation system"""
    
    def __init__(self, config: MedicalChatbotConfig):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.evaluation_model,
            temperature=0,  # Use deterministic evaluation
            timeout=30
        )
        self.json_parser = JsonOutputParser()
        self._setup_evaluation_prompt()
    
    def _setup_evaluation_prompt(self):
        """Setup the evaluation prompt template"""
        self.evaluation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a medical assistant evaluating patient responses to medical history questions.

Your task is to evaluate whether a patient's answer meets the specified criteria for a medical question.
You must be thorough but also considerate of the patient's perspective and communication style.

Evaluation Guidelines:
1. Check if the answer addresses each specified criterion
2. Consider partial fulfillment - some criteria may be "Should" vs "Must"
3. Be understanding of non-medical terminology from patients
4. Focus on substance over perfect phrasing
5. Consider cultural and educational differences in communication

Respond with valid JSON only, no additional text."""),
            ("human", """Medical Question: {question}

Evaluation Criteria:
{criteria}

Patient's Answer: "{answer}"

Evaluate this answer and respond with JSON in exactly this format:
{{
    "is_sufficient": true/false,
    "score": 0.0-1.0,
    "feedback": "Clear explanation for the patient",
    "missing_criteria": ["list", "of", "unmet", "criteria"],
    "evaluation_reasoning": "Detailed reasoning for medical staff"
}}

Guidelines for scoring:
- 1.0: Fully meets all criteria
- 0.8-0.9: Meets most criteria with minor gaps
- 0.6-0.7: Meets some criteria but has significant gaps
- 0.4-0.5: Partially addresses the question but misses key criteria
- 0.0-0.3: Does not adequately address the question

Be understanding but ensure medical completeness.""")
        ])
    
    async def evaluate_answer(
        self, 
        question: MedicalQuestion, 
        user_answer: str,
        context: Optional[Dict[str, Any]] = None
    ) -> QuestionEvaluation:
        """Evaluate a user's answer against question criteria"""
        
        try:
            # Validate inputs
            if not user_answer or not user_answer.strip():
                return QuestionEvaluation(
                    is_sufficient=False,
                    score=0.0,
                    feedback="Please provide an answer to continue.",
                    missing_criteria=question.criteria,
                    evaluation_reasoning="No answer provided"
                )
            
            # Prepare criteria for prompt
            criteria_text = "\n".join([f"- {criterion}" for criterion in question.criteria])
            
            # Create the evaluation chain
            chain = self.evaluation_prompt | self.llm | self.json_parser
            
            # Execute evaluation
            result = await chain.ainvoke({
                "question": question.question,
                "criteria": criteria_text,
                "answer": user_answer.strip()
            })
            
            # Parse and validate result
            evaluation = self._parse_evaluation_result(result, question, user_answer)
            
            logger.info(f"Evaluated answer for question {question.id}: score={evaluation.score}, sufficient={evaluation.is_sufficient}")
            return evaluation
            
        except Exception as e:
            logger.error(f"Answer evaluation failed for question {question.id}: {e}")
            return self._create_fallback_evaluation(question, user_answer, str(e))
    
    def _parse_evaluation_result(
        self, 
        result: Dict[str, Any], 
        question: MedicalQuestion,
        user_answer: str
    ) -> QuestionEvaluation:
        """Parse LLM evaluation result into QuestionEvaluation object"""
        
        try:
            # Validate required fields
            required_fields = ["is_sufficient", "score", "feedback", "missing_criteria", "evaluation_reasoning"]
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate and clean the data
            is_sufficient = bool(result["is_sufficient"])
            score = float(result["score"])
            
            # Ensure score is in valid range
            score = max(0.0, min(1.0, score))
            
            # Ensure consistency between is_sufficient and score
            if is_sufficient and score < 0.6:
                logger.warning(f"Inconsistent evaluation: sufficient=True but score={score}, adjusting")
                is_sufficient = False
            elif not is_sufficient and score >= 0.8:
                logger.warning(f"Inconsistent evaluation: sufficient=False but score={score}, adjusting")
                is_sufficient = True
            
            feedback = str(result["feedback"]).strip()
            if not feedback:
                feedback = "Thank you for your answer." if is_sufficient else "Please provide more details."
            
            missing_criteria = result.get("missing_criteria", [])
            if not isinstance(missing_criteria, list):
                missing_criteria = []
            
            evaluation_reasoning = str(result.get("evaluation_reasoning", "")).strip()
            
            return QuestionEvaluation(
                is_sufficient=is_sufficient,
                score=score,
                feedback=feedback,
                missing_criteria=missing_criteria,
                evaluation_reasoning=evaluation_reasoning
            )
            
        except Exception as e:
            logger.error(f"Failed to parse evaluation result: {e}")
            raise ValueError(f"Invalid evaluation result format: {e}")
    
    def _create_fallback_evaluation(
        self, 
        question: MedicalQuestion, 
        user_answer: str,
        error_msg: str
    ) -> QuestionEvaluation:
        """Create fallback evaluation when LLM evaluation fails"""
        
        # Simple heuristic evaluation as fallback
        answer_length = len(user_answer.strip())
        word_count = len(user_answer.strip().split())
        
        # Basic heuristics
        if answer_length < 5:
            score = 0.1
            is_sufficient = False
            feedback = "Please provide a more detailed answer."
        elif word_count < 3:
            score = 0.3
            is_sufficient = False
            feedback = "Please provide more details about your condition."
        elif word_count >= 5:
            score = 0.7
            is_sufficient = True
            feedback = "Thank you for your response."
        else:
            score = 0.5
            is_sufficient = False
            feedback = "Please provide additional details."
        
        logger.warning(f"Using fallback evaluation for question {question.id} due to: {error_msg}")
        
        return QuestionEvaluation(
            is_sufficient=is_sufficient,
            score=score,
            feedback=feedback,
            missing_criteria=question.criteria if not is_sufficient else [],
            evaluation_reasoning=f"Fallback evaluation used due to LLM error: {error_msg}"
        )
    
    def evaluate_answer_sync(
        self, 
        question: MedicalQuestion, 
        user_answer: str,
        context: Optional[Dict[str, Any]] = None
    ) -> QuestionEvaluation:
        """Synchronous version of answer evaluation"""
        
        try:
            # Validate inputs
            if not user_answer or not user_answer.strip():
                return QuestionEvaluation(
                    is_sufficient=False,
                    score=0.0,
                    feedback="Please provide an answer to continue.",
                    missing_criteria=question.criteria,
                    evaluation_reasoning="No answer provided"
                )
            
            # Prepare criteria for prompt
            criteria_text = "\n".join([f"- {criterion}" for criterion in question.criteria])
            
            # Create the evaluation chain
            chain = self.evaluation_prompt | self.llm | self.json_parser
            
            # Execute evaluation synchronously
            result = chain.invoke({
                "question": question.question,
                "criteria": criteria_text,
                "answer": user_answer.strip()
            })
            
            # Parse and validate result
            evaluation = self._parse_evaluation_result(result, question, user_answer)
            
            logger.info(f"Evaluated answer for question {question.id}: score={evaluation.score}, sufficient={evaluation.is_sufficient}")
            return evaluation
            
        except Exception as e:
            logger.error(f"Answer evaluation failed for question {question.id}: {e}")
            return self._create_fallback_evaluation(question, user_answer, str(e))
    
    def batch_evaluate_answers(
        self, 
        questions_and_answers: List[tuple[MedicalQuestion, str]]
    ) -> List[QuestionEvaluation]:
        """Evaluate multiple answers in batch"""
        
        evaluations = []
        for question, answer in questions_and_answers:
            try:
                evaluation = self.evaluate_answer_sync(question, answer)
                evaluations.append(evaluation)
            except Exception as e:
                logger.error(f"Batch evaluation failed for question {question.id}: {e}")
                evaluations.append(self._create_fallback_evaluation(question, answer, str(e)))
        
        return evaluations
    
    def get_evaluation_summary(self, evaluations: List[QuestionEvaluation]) -> Dict[str, Any]:
        """Get summary statistics for a set of evaluations"""
        
        if not evaluations:
            return {"error": "No evaluations provided"}
        
        sufficient_count = sum(1 for e in evaluations if e.is_sufficient)
        total_count = len(evaluations)
        average_score = sum(e.score for e in evaluations) / total_count
        
        return {
            "total_questions": total_count,
            "sufficient_answers": sufficient_count,
            "insufficient_answers": total_count - sufficient_count,
            "completion_rate": sufficient_count / total_count,
            "average_score": round(average_score, 2),
            "score_distribution": {
                "excellent": sum(1 for e in evaluations if e.score >= 0.9),
                "good": sum(1 for e in evaluations if 0.7 <= e.score < 0.9),
                "fair": sum(1 for e in evaluations if 0.5 <= e.score < 0.7),
                "poor": sum(1 for e in evaluations if e.score < 0.5)
            }
        }

# Convenience function for quick evaluation
def evaluate_medical_answer(
    question: MedicalQuestion,
    user_answer: str,
    config: Optional[MedicalChatbotConfig] = None
) -> QuestionEvaluation:
    """Quick evaluation function for single answers"""
    if config is None:
        config = MedicalChatbotConfig()
    
    evaluator = AnswerEvaluator(config)
    return evaluator.evaluate_answer_sync(question, user_answer) 