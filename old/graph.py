import os
import json
from typing import TypedDict, Annotated
import operator

from langchain_core.messages import AnyMessage, HumanMessage
from dotenv import load_dotenv
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

def load_prompt(file_name: str) -> str:
    """Loads a prompt from the prompts directory."""
    prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', file_name)
    with open(prompt_path, 'r') as f:
        return f.read().strip()

load_dotenv()

class GraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        messages: The list of exchanged messages.
    """
    messages: Annotated[list[AnyMessage], operator.add]

def load_config():
    """Loads the configuration from the config.json file."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    if not os.path.exists(config_path):
        # Fallback to backend/config.json if the above construction fails
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')

    with open(config_path, 'r') as f:
        return json.load(f)

def create_anamnesis_graph():
    """
    Creates and compiles the LangGraph graph for the medical history.

    Returns:
        A compiled LangGraph application.
    """
    # Load the configuration
    config = load_config()
    provider = config.get("provider", "huggingface")
    model_name = config.get("model_name", "meta-llama/Llama-3.1-8B-Instruct")
    
    # Initialize the model based on the provider
    if provider == "openai":
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")
        
        openai_config = config.get("openai", {})
        model = ChatOpenAI(
            model=model_name,
            api_key=openai_api_key,
            temperature=openai_config.get("temperature", 0.7),
            max_tokens=openai_config.get("max_tokens", 1000)
        )
    elif provider == "huggingface":
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            raise ValueError("HF_TOKEN not found in environment variables.")
        
        hf_config = config.get("huggingface", {})
        
        # Create the endpoint first
        llm = HuggingFaceEndpoint(  # type: ignore[arg-type]
            repo_id=model_name,
            huggingfacehub_api_token=hf_token,
            task="text-generation",
            max_new_tokens=hf_config.get("max_tokens", 512),
            temperature=hf_config.get("temperature", 0.7)
        )

        # Wrap the LLM in a chat model
        model = ChatHuggingFace(llm=llm)
    else:
        raise ValueError(f"Unsupported provider: {provider}. Supported providers are: openai, huggingface")

    # Load the system prompt from the file
    system_prompt = load_prompt("system_prompt.txt")

    # The prompt template now expects the entire message history
    # and an additional `user_input` variable, which remains empty here,
    # since the new messages are contained in the `messages` array.
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            # Variable that captures the previous chat history
            ("placeholder", "{messages}"),
        ]
    )

    # Chain of prompt and model
    chain = prompt | model

    def generate_question_node(state: GraphState):
        """
        Generates the next medical history question based on the current conversation state.
        """
        # Pass the entire message history to the chain
        response = chain.invoke({"messages": state["messages"]})
        # Add only the new response to the state
        return {"messages": [response]}

    # Define the workflow
    workflow = StateGraph(GraphState)
    workflow.add_node("generate_question", generate_question_node)
    workflow.set_entry_point("generate_question")
    workflow.add_edge("generate_question", END)

    # Compile the graph with a checkpointer and return it
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)

# Create a global instance of the graph for the application
anamnesis_graph = create_anamnesis_graph() 