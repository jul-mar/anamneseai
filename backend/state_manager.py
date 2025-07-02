# backend/state_manager.py
import logging
from typing import Optional

from .models import (
    ConversationState,
    MedicalQuestion,
    QuestionEvaluation,
    MedicalChatbotConfig,
)
from .question_manager import QuestionManager
from .answer_evaluator import AnswerEvaluator
from .guidance_generator import GuidanceGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages the conversation state by orchestrating question selection,
    answer evaluation, and guidance generation.
    """

    def __init__(self, config: MedicalChatbotConfig):
        self.config = config
        self.question_manager = QuestionManager(config)
        self.answer_evaluator = AnswerEvaluator(config)
        self.guidance_generator = GuidanceGenerator(config)

    async def process_user_answer(
        self, state: ConversationState, user_answer: str
    ) -> ConversationState:
        """
        Processes the user's answer to the current question and updates the state.

        Args:
            state: The current conversation state.
            user_answer: The user's most recent answer.

        Returns:
            The updated conversation state.
        """
        if not state.current_question_id:
            logger.error("State has no current_question_id, cannot process answer.")
            state.is_finished = True
            state.next_question_or_eval = "Sorry, an internal error occurred (no active question)."
            return state

        current_question = self.question_manager.get_question_by_id(
            state.current_question_id
        )
        if not current_question:
            logger.error(f"Could not find question with ID: {state.current_question_id}")
            state.is_finished = True
            state.next_question_or_eval = "Sorry, an internal error occurred."
            return state

        logger.info(f"Processing answer for question '{current_question.id}'")

        # Evaluate the answer
        evaluation = await self.answer_evaluator.evaluate_answer(
            current_question, user_answer
        )

        state.history.append(
            {
                "question": current_question.question,
                "answer": user_answer,
                "evaluation": evaluation.to_dict(),
            }
        )

        if evaluation.is_sufficient:
            logger.info("Answer is sufficient. Moving to the next question.")
            return self._prepare_next_question(state)
        else:
            logger.info("Answer is insufficient. Handling retry.")
            return await self._handle_insufficient_answer(
                state, current_question, evaluation, user_answer
            )

    def _prepare_next_question(self, state: ConversationState) -> ConversationState:
        """
        Identifies and prepares the next question in the sequence.
        """
        if not state.current_question_id:
            logger.error("State has no current_question_id, cannot prepare next question.")
            state.is_finished = True
            state.next_question_or_eval = "Sorry, an internal error occurred (no active question)."
            return state

        current_index = self.question_manager.get_question_index(
            state.current_question_id
        )
        next_question = self.question_manager.get_question_by_index(current_index + 1)

        if next_question:
            state.current_question_id = next_question.id
            state.next_question_or_eval = next_question.question
            state.reset_retries()
        else:
            logger.info("No more questions. Finishing conversation.")
            state.is_finished = True
            state.next_question_or_eval = self._generate_summary(state)

        return state

    async def _handle_insufficient_answer(
        self,
        state: ConversationState,
        question: MedicalQuestion,
        evaluation: QuestionEvaluation,
        user_answer: str,
    ) -> ConversationState:
        """
        Handles the logic for an insufficient answer, including retries.
        """
        if state.can_retry():
            state.decrement_retries()
            logger.info(f"Retrying question. {state.retries_left} retries left.")
            guidance = await self.guidance_generator.generate_guidance(
                question, evaluation, user_answer, state.retries_left
            )
            state.next_question_or_eval = guidance
        else:
            logger.warning("No retries left. Moving to the next question.")
            guidance = await self.guidance_generator.generate_guidance(
                question, evaluation, user_answer, retries_remaining=0
            )
            # We add the guidance to the history to inform the user why we moved on
            state.history.append({"system_notice": guidance})
            state = self._prepare_next_question(state)

        return state
    
    def _generate_summary(self, state: ConversationState) -> str:
        """
        Generates a final summary of the conversation.
        """
        # This can be expanded to be more sophisticated, e.g., using an LLM.
        summary = "Thank you for answering all questions. Here is a summary of your answers:\n\n"
        for item in state.history:
            if "question" in item:
                summary += f"- Q: {item['question']}\n  A: {item['answer']}\n"
        return summary

    def get_initial_state(self) -> ConversationState:
        """
        Returns the initial state for a new conversation.
        """
        first_question = self.question_manager.get_question_by_index(0)
        if not first_question:
            raise ValueError("No questions found in the question set.")

        return ConversationState(
            current_question_id=first_question.id,
            next_question_or_eval=first_question.question,
        ) 