## Relevant Files

- `backend/poc_langgraph.py` - Temporäre Datei für den Proof of Concept des LangGraph-Graphen.
- `backend/graph.py` - Finale Datei, die die Logik und die Struktur des LangGraph-Graphen enthalten wird.
- `backend/requirements.txt` - Wird um die neuen Abhängigkeiten `langchain`, `langgraph` und `langchain_groq` erweitert.
- `backend/main.py` - Haupt-API-Datei. Muss angepasst werden, um die `Chatbot`-Klasse durch den LangGraph-Graphen zu ersetzen.
- `backend/core.py` - Enthält die alte `Chatbot`-Klasse, die entfernt werden wird.
- `README.md` - Muss aktualisiert werden, um die neue Architektur zu beschreiben.

### Notes

- Der Implementierungsplan sieht vor, zuerst einen isolierten Proof of Concept (PoC) zu erstellen. Sobald dieser funktioniert, wird er in die Hauptanwendung integriert.

## Tasks

- [x] 1.0 Proof of Concept (PoC) in einer separaten Datei erstellen
  - [x] 1.1 Neue Datei `backend/poc_langgraph.py` erstellen.
  - [x] 1.2 `langgraph`, `langchain` und `langchain_groq` zu `backend/requirements.txt` hinzufügen und die Installation durchführen.
  - [x] 1.3 Einen Graphen-Zustand (`GraphState` als TypedDict) definieren, der den Gesprächsverlauf und andere relevante Daten enthält.
  - [x] 1.4 Die Graphen-Knoten als Python-Funktionen implementieren (z.B. ein Knoten zur Generierung der nächsten Frage).
  - [x] 1.5 Die Graphen-Struktur mit `StateGraph` definieren, indem die Knoten und die Kanten (Ablauflogik) hinzugefügt werden.
  - [x] 1.6 Den Graphen kompilieren (`workflow.compile()`).
  - [x] 1.7 Einen Test-Block (`if __name__ == "__main__"`) hinzufügen, um den Graphen isoliert auszuführen und die Funktionalität zu überprüfen.
- [x] 2.0 Integration des PoC in die Backend-Anwendung
  - [x] 2.1 Die PoC-Logik in eine neue Datei `backend/graph.py` verschieben.
  - [x] 2.2 In `backend/main.py` die Logik zur Verwaltung von Sessions anpassen, um pro Session eine Graphen-Instanz statt einer `Chatbot`-Instanz zu speichern.
  - [x] 2.3 Den `/api/session/start`-Endpunkt so anpassen, dass eine neue, kompilierte Graphen-Instanz erstellt wird.
  - [x] 2.4 Den `/api/chat`-Endpunkt so anpassen, dass die Benutzereingabe an die korrekte Graphen-Instanz übergeben und der Graph ausgeführt wird.
- [x] 3.0 Entfernen der alten Logik und Aufräumarbeiten
  - [x] 3.1 Die `Chatbot`-Klasse und zugehörige Funktionen aus `backend/core.py` vollständig entfernen.
  - [x] 3.2 Die temporäre PoC-Datei `backend/poc_langgraph.py` löschen.
  - [x] 3.3 Alle nicht mehr benötigten Imports in `backend/main.py` und anderen Dateien entfernen.
- [ ] 4.0 Anpassung des Debug-Modus für LangGraph
  - [x] 4.1 Den `/api/debug/continue`-Endpunkt anpassen, sodass er mit dem Zustand des LangGraph-Graphen interagiert.
  - [x] 4.2 Sicherstellen, dass der Graph im Debug-Modus pausieren kann, den Zustand an das Frontend sendet und auf das "Weiter"-Signal wartet.
- [x] 5.0 Dokumentation aktualisieren und abschließen
  - [x] 5.1 Die `README.md` überarbeiten, um die neue, auf LangGraph basierende Architektur zu erklären.
  - [x] 5.2 Sicherstellen, dass die Installations- und Startanweisungen noch korrekt sind. 