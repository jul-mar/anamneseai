from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from backend.models import MedicalChatState, MedicalChatbotConfig, MedicalQuestion
from backend.question_manager import QuestionManager
from backend.answer_evaluator import AnswerEvaluator
from backend.summary_generator import MedicalSummaryGenerator
import logging

logger = logging.getLogger(__name__)

# This implementation will be progressively refined.
# Full functionality requires all sub-tasks for Parent Task 3.0 to be complete.

def build_medical_graph():
    """
    Builds and compiles the LangGraph for the medical history conversation.
    """
    
    # Instantiate necessary components for the graph's logic
    config = MedicalChatbotConfig()
    question_manager = QuestionManager(config)
    answer_evaluator = AnswerEvaluator(config)
    summary_generator = MedicalSummaryGenerator(config)

    def ask_question(state: MedicalChatState) -> dict:
        """
        Asks the current question, handling the welcome message and retries.
        """
        current_question = question_manager.get_question_at_index(state.current_question_index)

        # If no more questions are left, trigger session completion
        if not current_question:
            return {
                "is_complete": True,
                "last_bot_message": "Thank you. Your medical history has been completely recorded. A summary is being created.",
                "needs_session_summary": True
            }

        bot_message = ""
        # Handle the very first interaction (welcome message + first question)
        if state.is_welcome_phase:
            welcome_message = "Welcome to QuestionnAIre! I am your medical assistant. To begin, please answer the following question."
            bot_message = f"{welcome_message}\n\n{current_question.question}"
        # Handle retries - this should not happen as retries are handled in handle_insufficient_response
        elif state.retry_count > 0:
            # This is a fallback that should rarely be used
            bot_message = current_question.question
        # Handle regular question progression
        else:
            bot_message = current_question.question
            
        return {
            "current_question": current_question.to_dict(),
            "last_bot_message": bot_message,
            "is_welcome_phase": False  # Welcome phase is over after the first message is composed
        }

    def evaluate_response(state: MedicalChatState) -> dict:
        """
        Evaluates the user's response using the AnswerEvaluator.
        """
        user_answer = state.user_input
        current_question_data = state.current_question

        if not user_answer or not current_question_data:
            return {"evaluation_result": {
                "is_sufficient": False,
                "score": 0.0,
                "feedback": "An internal error occurred.",
                "guidance": "Could you please repeat your answer?",
                "evaluation_reasoning": "Missing user_input or current_question in state."
            }}

        # Re-create the MedicalQuestion object from the dictionary in the state
        question = MedicalQuestion.from_dict(current_question_data)

        # Evaluate the answer synchronously
        evaluation = answer_evaluator.evaluate_answer_sync(
            question=question,
            user_answer=user_answer
        )

        return {"evaluation_result": evaluation.to_dict()}

    def handle_sufficient_response(state: MedicalChatState) -> dict:
        """
        Handles a sufficient response by generating a summary, advancing to the next question, and resetting retries.
        """
        # Generate medical summary for the current question-answer pair
        current_question_data = state.current_question
        user_answer = state.user_input
        
        if current_question_data and user_answer:
            try:
                # Re-create the MedicalQuestion object from the dictionary in the state
                question = MedicalQuestion.from_dict(current_question_data)
                
                # Generate clinical summary synchronously
                summary_result = summary_generator.generate_question_summary_sync(
                    question=question.question,
                    answer=user_answer,
                    criteria=question.criteria
                )
                
                if summary_result:
                    # Store the summary in the state for database persistence
                    if not hasattr(state, 'question_summaries'):
                        state.question_summaries = {}
                    
                    state.question_summaries[state.current_question_index] = {
                        "question_id": question.id,
                        "question_text": question.question,
                        "user_response": user_answer,
                        "summary": summary_result,
                        "question_index": state.current_question_index
                    }
                    
                    logger.info(f"Generated summary for question {state.current_question_index}: {question.question[:50]}...")
                else:
                    logger.warning(f"Failed to generate summary for question {state.current_question_index}")
                    
            except Exception as e:
                logger.error(f"Error generating summary for question {state.current_question_index}: {e}")

        # The state object's method encapsulates the logic for advancing.
        state.advance_to_next_question()

        # After advancing, get the new question and set it as the next bot message.
        new_bot_message = ""
        if not state.is_complete:
            # If we are not done, get the next question to ask.
            current_question = question_manager.get_question_at_index(state.current_question_index)
            if current_question:
                state.current_question = current_question.to_dict()
                new_bot_message = current_question.question
        # If state.is_complete is True, the routing will handle sending it
        # to the summary node, which provides its own completion message.

        # Return the updated fields to be merged back into the graph's state.
        return {
            "current_question_index": state.current_question_index,
            "retry_count": state.retry_count,
            "is_complete": state.is_complete,
            "current_question": state.current_question,
            "question_summaries": getattr(state, 'question_summaries', {}),
            "last_bot_message": new_bot_message
        }

    def handle_insufficient_response(state: MedicalChatState) -> dict:
        """
        Handles an insufficient response by incrementing the retry count or advancing
        to the next question if the maximum number of retries has been reached.
        """
        # Check if the user has retries left for the current question
        if state.has_retries_left():
            # If so, increment the retry count and generate guidance-based message
            state.increment_retry()
            
            # Get current question for guidance message
            current_question = question_manager.get_question_at_index(state.current_question_index)
            if current_question:
                # Get guidance from evaluation result
                evaluation_result = state.evaluation_result or {}
                guidance = evaluation_result.get("guidance", "Could you please provide more details?")
                
                if guidance and guidance.strip():
                    # Use guidance as the main message - it's already contextual and user-friendly
                    bot_message = guidance
                else:
                    # Fallback if no guidance is available
                    bot_message = f"Could you please provide more details? {current_question.question}"
                
                return {
                    "retry_count": state.retry_count,
                    "last_bot_message": bot_message
                }
            else:
                return {"retry_count": state.retry_count}
        else:
            # If no retries are left, advance to the next question to avoid getting stuck.
            state.advance_to_next_question()
            
            # Update current_question to the new question after advancing
            if not state.is_complete:
                current_question = question_manager.get_question_at_index(state.current_question_index)
                if current_question:
                    state.current_question = current_question.to_dict()
            
            return {
                "current_question_index": state.current_question_index,
                "retry_count": state.retry_count,  # Will be 0 after advancing
                "is_complete": state.is_complete,
                "current_question": state.current_question
            }

    def route_evaluation(state: MedicalChatState) -> str:
        """Route based on evaluation result"""
        evaluation_result = state.evaluation_result or {}
        if evaluation_result.get("is_sufficient"):
            return "sufficient"
        return "insufficient"

    def generate_session_summary(state: MedicalChatState) -> dict:
        """Generate comprehensive session summary when all questions are completed"""
        try:
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
            
            summary_list = []
            if state.question_summaries:
                # Sort by question index to ensure correct order
                sorted_summaries = sorted(state.question_summaries.items())
                for index, summary_data in sorted_summaries:
                    question_text = summary_data.get("question_text", "Unknown Question")
                    # The summary from the generator is a dict, get the text from it
                    summary_details = summary_data.get("summary", {})
                    summary_text = summary_details.get("summary", "No summary available.")
                    summary_list.append(f"{index + 1}. {question_text}: {summary_text}")

            # Add individual question summaries to session data
            for _, summary_data in state.question_summaries.items():
                session_data["answered_questions"].append(summary_data)
            
            # Generate comprehensive session summary synchronously
            comprehensive_summary = summary_generator.generate_session_summary_sync(session_data)
            
            final_message = "Your medical history is complete. The summary could not be automatically created, but your answers have been saved."
            if comprehensive_summary and summary_list:
                formatted_summaries = "\n".join(summary_list)
                final_message = f"Your medical history is complete. Here is a summary of your answers:\n\n{formatted_summaries}"
                logger.info(f"Generated comprehensive session summary for session {state.session_id}")
            else:
                logger.warning(f"Failed to generate session summary for session {state.session_id}")
            
            return {
                "session_summary": comprehensive_summary,
                "needs_session_summary": False,
                "last_bot_message": final_message
            }
            
        except Exception as e:
            logger.error(f"Error generating session summary: {e}")
            return {
                "session_summary": None,
                "needs_session_summary": False,
                "last_bot_message": "Your medical history is complete. There was a problem creating the summary, but your answers have been saved."
            }

    def route_after_handling_response(state: MedicalChatState) -> str:
        """Determines the next step after handling a sufficient response."""
        if state.is_complete:
            # If the questionnaire is complete, generate the final summary
            return "generate_session_summary"
        else:
            # Otherwise, the graph flow ends for this turn
            return END
    
    # Define the workflow
    workflow = StateGraph(MedicalChatState)

    # Add nodes
    workflow.add_node("ask_question", ask_question)
    workflow.add_node("evaluate_response", evaluate_response)
    workflow.add_node("handle_sufficient_response", handle_sufficient_response)
    workflow.add_node("handle_insufficient_response", handle_insufficient_response)
    workflow.add_node("generate_session_summary", generate_session_summary)

    def should_evaluate(state: MedicalChatState) -> str:
        """Check if we should evaluate user input or just present question"""
        # If this is the initial question presentation (no user input yet), just show question
        if not state.user_input or not state.user_input.strip():
            return END
        # If we have user input, evaluate it
        return "evaluate_response"
    
    # Define edges
    workflow.set_entry_point("ask_question")
    workflow.add_conditional_edges(
        "ask_question",
        should_evaluate,
        {
            "evaluate_response": "evaluate_response",
            END: END
        }
    )
    
    # Conditional routing after evaluation
    workflow.add_conditional_edges(
        "evaluate_response",
        route_evaluation,
        {
            "sufficient": "handle_sufficient_response",
            "insufficient": "handle_insufficient_response"
        }
    )

    # After handling a sufficient response, decide whether to summarize or end
    workflow.add_conditional_edges(
        "handle_sufficient_response",
        route_after_handling_response,
        {
            "generate_session_summary": "generate_session_summary",
            END: END
        }
    )

    # After handling an insufficient response, always end to await next user input
    workflow.add_edge("handle_insufficient_response", END)
    
    # End after generating session summary
    workflow.add_edge("generate_session_summary", END)
    
    # Compile the graph with a memory saver to make it stateful
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

# Create a global instance of the graph
anamnesis_graph = build_medical_graph() 