# PRD: Migration zur Hugging Face Inference API mit einfachem LLM-Wechsel

## Übersicht
Ziel ist es, die Anwendung von der aktuellen Ollama-LLM-Integration zur Hugging Face Inference API zu migrieren und dabei eine einfache Option zum Wechseln verschiedener LLMs bereitzustellen.

## Problemstellung
- Die aktuelle Ollama-Integration erfordert lokale Modell-Installation und Serververwaltung
- Benutzer möchten Zugang zu verschiedenen Hugging Face-Modellen ohne lokale Setup-Komplexität
- Entwickler benötigen eine einfache Möglichkeit, zwischen verschiedenen LLM-Anbietern zu wechseln

## Anforderungen

### Funktionale Anforderungen
1. **Hugging Face Inference API Integration**
   - Vollständige Migration von Ollama-Client zur Hugging Face Inference API
   - Unterstützung für beliebte medizinische/allgemeine Modelle (z.B. Llama-3.1, Gemma-2, Mistral)
   - Authentifizierung über HF_TOKEN environment variable

2. **Konfigurierbare LLM-Auswahl**
   - Erweiterung der config.json um LLM-Provider-Konfiguration
   - Unterstützung für mehrere Provider (HuggingFace, Ollama als Fallback)
   - Einfacher Modellwechsel ohne Code-Änderungen

3. **Fallback-Mechanismen**
   - Graceful fallback wenn Hugging Face API nicht verfügbar ist
   - Mock-Client für Entwicklung ohne API-Keys
   - Fehlerbehandlung bei ungültigen Modell-Namen

### Technische Anforderungen
- **API-Kompatibilität**: Beibehaltung der bestehenden LLMService-Schnittstelle
- **Konfiguration**: JSON-basierte Konfiguration für Provider und Modelle
- **Logging**: Detaillierte Logs für API-Aufrufe und Fehler
- **Performance**: Ähnliche Antwortzeiten wie bei Ollama

### Benutzererfahrung
- **Entwickler**: Einfache Konfiguration über config.json
- **Transparent**: Keine Änderungen an der Benutzeroberfläche erforderlich
- **Zuverlässig**: Robuste Fehlerbehandlung und Fallbacks

## Akzeptanzkriterien

### Primär
- [ ] Hugging Face Inference API erfolgreich integriert
- [ ] Bestehende Chat-Funktionalität bleibt vollständig erhalten
- [ ] config.json ermöglicht einfachen Provider/Modell-Wechsel
- [ ] HF_TOKEN Authentifizierung implementiert

### Sekundär
- [ ] Mock-Client für lokale Entwicklung verfügbar
- [ ] Detaillierte Fehlerbehandlung und Logging
- [ ] Performance vergleichbar mit Ollama-Implementation
- [ ] Dokumentation für Entwickler aktualisiert

## Erfolgsmetriken
- **Technisch**: Erfolgreiche API-Aufrufe > 95%
- **Benutzerfreundlichkeit**: Konfigurationszeit < 2 Minuten
- **Zuverlässigkeit**: Uptime > 99% (abhängig von HF API)

## Risiken und Mitigationen
- **API-Abhängigkeit**: Fallback auf lokale Modelle implementieren
- **Kosten**: Monitoring der API-Nutzung und Rate Limits
- **Performance**: Caching-Strategien für häufige Anfragen

## Zeitplan
- **Phase 1** (Tag 1): HuggingFace Client-Integration
- **Phase 2** (Tag 2): Provider-Konfigurationssystem
- **Phase 3** (Tag 3): Fehlerbehandlung und Fallbacks
- **Phase 4** (Tag 4): Testing und Dokumentation

## Abhängigkeiten
- Hugging Face API Token
- `huggingface_hub` Python Package
- Bestehende config.json Infrastruktur 