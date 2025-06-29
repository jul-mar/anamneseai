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

def load_prompt(file_name: str) -> str:
    """Lädt einen Prompt aus dem prompts-Verzeichnis."""
    prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', file_name)
    with open(prompt_path, 'r') as f:
        return f.read().strip()

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

    # Lade den System-Prompt aus der Datei
    system_prompt = load_prompt("system_prompt.txt")

    # Das Prompt-Template erwartet jetzt den gesamten Nachrichtenverlauf
    # und eine zusätzliche `user_input` Variable, die hier leer bleibt,
    # da die neuen Nachrichten im `messages` Array enthalten sind.
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            # Variable, die den bisherigen Chatverlauf aufnimmt
            ("placeholder", "{messages}"),
        ]
    )

    # Kette aus Prompt und Modell
    chain = prompt | model

    def generate_question_node(state: GraphState):
        """
        Generiert die nächste Anamnesefrage basierend auf dem aktuellen Gesprächszustand.
        """
        # Übergib den gesamten Nachrichtenverlauf an die Kette
        response = chain.invoke({"messages": state["messages"]})
        # Füge nur die neue Antwort zum Zustand hinzu
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