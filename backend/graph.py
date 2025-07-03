from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from backend.models import MedicalChatState, MedicalChatbotConfig, MedicalQuestion
from backend.question_manager import QuestionManager
from backend.answer_evaluator import AnswerEvaluator

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

    def ask_question(state: MedicalChatState) -> dict:
        """
        Asks the current question, handling the welcome message and retries.
        """
        current_question = question_manager.get_question_at_index(state.current_question_index)

        # If no more questions are left, the check_completion node will end the graph.
        # This is a safeguard.
        if not current_question:
            return {
                "is_complete": True,
                "last_bot_message": "Vielen Dank. Ihre medizinische Vorgeschichte wurde erfasst."
            }

        bot_message = ""
        # Handle the very first interaction (welcome message + first question)
        if state.is_welcome_phase:
            welcome_message = "Willkommen bei AnamneseAI! Ich bin Ihr medizinischer Assistent. Um zu beginnen, beantworten Sie bitte die folgende Frage."
            bot_message = f"{welcome_message}\\n\\n{current_question.question}"
        # Handle retries for insufficient answers
        elif state.retry_count > 0:
            guidance = state.evaluation_result.get("guidance", "Könnten Sie bitte etwas mehr Details angeben?")
            bot_message = f"{guidance}\\n\\nLassen Sie es uns noch einmal versuchen: {current_question.question}"
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
                "feedback": "Ein interner Fehler ist aufgetreten.",
                "guidance": "Könnten Sie Ihre Antwort bitte wiederholen?",
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
        Handles a sufficient response by advancing to the next question and resetting retries.
        """
        # The state object's method encapsulates the logic for advancing.
        state.advance_to_next_question()

        # Return the updated fields to be merged back into the graph's state.
        return {
            "current_question_index": state.current_question_index,
            "retry_count": state.retry_count,
            "is_complete": state.is_complete,
            "current_question": state.current_question
        }

    def handle_insufficient_response(state: MedicalChatState) -> dict:
        """
        Handles an insufficient response by incrementing the retry count or advancing
        to the next question if the maximum number of retries has been reached.
        """
        # Check if the user has retries left for the current question
        if state.has_retries_left():
            # If so, increment the retry count. The graph will loop back to ask again.
            state.increment_retry()
            return {"retry_count": state.retry_count}
        else:
            # If no retries are left, advance to the next question to avoid getting stuck.
            state.advance_to_next_question()
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

    def check_completion(state: MedicalChatState) -> str:
        """Check if all questions have been answered"""
        if state.is_complete:
            return END
        return "ask_question"
    
    # Define the workflow
    workflow = StateGraph(MedicalChatState)

    # Add nodes
    workflow.add_node("ask_question", ask_question)
    workflow.add_node("evaluate_response", evaluate_response)
    workflow.add_node("handle_sufficient_response", handle_sufficient_response)
    workflow.add_node("handle_insufficient_response", handle_insufficient_response)

    # Define edges
    workflow.set_entry_point("ask_question")
    workflow.add_edge("ask_question", "evaluate_response")
    
    # Conditional routing after evaluation
    workflow.add_conditional_edges(
        "evaluate_response",
        route_evaluation,
        {
            "sufficient": "handle_sufficient_response",
            "insufficient": "handle_insufficient_response"
        }
    )

    # Loop back or end after handling responses
    workflow.add_conditional_edges(
        "handle_sufficient_response",
        check_completion,
        {END: END, "ask_question": "ask_question"}
    )
    workflow.add_conditional_edges(
        "handle_insufficient_response",
        check_completion,
        {END: END, "ask_question": "ask_question"}
    )
    
    # Compile the graph with a memory saver to make it stateful
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

# Create a global instance of the graph
anamnesis_graph = build_medical_graph() 