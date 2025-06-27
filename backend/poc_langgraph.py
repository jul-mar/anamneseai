import os
from typing import TypedDict, Annotated
import operator

from langchain_core.messages import AnyMessage, HumanMessage
from dotenv import load_dotenv
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

load_dotenv()

hf_token = os.environ.get("HF_TOKEN")
if not hf_token:
    raise ValueError("HF_TOKEN not found in environment variables.")

# Erstelle zuerst den Endpoint
llm_endpoint = HuggingFaceEndpoint(
    repo_id="mistralai/Mistral-7B-Instruct-v0.3",
    huggingfacehub_api_token=hf_token,
    task="text-generation",
)

# Initialisiere das Chat-Modell mit dem Endpoint
model = ChatHuggingFace(llm=llm_endpoint)

# Definiere eine Prompt-Vorlage für die Generierung der Frage
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Du bist ein medizinischer Assistent. Deine Aufgabe ist es, eine Anamnese durchzuführen. Stelle dem Benutzer relevante Fragen zu seinem Gesundheitszustand. Halte deine Fragen kurz und prägnant."),
        ("human", "{user_input}"),
    ]
)

# Kette aus Prompt und Modell
chain = prompt | model

class GraphState(TypedDict):
    """
    Stellt den Zustand unseres Graphen dar.

    Attribute:
        messages: Die Liste der ausgetauschten Nachrichten.
    """
    messages: Annotated[list[AnyMessage], operator.add]

def generate_question_node(state: GraphState):
    """
    Generiert die nächste Anamnesefrage basierend auf dem aktuellen Gesprächszustand.

    Args:
        state: Der aktuelle Zustand des Graphen.

    Returns:
        Ein Dictionary, das die neu generierte Nachricht des Assistenten enthält.
    """
    # Rufe die letzte Nachricht aus dem Zustand ab
    last_message = state["messages"][-1].content
    
    # Rufe das LLM auf, um eine Antwort zu generieren
    response = chain.invoke({"user_input": last_message})
    
    # Gib die Antwort als neue Nachricht zurück, die zum Zustand hinzugefügt wird
    return {"messages": [response]}

# Definiere den Workflow
workflow = StateGraph(GraphState)

# Füge den Knoten zum Graphen hinzu
workflow.add_node("generate_question", generate_question_node)

# Setze den Einstiegspunkt
workflow.set_entry_point("generate_question")

# Füge eine Kante vom Generierungsknoten zum Ende hinzu, um einen einfachen Ablauf zu erstellen
workflow.add_edge("generate_question", END)

# Kompiliere den Graphen zu einer aufrufbaren Anwendung
app = workflow.compile()

if __name__ == "__main__":
    # Definiere den initialen Zustand mit einer ersten Benutzernachricht
    initial_state = {"messages": [HumanMessage(content="Hallo, ich habe seit gestern Kopfschmerzen.")]}
    
    # Führe den Graphen aus
    final_state = app.invoke(initial_state)
    
    # Gib die letzte Nachricht aus, die vom Assistenten generiert wurde
    print("--- POC - ANTWORT DES ASSISTENTEN ---")
    print(final_state['messages'][-1].content)
    print("------------------------------------") 