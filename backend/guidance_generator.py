import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.models import MedicalQuestion, QuestionEvaluation, MedicalChatbotConfig

logger = logging.getLogger(__name__)

class GuidanceGenerator:
    """Generates helpful, user-friendly guidance for insufficient answers."""
    
    def __init__(self, config: MedicalChatbotConfig):
        self.config = config
        self.llm = ChatOpenAI(model=config.conversation_model, temperature=0.7)
        self._setup_prompt()

    def _setup_prompt(self):
        """Sets up the prompt template for generating guidance."""
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a compassionate medical assistant. Your goal is to help a patient provide a more complete answer to a medical question.

You will be given the original question, the patient's insufficient answer, and a list of missing criteria.

Your task is to generate a friendly, encouraging, and clear follow-up message.

Guidelines:
1.  **Be encouraging:** Start with a positive and supportive tone (e.g., "Thanks for that information. To help me understand better...").
2.  **Be specific:** Clearly state what information is missing by referencing the `missing_criteria`. Rephrase them into a natural, conversational question, not a list.
3.  **Provide examples:** If possible, give a simple example of the kind of information that would be helpful.
4.  **Keep it concise:** The message should be short and easy to understand.
5.  **Do not sound robotic or demanding.** Sound like a caring human.
6.  **Re-ask the original question at the end** to give the user a clear call to action.

Example:
-   **Original Question:** "When did your symptoms first start?"
-   **Patient's Answer:** "A while ago."
-   **Missing Criteria:** ["Must include a time period (days, weeks, months)", "Must be specific (not vague terms like 'recently' or 'a while ago')"]
-   **Generated Guidance:** "Thanks for letting me know. To get a clearer picture, could you be a bit more specific about when the symptoms began? For example, you could say 'about 3 days ago' or 'last Tuesday'. When did your symptoms first start?"
"""),
            ("human", """
Original Question:
"{question}"

Patient's Answer:
"{answer}"

Missing Information based on these criteria:
{missing_criteria}

Please generate a helpful and encouraging follow-up message for the patient.
"""),
        ])

    async def generate_guidance(
        self,
        question: MedicalQuestion,
        evaluation: QuestionEvaluation,
        answer: str,
        retries_remaining: int
    ) -> str:
        """Asynchronously generates guidance for an insufficient answer."""
        if evaluation.is_sufficient:
            return "Thank you, that's very helpful."

        if retries_remaining <= 0:
            return f"Thank you for the information. We'll move on to the next question for now. Your doctor can discuss this with you in more detail."

        try:
            # Use LLM for sophisticated guidance
            if evaluation.missing_criteria:
                chain = self.prompt | self.llm | StrOutputParser()
                criteria_str = "\n".join(f"- {c}" for c in evaluation.missing_criteria)

                guidance = await chain.ainvoke({
                    "question": question.question,
                    "answer": answer,
                    "missing_criteria": criteria_str
                })
            else:
                # Simple fallback if no specific criteria are missing
                guidance = f"Could you please provide a little more detail? Let's try again: {question.question}"

            # Add retry information
            retries_plural = "attempts" if retries_remaining > 1 else "attempt"
            guidance += f" (You have {retries_remaining} {retries_plural} left for this question.)"

            logger.info(f"Generated guidance for question {question.id}")
            return guidance
        except Exception as e:
            logger.error(f"Guidance generation failed: {e}")
            return self.generate_simple_guidance(question, evaluation, retries_remaining)


    def generate_simple_guidance(
        self,
        question: MedicalQuestion,
        evaluation: QuestionEvaluation,
        retries_remaining: int
    ) -> str:
        """Generates simple, non-LLM guidance as a fallback."""
        if retries_remaining <= 0:
            return f"Thank you for the information. We'll move on to the next question for now. Your doctor can discuss this with you in more detail."

        feedback = evaluation.feedback or "Could you please provide more detail?"
        
        # Add missing criteria to feedback if available
        if evaluation.missing_criteria:
            missing_info = ", ".join(evaluation.missing_criteria)
            feedback = f"Thanks for the answer. To help me understand better, please provide more information about: {missing_info}."

        retries_plural = "attempts" if retries_remaining > 1 else "attempt"
        guidance = f"{feedback} Let's try again. {question.question} (You have {retries_remaining} {retries_plural} left.)"

        return guidance 