# backend/main.py
from fasthtml.common import *
from fasthtml.fastapp import *
import uvicorn
from starlette.middleware.cors import CORSMiddleware

# Wir importieren die gesamte Anwendungslogik aus der umbenannten Datei.
# Später wird dies in `core.py` aufgeteilt.
from questionnAIre import app as backend_app

app = backend_app

# Füge die CORS-Middleware hinzu
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Erlaube alle Ursprünge für die Entwicklung
    allow_credentials=True,
    allow_methods=["*"],  # Erlaube alle Methoden (GET, POST, etc.)
    allow_headers=["*"],  # Erlaube alle Header
)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 