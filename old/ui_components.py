# ui_components.py
from fasthtml.common import *
import uuid

# --- Application Headers and Global Styles ---
# Moved Style from app.py into hdrs for better organization
hdrs = (
    Script(src="https://cdn.tailwindcss.com"),
    Script(src="https://unpkg.com/htmx.org@1.9.10"),
    Script(src="https://unpkg.com/htmx.org@1.9.10/dist/ext/loading-states.js"),
    Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.10.1/dist/full.min.css"),
    Script("""
    tailwind.config = {
      theme: {
        extend: {
          colors: { 'medical-blue': '#0077b6', 'medical-blue-light': '#90e0ef', 'medical-blue-dark': '#03045e' }
        }
      }
    }
    """, type="text/javascript"),
    Script("""
    document.addEventListener('DOMContentLoaded', function() {
        htmx.config.useTemplateFragments = true;
        htmx.config.indicatorClass = 'htmx-indicator';
        htmx.config.requestClass = 'htmx-request';
    });
    """, type="text/javascript"),
    Style("""
        body { background-color: #f8fafc; font-family: 'Inter', sans-serif; }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #f1f5f9; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
        #loading-indicator { opacity: 0; transition: opacity 200ms ease-in; }
        #loading-indicator.processing { opacity: 1 !important; } /* Ensure visibility when processing */
        .htmx-request .htmx-indicator { opacity: 1 !important; }
    """)
)

# --- UI Components ---
def ChatMessage(message: dict):
    """
    Generates an HTML component for a single chat message.
    Args:
        message (dict): A dictionary containing message details (id, role, content).
    Returns:
        Div: A FastHTML Div component representing the chat message.
    """
    is_user = message.get("role") == "user"
    chat_alignment = "chat-end" if is_user else "chat-start"
    bubble_color = "bg-white text-gray-800" if is_user else "bg-medical-blue text-white"
    # Removed border_style for user messages to simplify, can be added back if desired
    # border_style = "border-l-4 border-medical-blue" if is_user else "" 
    border_style = "" # Default no specific border, can be enhanced

    if message.get("role") == "error":
        bubble_color = "bg-red-100 text-red-800"
        border_style = "border-l-4 border-red-500"
    
    message_content = message.get("content", "")
    avatar_initial = "P" if is_user else "A"
    avatar_bg = "bg-medical-blue-dark text-white" if is_user else "bg-white text-medical-blue-dark border border-medical-blue"
    
    avatar = Div(
        Div(Span(avatar_initial, cls="inline-flex items-center justify-center w-full h-full"), 
            cls=f"w-8 h-8 rounded-full {avatar_bg} flex items-center justify-center text-sm font-semibold shadow-sm"),
        cls="chat-image avatar"
    )
    role_label = "Patient" if is_user else "AnamneseAI"

    return Div(
        avatar,
        Div(role_label, cls="chat-header text-xs font-medium mb-1 text-gray-600"),
        Div(P(message_content), cls=f"chat-bubble shadow-sm {bubble_color} {border_style} break-words prose prose-sm sm:prose-base rounded-lg px-4 py-3"),
        cls=f"chat {chat_alignment}", id=f"message-{message.get('id', uuid.uuid4())}"
    )

def ChatInterface(messages: list = None, actual_model_name: str = "N/A", actual_eval_model_name: str = "N/A"):
    """
    Generates the main chat interface HTML structure.
    Args:
        messages (list, optional): A list of message dictionaries to display. Defaults to None.
        actual_model_name (str): Name of the main LLM being used.
        actual_eval_model_name (str): Name of the evaluation LLM being used.
    Returns:
        Div: A FastHTML Div component representing the entire chat interface.
    """
    chat_messages_components = [ChatMessage(msg) for msg in messages] if messages else []
    
    chat_box = Div(*chat_messages_components, id="chat-box",
        cls="p-4 space-y-6 overflow-y-auto h-[calc(100vh-220px)] bg-white rounded-lg shadow-md border border-gray-200")

    user_input = Input(id="user-message-input", type="text", name="user_message",
        placeholder="Ihre Antwort...",
        cls="input bg-white border border-gray-300 focus:border-medical-blue focus:ring-2 focus:ring-medical-blue-light w-full flex-grow mr-2 rounded-lg",
        autofocus=True)
    submit_button = Button("Senden", type="submit",
        cls="bg-medical-blue hover:bg-medical-blue-dark text-white font-medium py-2 px-6 rounded-lg transition-colors duration-200")
    
    # Loading indicator, ensuring it becomes visible during htmx requests
    loading_indicator = Div(
        Div(_innerHTML="""<svg class="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>""",
            cls="inline-block"),
        Span("Verarbeite...", cls="text-sm font-medium"),
        id="loading-indicator", 
        # The class 'htmx-indicator' is automatically handled by htmx to toggle visibility
        # We ensure it starts hidden and transitions smoothly.
        cls="htmx-indicator flex items-center text-medical-blue ml-2 opacity-0 transition-opacity duration-300", 
    )

    chat_form = Form(user_input, submit_button, loading_indicator, 
        hx_post="/chat", hx_target="#chat-box",
        hx_swap="beforeend", 
        hx_indicator="#loading-indicator", # Points to the loading indicator
        # hx_ext="loading-states", # This extension can simplify state handling on buttons etc.
        # For the indicator itself, htmx-indicator class is key.
        # The loading-states extension might be useful for disabling the button or changing its text.
        # For now, the global indicator is the primary focus.
        # data_loading_delay="100", # Delays showing indicator
        # data_loading_target="#loading-indicator", # Redundant if using hx_indicator
        # data_loading_class_remove="opacity-0", # This would be for loading-states on the form itself
        
        # Ensure chat scrolls to bottom after new messages are added and processed by HTMX
        # hx_on_htmx_after_on_load: This event fires after content from an hx-target has been loaded and processed.
        # hx_on_htmx_after_settle: This event fires after the hx-swap has completed and the DOM is settled.
        # Using after-settle is often more reliable for scrolling.
        hx_on_htmx_after_settle="htmx.find('#chat-box').scrollTop = htmx.find('#chat-box').scrollHeight",
        cls="p-4 flex items-center bg-gray-50 rounded-lg shadow-sm mt-4 sticky bottom-0 border border-gray-200")
    
    header = Div(
        Div(
            Div(_innerHTML="""<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-medical-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>""", cls="mr-3"),
            Div(H1("AnamneseAI", cls="text-2xl font-bold text-medical-blue-dark"), P("Patientenbefragung", cls="text-sm text-gray-600"), cls="flex flex-col"),
            cls="flex items-center mb-2"
        ),
        Div(cls="w-full h-px bg-gray-200 mb-4"),
        Div(
            Div(_innerHTML="""<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>""", cls="text-medical-blue"),
            Span(f"Modell: {actual_model_name} (Eval: {actual_eval_model_name})", cls="text-xs text-gray-600"),
            cls="flex items-center justify-end mb-4"
        ),
        cls="bg-white rounded-lg shadow-sm p-4 mb-4 border border-gray-200"
    )
    return Div(header, chat_box, chat_form, cls="container mx-auto max-w-3xl p-4 flex flex-col h-screen font-sans bg-gray-50")

def InputToClear(target_id: str = "user-message-input"):
    """
    Returns an Input component designed to clear the user input field via HTMX OOB swap.
    Args:
        target_id (str): The ID of the input field to clear.
    Returns:
        Input: A FastHTML Input component.
    """
    return Input(id=target_id, name="user_message", placeholder="Ihre Antwort...",
                 cls="input bg-white border border-gray-300 focus:border-medical-blue focus:ring-2 focus:ring-medical-blue-light w-full flex-grow mr-2 rounded-lg",
                 hx_swap_oob="true", value="", autofocus=True)
