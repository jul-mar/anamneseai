from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda

# LLMs definieren
llm_eval = ChatOpenAI(model="gpt-4-turbo", temperature=0)
llm_reform = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)

# Memory
memory = ConversationBufferMemory(return_messages=True, memory_key="history")

# Konversationskette mit Memory für regulären Botflow
conversation_chain = ConversationChain(llm=llm_eval, memory=memory)

# Zustandsklasse
class ChatState(dict):
    pass
def ask_first_question(state: ChatState) -> ChatState:
    prompt = "Stelle eine einfache, offene Frage, um ein Gespräch mit einem Nutzer zu beginnen."

    response = llm_reform.invoke([
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Beginne eine Unterhaltung mit einer freundlichen Frage."}
    ])

    question = response.content.strip()
    memory.chat_memory.add_ai_message(question)

    print("🤖 Erste Frage:", question)
    return {**state, "last_bot_question": question}


def evaluate_input(state: ChatState) -> ChatState:
    user_input = state["user_input"]
    question = state["last_bot_question"]

    system_prompt = "Beurteile, ob die folgende Antwort sinnvoll zur Frage passt. Antworte mit 'Ja' oder 'Nein'."

    response = llm_eval.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Frage: {question}\nAntwort: {user_input}"}
    ])

    is_valid = "ja" in response.content.lower()
    return {**state, "eval_result": is_valid}


def continue_flow(state: ChatState) -> ChatState:
    user_input = state["user_input"]
    memory.chat_memory.add_user_message(user_input)

    response = conversation_chain.run(user_input)
    memory.chat_memory.add_ai_message(response)

    print("🤖 Bot-Antwort:", response)
    return {**state, "last_bot_question": response}


def reformulate_question(state: ChatState) -> ChatState:
    original = state["last_bot_question"]
    prompt = "Formuliere die folgende Frage klarer und verständlicher."

    response = llm_reform.invoke([
        {"role": "system", "content": prompt},
        {"role": "user", "content": original}
    ])

    return {**state, "reformulated_question": response.content.strip()}


def ask_again(state: ChatState) -> ChatState:
    reformulated = state["reformulated_question"]
    memory.chat_memory.add_ai_message(reformulated)

    print("🤖 Reformulierte Frage:", reformulated)
    return {**state, "last_bot_question": reformulated}


def route_eval(state: ChatState) -> str:
    return "continue_flow" if state["eval_result"] else "reformulate_question"


builder = StateGraph(ChatState)

builder.add_node("ask_first_question", RunnableLambda(ask_first_question))
builder.add_node("evaluate_input", RunnableLambda(evaluate_input))
builder.add_node("continue_flow", RunnableLambda(continue_flow))
builder.add_node("reformulate_question", RunnableLambda(reformulate_question))
builder.add_node("ask_again", RunnableLambda(ask_again))

# Startpunkt: erste Frage stellen
builder.set_entry_point("ask_first_question")
builder.add_edge("ask_first_question", "evaluate_input")

# Hauptverzweigung: Antwort evaluieren
builder.add_conditional_edges("evaluate_input", route_eval)

# Bei validem Input → weiter im Flow
builder.add_edge("continue_flow", END)

# Bei invalider Antwort → Frage umformulieren → erneut fragen
builder.add_edge("reformulate_question", "ask_again")
builder.add_edge("ask_again", "evaluate_input")

# Kompilieren
graph = builder.compile()
