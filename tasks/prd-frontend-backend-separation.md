# PRD: Trennung von Frontend und Backend

## 1. Einführung & Überblick

**Problem:** Aktuell ist die Anwendung ein Monolith, bei dem der Python-Backend-Code (in `questionnAIre.py`) eng mit der Frontend-Generierung (FastHTML, `UIComponents`-Klasse) gekoppelt ist. Diese enge Kopplung erschwert die Wartung, das Verständnis des Codes und zukünftige Weiterentwicklungen.

**Ziel:** Das Hauptziel dieser Initiative ist es, die Code-Übersichtlichkeit zu erhöhen, indem wir eine klare Trennung zwischen dem Frontend (Benutzeroberfläche) und dem Backend (Anwendungslogik) schaffen.

## 2. Ziele

*   **Strukturierte Trennung:** Die Anwendung wird in zwei separate Komponenten aufgeteilt: ein Python-Backend, das eine API bereitstellt, und ein reines Frontend, das diese API konsumiert.
*   **Verbesserte Wartbarkeit:** Durch die klare Trennung und einen definierten API-Vertrag wird die Codebasis leichter verständlich und einfacher zu warten sein.
*   **Unabhängige Entwicklung:** Ermöglichen des unabhängigen lokalen Starts von Frontend und Backend, um die Entwicklungs-Workflows zu vereinfachen.

## 3. User Stories (Entwickler-Perspektive)

*   **Als Entwickler** möchte ich am Frontend arbeiten können, ohne den gesamten Python-Backend-Stack ausführen zu müssen, um die UI-Entwicklung zu beschleunigen.
*   **Als Entwickler** möchte ich einen klaren API-Vertrag (definiert durch Endpunkte), um den Datenfluss zwischen Frontend und Backend nachvollziehen und debuggen zu können.
*   **Als Entwickler** möchte ich, dass das Backend UI-agnostisch ist, damit das Frontend-Framework in Zukunft ohne größere Umbauten am Backend ausgetauscht werden kann.

## 4. Funktionale Anforderungen

1.  **Verzeichnisstruktur:** Es wird eine neue Verzeichnisstruktur eingeführt, die Frontend- und Backend-Code klar voneinander trennt.
2.  **REST-API:** Das Backend muss eine RESTful-API bereitstellen, die ausschließlich JSON als Kommunikationsformat verwendet. Alle bestehenden Funktionen (Chat starten, Nachrichten senden, Zustandsänderungen) müssen über diese API abgebildet werden.
3.  **API-Präfix:** Alle API-Endpunkte müssen unter dem Präfix `/api/` erreichbar sein (z.B. `/api/chat`, `/api/restart_chat`).
4.  **Backend-Säuberung:** Die `UIComponents`-Klasse und jeglicher anderer FastHTML-Code zur Generierung von UI-Elementen müssen vollständig aus dem Python-Backend entfernt werden.
5.  **Frontend-Implementierung:** Das Frontend wird als statische Single-Page-Anwendung (SPA) mit HTML, CSS und JavaScript (HTMX kann weiterhin verwendet werden) neu aufgebaut. Es ist allein für die Darstellung der UI und die Kommunikation mit der Backend-API zuständig.
6.  **1:1-Refaktorierung:** Die Benutzeroberfläche und die Funktionalität müssen exakt dem aktuellen Stand entsprechen. Es werden in dieser Phase keine neuen Features oder UI-Änderungen eingeführt.
7.  **Lokales Setup:** Die lokale Entwicklungsumgebung muss es ermöglichen, den Frontend-Server und den Backend-Server als zwei separate Prozesse zu starten. Eine Anleitung hierzu muss in der `README.md` dokumentiert werden.
8.  **Keine UI-Logik im Backend:** Das Backend darf keine Logik enthalten, die sich auf die Darstellung der UI bezieht. Seine einzige Aufgabe ist die Verwaltung des Anwendungszustands, die Interaktion mit dem LLM und die Bereitstellung von Daten über die API.

## 5. Non-Goals (Außerhalb des Scopes)

*   Einführung eines neuen Frontend-Frameworks wie React, Vue oder Svelte.
*   Implementierung neuer Funktionen oder Änderungen am UI/UX-Design.
*   Einrichtung einer Produktions-Pipeline oder die Verwendung von Docker/docker-compose. Dies kann in einem späteren Schritt erfolgen.

## 6. Technische Überlegungen

*   Das Backend wird weiterhin `fasthtml` verwenden, um die JSON-basierten API-Endpunkte bereitzustellen. Obwohl unkonventionell, ist dies möglich und vermeidet die Einführung einer neuen Abhängigkeit.
*   Das Frontend kann von einem beliebigen einfachen HTTP-Server für statische Dateien bereitgestellt werden.
*   Auf dem Backend muss CORS (Cross-Origin Resource Sharing) konfiguriert werden, um API-Anfragen vom Frontend (das auf einem anderen Port läuft) zu erlauben.

## 7. Erfolgskriterien

1.  Die `UIComponents`-Klasse existiert nicht mehr im Python-Code.
2.  Die gesamte Kommunikation zwischen Browser und Server erfolgt über JSON-basierte API-Endpunkte unter `/api/`.
3.  Das Frontend kann eigenständig mit einem Mock-API-Server für Entwicklungszwecke betrieben werden.
4.  Die End-to-End-Funktionalität der Anwendung ist für den Endbenutzer unverändert.

## 8. Offene Fragen

*   **Entscheidung:** Das Projekt wird weiterhin `fasthtml` verwenden. 