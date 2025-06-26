## Relevante Dateien

- `backend/main.py` - Neuer Haupteinstiegspunkt für das Backend, der die `fasthtml`-Anwendung konfiguriert und startet.
- `backend/core.py` - Enthält die refaktorisierte Kernlogik (z.B. `LLMService`, `SessionManager`), die vom API-Layer getrennt ist.
- `frontend/index.html` - Die Haupt-HTML-Datei für das Frontend.
- `frontend/app.js` - JavaScript-Code für die Interaktion mit der Backend-API und die Aktualisierung der Benutzeroberfläche.
- `frontend/style.css` - CSS-Stile für das Frontend.
- `README.md` - Wird aktualisiert, um die neue Startanleitung für die getrennten Dienste zu enthalten.

### Hinweise

- Die Aufteilung des Backends in `main.py` (für die API) und `core.py` (für die Logik) ist eine Empfehlung für sauberen Code.
- Das Frontend sollte so entwickelt werden, dass es mit einem einfachen `python -m http.server` aus dem `frontend`-Verzeichnis ausgeführt werden kann.

## Aufgaben

- [ ] 1.0 Projektstruktur und Backend-Grundgerüst einrichten
  - [ ] 1.1 Erstelle die Hauptverzeichnisse: `backend/` und `frontend/`.
  - [ ] 1.2 Verschiebe `questionnAIre.py`, `config.json`, `questions.json` und `requirements.txt` in das `backend/`-Verzeichnis.
  - [ ] 1.3 Erstelle eine neue `backend/main.py`, die die `fasthtml`-App initialisiert.
  - [ ] 1.4 Konfiguriere CORS in `backend/main.py`, um Anfragen vom Frontend zu erlauben (wird auf einem anderen Port laufen).
  - [ ] 1.5 Erstelle eine einfache `frontend/index.html` als Platzhalter.

- [ ] 2.0 API-Endpunkte im Backend implementieren
  - [ ] 2.1 Erstelle einen `POST /api/session/start`-Endpunkt, der eine neue Chat-Sitzung initialisiert und die erste Begrüßungsnachricht zurückgibt.
  - [ ] 2.2 Erstelle einen `POST /api/chat`-Endpunkt, der eine Benutzernachricht und eine Sitzungs-ID entgegennimmt und die Antwort des Bots zurückgibt.
  - [ ] 2.3 Erstelle einen `POST /api/session/restart`-Endpunkt, um die Konversation neu zu starten.
  - [ ] 2.4 Erstelle einen `POST /api/debug/toggle`-Endpunkt zum Umschalten des Debug-Modus.
  - [ ] 2.5 Stelle sicher, dass alle Endpunkte JSON-Objekte zurückgeben und nicht HTML.

- [ ] 3.0 Backend-Logik refaktorisieren und UI-Code entfernen
  - [ ] 3.1 Lösche die `UIComponents`-Klasse und alle ihre Aufrufe aus dem Backend-Code.
  - [ ] 3.2 Entferne jeglichen Code, der `fasthtml`-Komponenten (wie `Div`, `Button`, `Form`) direkt generiert.
  - [ ] 3.3 Trenne die Kernlogik (z.B. `SessionManager`, `LLMService`, `QuestionService`) vom API-Handling. Es wird empfohlen, diese Logik in eine separate `backend/core.py` zu verschieben.
  - [ ] 3.4 Passe die Logik so an, dass sie nur noch Daten verarbeitet und den Status verwaltet, anstatt UI-Komponenten zu erstellen.

- [ ] 4.0 Statisches Frontend erstellen
  - [ ] 4.1 Baue in `frontend/index.html` die grundlegende Seitenstruktur mit einem Chat-Container und einem Eingabeformular auf.
  - [ ] 4.2 Erstelle in `frontend/app.js` Funktionen, um die neuen Backend-API-Endpunkte über `fetch` oder `htmx` aufzurufen.
  - [ ] 4.3 Implementiere die Logik, um bei erfolgreicher Antwort des Backends dynamisch neue Chat-Nachrichten in der UI darzustellen.
  - [ ] 4.4 Binde die Funktionalität für den "Neustart"- und "Debug"-Button an die entsprechenden API-Aufrufe.
  - [ ] 4.5 Übertrage die bestehenden CSS-Stile in eine separate `frontend/style.css`.

- [ ] 5.0 Dokumentation und Abschluss
  - [ ] 5.1 Aktualisiere die `README.md` mit klaren Anweisungen, wie man den Backend-Server und den Frontend-Server getrennt startet.
  - [ ] 5.2 Führe End-to-End-Tests durch, um sicherzustellen, dass die Anwendung für den Endbenutzer genau wie zuvor funktioniert.
  - [ ] 5.3 Entferne alle nicht mehr benötigten alten Dateien oder Code-Strukturen. 