### **PRD: LangGraph-basierter Anamnese-Bot**

**1. Überblick**
Das Ziel ist die Refaktorierung der Kernlogik des Chatbots von der aktuellen klassenbasierten Implementierung zu einer graphenbasierten Architektur mit LangGraph. Diese Änderung soll die Modularität, das Zustandsmanagement und die Nachvollziehbarkeit des Gesprächsflusses verbessern.

**2. Funktionale Anforderungen**
*   **F-1: Graphenbasierter Gesprächsfluss:** Die gesamte Gesprächslogik wird als LangGraph-Graph modelliert.
*   **F-2: Zustandsmanagement:** Das LangGraph-Zustandsobjekt (`State`) wird die alleinige Quelle der Wahrheit für den Gesprächszustand sein (Nachrichtenverlauf, LLM-Antworten etc.). Das FastAPI-Backend fungiert als dünner Wrapper um den Graphen.
*   **F-3: Sequenzieller Prozess:** Die erste Implementierung wird ein einfacher, sequenzieller Graph sein, der den Ablauf abbildet: `Benutzereingabe` -> `Anamnesefrage generieren` -> `Ausgabe`.
*   **F-4: Integrierte Fehlerbehandlung:** Der Graph wird Knoten enthalten, um Fehler während der Ausführung (z. B. LLM-API-Fehler) abzufangen und zu behandeln.
*   **F-5: Debug-Modus (Extern):** Die bestehende Debug-Funktionalität bleibt erhalten. Das Backend pausiert den Prozess *vor* der Ausführung eines Knotens, um Debug-Informationen an das Frontend zu senden und auf das "Weiter"-Signal zu warten.

**3. Implementierungsplan (MVP)**
Der Plan folgt Ihrer Wahl (5d): Wir erstellen zuerst einen Proof of Concept (PoC) in einer separaten Datei. Sobald dieser funktioniert, wird er in die Hauptanwendung integriert und ersetzt die alte Logik. 