import os
import json
from typing import TypedDict, Annotated
import operator

from langchain_core.messages import AnyMessage, HumanMessage
from dotenv import load_dotenv
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

class GraphState(TypedDict):
    """
    Stellt den Zustand unseres Graphen dar.

    Attribute:
        messages: Die Liste der ausgetauschten Nachrichten.
    """
    messages: Annotated[list[AnyMessage], operator.add]

def load_config():
    """Lädt die Konfiguration aus der config.json-Datei."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    if not os.path.exists(config_path):
        # Fallback auf backend/config.json wenn die obige Konstruktion fehlschlägt
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')

    with open(config_path, 'r') as f:
        return json.load(f)

def create_anamnesis_graph():
    """
    Erstellt und kompiliert den LangGraph-Graphen für die Anamnese.

    Returns:
        Eine kompilierte LangGraph-Anwendung.
    """
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise ValueError("HF_TOKEN not found in environment variables.")

    # Lade die Konfiguration
    config = load_config()
    model_name = config.get("model_name", "meta-llama/Llama-3.1-8B-Instruct")
    hf_config = config.get("huggingface", {})
    
    # Erstelle zuerst den Endpoint
    llm = HuggingFaceEndpoint(  # type: ignore[arg-type]
        repo_id=model_name,
        huggingfacehub_api_token=hf_token,
        task="text-generation",
        max_new_tokens=hf_config.get("max_tokens", 512),
        temperature=hf_config.get("temperature", 0.7)
    )

    # Wickle den LLM in ein Chat-Modell ein
    model = ChatHuggingFace(llm=llm)

    # Definiere eine Prompt-Vorlage für die Generierung der Frage
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "Du bist ein medizinischer Assistent. Deine Aufgabe ist es, eine Anamnese durchzuführen. Stelle dem Benutzer relevante Fragen zu seinem Gesundheitszustand. Halte deine Fragen kurz und prägnant."),
            ("human", "{user_input}"),
        ]
    )

    # Kette aus Prompt und Modell
    chain = prompt | model

    def generate_question_node(state: GraphState):
        """
        Generiert die nächste Anamnesefrage basierend auf dem aktuellen Gesprächszustand.
        """
        last_message = state["messages"][-1].content
        response = chain.invoke({"user_input": last_message})
        return {"messages": [response]}

    # Definiere den Workflow
    workflow = StateGraph(GraphState)
    workflow.add_node("generate_question", generate_question_node)
    workflow.set_entry_point("generate_question")
    workflow.add_edge("generate_question", END)

    # Kompiliere den Graphen mit einem Checkpointer und gib ihn zurück
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

# Erstelle eine globale Instanz des Graphen für die Anwendung
anamnesis_graph = create_anamnesis_graph() 