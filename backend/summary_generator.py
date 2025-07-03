import json
import logging
from typing import Dict, List, Optional, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from backend.models import MedicalChatbotConfig

logger = logging.getLogger(__name__)
llm_logger = logging.getLogger("llm_interactions")

class MedicalSummaryGenerator:
    """Medical summary generation using OpenAI GPT-4o-mini for clinical documentation"""
    
    def __init__(self, config: MedicalChatbotConfig):
        self.config = config
        self.llm = ChatOpenAI(
            model=config.conversation_model,  # Using gpt-4o-mini from config
            temperature=0.1,  # Low temperature for consistent clinical summaries
            timeout=60
        )
        self.json_parser = JsonOutputParser()
        self._setup_prompts()
    
    def _setup_prompts(self):
        """Setup the prompt templates for summary generation"""
        
        # Prompt for summarizing a single question-answer pair
        self.question_summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a medical assistant transforming patient answers into precise clinical summaries.

Your task is to convert a patient's response to a medical question into a structured, professional summary that can be used by clinicians.

Guidelines:
- Use medical terminology where appropriate
- Be concise and objective
- Retain all important details
- Structure the information logically
- Do not add interpretations or diagnoses
- Summarize only the information provided by the patient

Respond with valid JSON only, no additional text."""),
            ("human", """Question: {question}

Patient Answer: {answer}

Evaluation Criteria: {criteria}

Create a structured clinical summary in the following JSON format:
{{
    "summary": "Precise clinical summary of the patient's answer",
    "key_findings": ["List", "of", "key", "findings"],
    "timeline": "Timeline information if available",
    "severity": "Severity level if mentioned",
    "associated_factors": ["Associated", "factors"]
}}""")
        ])
        
        # Prompt for generating a comprehensive session summary
        self.session_summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a senior medical analyst responsible for creating a comprehensive clinical summary from a patient's entire medical history session.

Your task is to synthesize all answered questions, conversation history, and metadata into a holistic, professional, and structured clinical document.

Guidelines:
- Synthesize, do not just list. Connect related pieces of information.
- Provide a narrative summary that tells the patient's story.
- Highlight the most critical findings and red flags.
- Maintain a neutral, objective, and professional tone.
- Structure the final output logically for quick clinical review.

Respond with valid JSON only, no additional text."""),
            ("human", """Please generate a comprehensive clinical summary based on the following session data:

{session_data_json}

Create a structured clinical summary in the following JSON format:
{{
    "patient_id": "Unique patient identifier",
    "session_id": "Session identifier",
    "summary_date": "Date of summary generation",
    "narrative_summary": "A cohesive narrative of the patient's medical history, synthesizing all data.",
    "key_findings": ["A prioritized list of the most important clinical findings and red flags."],
    "symptom_timeline": "A chronological overview of symptom onset and progression.",
    "medications_and_allergies": {{
        "current_medications": ["List of current medications"],
        "allergies": ["List of known allergies"]
    }},
    "past_medical_history": ["Summary of relevant past medical history"],
    "final_assessment_prompt": "A final question or prompt for the clinician based on the summary (e.g., 'Consider investigating potential cardiac causes for reported chest pain.')"
}}""")
        ])
    
    async def generate_question_summary(
        self, 
        question: str, 
        answer: str,
        criteria: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Generate a clinical summary for a single question-answer pair"""
        
        try:
            # Create the chain
            chain = self.question_summary_prompt | self.llm | JsonOutputParser()
            
            # Format and log the prompt
            prompt_for_log = self.question_summary_prompt.format_prompt(
                question=question,
                answer=answer,
                criteria=criteria
            ).to_string()
            llm_logger.info(f"--- LLM PROMPT (Question Summary) ---\n{prompt_for_log}")
            
            # Execute the chain
            result = await chain.ainvoke({
                "question": question,
                "answer": answer,
                "criteria": criteria
            })
            
            # Log the response
            llm_logger.info(f"--- LLM RESPONSE (Question Summary) ---\n{json.dumps(result, indent=2)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate question summary: {e}")
            return self._create_fallback_question_summary(question, answer)
    
    def generate_question_summary_sync(
        self, 
        question: str, 
        answer: str,
        criteria: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Synchronous version of question summary generation"""
        
        try:
            # Create the chain
            chain = self.question_summary_prompt | self.llm | JsonOutputParser()
            
            # Format and log the prompt
            prompt_for_log = self.question_summary_prompt.format_prompt(
                question=question,
                answer=answer,
                criteria=criteria
            ).to_string()
            llm_logger.info(f"--- LLM PROMPT (Sync Question Summary) ---\n{prompt_for_log}")

            # Execute the chain
            result = chain.invoke({
                "question": question,
                "answer": answer,
                "criteria": criteria
            })
            
            # Log the response
            llm_logger.info(f"--- LLM RESPONSE (Sync Question Summary) ---\n{json.dumps(result, indent=2)}")

            return result
            
        except Exception as e:
            logger.error(f"Failed to generate sync question summary: {e}")
            return self._create_fallback_question_summary(question, answer)
    
    async def generate_session_summary(
        self, 
        session_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Generate a comprehensive clinical summary for an entire session"""
        
        try:
            # Create the chain
            chain = self.session_summary_prompt | self.llm | JsonOutputParser()
            
            # Format and log the prompt
            prompt_for_log = self.session_summary_prompt.format_prompt(
                session_data_json=json.dumps(session_data, indent=2)
            ).to_string()
            llm_logger.info(f"--- LLM PROMPT (Session Summary) ---\n{prompt_for_log}")

            # Execute the chain
            result = await chain.ainvoke({
                "session_data_json": json.dumps(session_data, indent=2)
            })

            # Log the response
            llm_logger.info(f"--- LLM RESPONSE (Session Summary) ---\n{json.dumps(result, indent=2)}")
            
            return result

        except Exception as e:
            logger.error(f"Failed to generate session summary: {e}")
            return self._create_fallback_session_summary(session_data)
    
    def generate_session_summary_sync(
        self, 
        session_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Synchronous version of comprehensive session summary generation"""
        
        try:
            # Create the chain
            chain = self.session_summary_prompt | self.llm | JsonOutputParser()

            # Format and log the prompt
            prompt_for_log = self.session_summary_prompt.format_prompt(
                session_data_json=json.dumps(session_data, indent=2)
            ).to_string()
            llm_logger.info(f"--- LLM PROMPT (Sync Session Summary) ---\n{prompt_for_log}")

            # Execute the chain
            result = chain.invoke({
                "session_data_json": json.dumps(session_data, indent=2)
            })

            # Log the response
            llm_logger.info(f"--- LLM RESPONSE (Sync Session Summary) ---\n{json.dumps(result, indent=2)}")

            return result

        except Exception as e:
            logger.error(f"Failed to generate session summary (sync): {e}")
            return self._create_fallback_session_summary(session_data)
    
    def _format_session_data(self, session_data: Dict[str, Any]) -> str:
        """Format session data for the summary prompt"""
        
        formatted_parts = []
        
        # Add answered questions
        if "answered_questions" in session_data:
            formatted_parts.append("BEANTWORTETE FRAGEN:")
            for qa in session_data["answered_questions"]:
                formatted_parts.append(f"Frage: {qa.get('question_text', 'N/A')}")
                formatted_parts.append(f"Antwort: {qa.get('user_response', 'N/A')}")
                formatted_parts.append(f"Zusammenfassung: {qa.get('summary', 'N/A')}")
                formatted_parts.append("---")
        
        # Add conversation history if available
        if "conversation_history" in session_data:
            formatted_parts.append("\nGESPRÄCHSVERLAUF:")
            for msg in session_data["conversation_history"]:
                role = "Patient" if msg.get("role") == "user" else "System"
                formatted_parts.append(f"{role}: {msg.get('message', 'N/A')}")
        
        return "\n".join(formatted_parts)
    
    def _create_fallback_question_summary(self, question: str, answer: str) -> Dict[str, Any]:
        """Create a basic fallback summary when LLM generation fails"""
        
        return {
            "summary": f"Patient antwortete auf die Frage '{question}' mit: {answer[:200]}{'...' if len(answer) > 200 else ''}",
            "key_findings": [answer[:100] + "..." if len(answer) > 100 else answer],
            "timeline": "Nicht spezifiziert",
            "severity": "Nicht bewertet",
            "associated_factors": []
        }
    
    def _create_fallback_session_summary(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a basic fallback summary when LLM generation fails"""
        
        return {
            "chief_complaint": "Zusammenfassung konnte nicht generiert werden",
            "history_of_present_illness": "Daten verfügbar, aber Verarbeitung fehlgeschlagen",
            "symptom_timeline": "Nicht verfügbar",
            "associated_symptoms": [],
            "severity_assessment": "Nicht bewertet",
            "aggravating_factors": [],
            "relieving_factors": [],
            "previous_episodes": "Nicht spezifiziert",
            "current_medications": [],
            "allergies": "Nicht spezifiziert",
            "medical_history": "Nicht spezifiziert",
            "clinical_impression": "Automatische Zusammenfassung fehlgeschlagen - manuelle Überprüfung erforderlich"
        }

# Convenience function for quick summary generation
def generate_medical_summary(
    question: str,
    answer: str,
    criteria: List[str],
    config: Optional[MedicalChatbotConfig] = None
) -> Optional[Dict[str, Any]]:
    """Generate a medical summary with default or provided configuration"""
    if config is None:
        config = MedicalChatbotConfig()
    
    generator = MedicalSummaryGenerator(config)
    return generator.generate_question_summary_sync(question, answer, criteria) 