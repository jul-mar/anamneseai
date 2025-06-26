# backend/main.py
from fasthtml.common import *
from fasthtml.fastapp import *
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

# Importiere Logik aus der ursprünglichen Datei. Dies wird später refaktorisiert.
from questionnAIre import SessionManager, _trigger_initial_bot_action, handle_bot_turn

app = FastHTML()
rt = app.route

# Ein einfacher In-Memory-Speicher für Sitzungen für die Entwicklung.
SESSIONS = {}

# Füge die CORS-Middleware hinzu, um Anfragen vom Frontend zu erlauben.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@rt("/api/session/start", methods=["POST"])
async def start_session():
    """
    Initialisiert eine neue Chat-Sitzung, speichert sie serverseitig
    und gibt die Sitzungs-ID sowie die ersten Nachrichten zurück.
    """
    session_data = {}
    SessionManager.initialize_session(session_data)
    
    session_id = session_data['session_id']
    SESSIONS[session_id] = session_data

    # Triggert die erste Aktion des Bots (z.B. die erste Frage vorbereiten)
    await _trigger_initial_bot_action(session_data)

    # Wenn der Debug-Modus nicht aktiv ist, stellt der Bot sofort die erste Frage.
    if not session_data.get('debug_mode_enabled') and session_data.get('bot_state') == "WAITING_TO_ASK_PREDEFINED":
        await handle_bot_turn(session_data, user_message_content=None)

    # Gebe den Anfangszustand an das Frontend zurück.
    return JSONResponse({
        "session_id": session_id,
        "messages": session_data.get('chat_messages', [])
    })

@rt("/api/chat", methods=["POST"])
async def post_chat(request: Request):
    """
    Verarbeitet eine einzelne Benutzernachricht für eine bestehende Sitzung
    und gibt die daraus resultierenden neuen Chat-Nachrichten zurück.
    """
    try:
        data = await request.json()
        session_id = data.get("session_id")
        user_message = data.get("user_message")

        if not session_id or not user_message:
            return JSONResponse({"error": "session_id and user_message are required"}, status_code=400)

        session_data = SESSIONS.get(session_id)
        if not session_data:
            return JSONResponse({"error": "Session not found"}, status_code=404)

        # Merken, wie viele Nachrichten wir vor diesem Turn hatten.
        messages_before_count = len(session_data.get('chat_messages', []))

        # Die ursprüngliche Funktion `post_chat_message` hat die Bot-Logik angestoßen.
        # Wir replizieren diesen Teil hier, aber geben JSON statt UI-Komponenten zurück.
        
        # 1. Benutzernachricht zur Konversation hinzufügen
        SessionManager.add_message_to_display_chat(session_data, "user", user_message)
        
        # 2. Den Bot den Zug ausführen lassen (dies modifiziert session_data)
        await handle_bot_turn(session_data, user_message_content=user_message)

        # 3. Nur die neuen Nachrichten zurückgeben, die in diesem Turn entstanden sind.
        new_messages = session_data.get('chat_messages', [])[messages_before_count:]

        return JSONResponse({
            "messages": new_messages
        })
    except Exception as e:
        # Grundlegendes Error-Handling
        print(f"Error in /api/chat: {e}")
        return JSONResponse({"error": "An internal error occurred"}, status_code=500)

@rt("/api/session/restart", methods=["POST"])
async def restart_session(request: Request):
    """
    Setzt eine bestehende Sitzung zurück oder erstellt eine neue,
    falls die ID nicht existiert.
    """
    data = await request.json()
    session_id = data.get("session_id")

    if session_id and session_id in SESSIONS:
        del SESSIONS[session_id]

    # Nach dem Löschen (oder wenn keine ID gesendet wurde),
    # einfach eine neue Sitzung starten und zurückgeben.
    return await start_session()

@rt("/api/debug/toggle", methods=["POST"])
async def toggle_debug(request: Request):
    """
    Schaltet den Debug-Modus für eine Sitzung um und gibt den neuen
    Status zurück.
    """
    data = await request.json()
    session_id = data.get("session_id")

    if not session_id or session_id not in SESSIONS:
        return JSONResponse({"error": "Session not found"}, status_code=404)
    
    session_data = SESSIONS[session_id]
    current_status = session_data.get('debug_mode_enabled', False)
    new_status = not current_status
    session_data['debug_mode_enabled'] = new_status

    return JSONResponse({"debug_mode_enabled": new_status})

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 