import logging
from typing import Dict, List, Optional, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from backend.models import MedicalChatbotConfig

logger = logging.getLogger(__name__)

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
        """Setup prompt templates for different types of summaries"""
        
        # Prompt for individual question summaries
        self.question_summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """Sie sind ein medizinischer Assistent, der Patientenantworten in präzise klinische Zusammenfassungen umwandelt.

Ihre Aufgabe ist es, eine Patientenantwort auf eine medizinische Frage in eine strukturierte, professionelle Zusammenfassung zu verwandeln, die von Ärzten verwendet werden kann.

Richtlinien:
- Verwenden Sie medizinische Fachterminologie wo angemessen
- Seien Sie präzise und objektiv
- Behalten Sie alle wichtigen Details bei
- Strukturieren Sie die Informationen logisch
- Verwenden Sie keine Interpretationen oder Diagnosen
- Fassen Sie nur die vom Patienten bereitgestellten Informationen zusammen

Antworten Sie nur mit gültigem JSON, ohne zusätzlichen Text."""),
            ("human", """Frage: {question}

Patientenantwort: {answer}

Bewertungskriterien: {criteria}

Erstellen Sie eine strukturierte klinische Zusammenfassung im folgenden JSON-Format:
{{
    "summary": "Präzise klinische Zusammenfassung der Patientenantwort",
    "key_findings": ["Liste", "wichtiger", "Befunde"],
    "timeline": "Zeitliche Angaben falls vorhanden",
    "severity": "Schweregrad falls erwähnt",
    "associated_factors": ["Begleitende", "Faktoren"]
}}""")
        ])
        
        # Prompt for comprehensive session summaries
        self.session_summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """Sie sind ein medizinischer Assistent, der eine umfassende klinische Zusammenfassung aus einer vollständigen Anamnese erstellt.

Ihre Aufgabe ist es, alle gesammelten Patienteninformationen in eine strukturierte, professionelle medizinische Zusammenfassung zu konsolidieren.

Richtlinien:
- Verwenden Sie standard medizinische Dokumentationsformate
- Organisieren Sie Informationen nach klinischen Kategorien
- Priorisieren Sie die wichtigsten Befunde
- Stellen Sie Zusammenhänge zwischen verschiedenen Symptomen her
- Verwenden Sie präzise medizinische Terminologie
- Erstellen Sie eine objektive, faktische Zusammenfassung

Antworten Sie nur mit gültigem JSON, ohne zusätzlichen Text."""),
            ("human", """Vollständige Anamnese-Daten:

{session_data}

Erstellen Sie eine umfassende klinische Zusammenfassung im folgenden JSON-Format:
{{
    "chief_complaint": "Hauptbeschwerde des Patienten",
    "history_of_present_illness": "Detaillierte Beschreibung der aktuellen Beschwerden",
    "symptom_timeline": "Zeitlicher Verlauf der Symptome",
    "associated_symptoms": ["Liste", "aller", "Begleitsymptome"],
    "severity_assessment": "Bewertung des Schweregrades",
    "aggravating_factors": ["Verstärkende", "Faktoren"],
    "relieving_factors": ["Lindernde", "Faktoren"],
    "previous_episodes": "Frühere ähnliche Episoden",
    "current_medications": ["Aktuelle", "Medikamente"],
    "allergies": "Bekannte Allergien",
    "medical_history": "Relevante Vorgeschichte",
    "clinical_impression": "Klinischer Gesamteindruck basierend auf den Daten"
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
            # Prepare criteria text
            criteria_text = "\n".join([f"- {criterion}" for criterion in criteria])
            
            # Create the summary chain
            chain = self.question_summary_prompt | self.llm | self.json_parser
            
            # Execute summary generation
            result = await chain.ainvoke({
                "question": question,
                "answer": answer,
                "criteria": criteria_text
            })
            
            logger.info(f"Generated question summary for: {question[:50]}...")
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
            # Prepare criteria text
            criteria_text = "\n".join([f"- {criterion}" for criterion in criteria])
            
            # Create the summary chain
            chain = self.question_summary_prompt | self.llm | self.json_parser
            
            # Execute summary generation synchronously
            result = chain.invoke({
                "question": question,
                "answer": answer,
                "criteria": criteria_text
            })
            
            logger.info(f"Generated sync question summary for: {question[:50]}...")
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
            # Format session data for the prompt
            formatted_data = self._format_session_data(session_data)
            
            # Create the summary chain
            chain = self.session_summary_prompt | self.llm | self.json_parser
            
            # Execute summary generation
            result = await chain.ainvoke({
                "session_data": formatted_data
            })
            
            logger.info(f"Generated comprehensive session summary")
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
            # Format session data for the prompt
            formatted_data = self._format_session_data(session_data)
            
            # Create the summary chain
            chain = self.session_summary_prompt | self.llm | self.json_parser
            
            # Execute summary generation synchronously
            result = chain.invoke({
                "session_data": formatted_data
            })
            
            logger.info(f"Generated comprehensive session summary (sync)")
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