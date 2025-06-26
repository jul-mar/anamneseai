# Taskliste: Migration zur Hugging Face Inference API

## Phase 1: HuggingFace Client-Integration

### 1.1 Dependencies Installation
- [ ] `huggingface_hub` package zur requirements.txt hinzufügen
- [ ] Import-Statements in LLMService aktualisieren

### 1.2 HuggingFace Client Implementation
- [ ] Neue HuggingFaceClient-Klasse erstellen
- [ ] Inference API Integration implementieren
- [ ] Chat-Completion Format für HF API anpassen

### 1.3 Authentication Setup
- [ ] HF_TOKEN environment variable Support hinzufügen
- [ ] Token-Validierung implementieren
- [ ] Fallback bei fehlenden Credentials

## Phase 2: Provider-Konfigurationssystem

### 2.1 Config Schema Erweiterung
- [ ] config.json Schema um "provider" Feld erweitern
- [ ] Provider-spezifische Konfigurationsoptionen hinzufügen
- [ ] Backward-Kompatibilität mit alter config.json sicherstellen

### 2.2 Provider Factory Pattern
- [ ] ProviderFactory-Klasse implementieren
- [ ] HuggingFaceProvider und OllamaProvider erstellen
- [ ] LLMService für multi-provider Support refaktorieren

### 2.3 Configuration Loading
- [ ] Enhanced config loading mit Provider-Support
- [ ] Validation der Provider-Konfiguration
- [ ] Default-Provider festlegen

## Phase 3: Fehlerbehandlung und Fallbacks

### 3.1 Error Handling
- [ ] HuggingFace API-spezifische Fehlerbehandlung
- [ ] Rate limiting und quota handling
- [ ] Network error recovery

### 3.2 Fallback Mechanisms
- [ ] Provider fallback chain implementieren
- [ ] Mock client für HuggingFace erweitern
- [ ] Graceful degradation bei API-Ausfällen

### 3.3 Logging und Monitoring
- [ ] Strukturiertes Logging für API-Aufrufe
- [ ] Performance-Metriken sammeln
- [ ] Debug-Modi für verschiedene Provider

## Phase 4: Testing und Dokumentation

### 4.1 Testing
- [ ] Unit tests für HuggingFace integration
- [ ] Integration tests mit Mock-APIs
- [ ] Config validation tests

### 4.2 Documentation
- [ ] README.md mit HuggingFace setup instructions
- [ ] config.json Beispiele und Schemas
- [ ] Migration guide von Ollama

### 4.3 Example Configurations
- [ ] Beispiel-configs für beliebte HF-Modelle
- [ ] Multi-provider setup Beispiele
- [ ] Development vs Production configs

## Implementierungsreihenfolge

1. **Subtask 1.1**: Dependencies hinzufügen
2. **Subtask 2.1**: Config schema erweitern
3. **Subtask 1.2**: HuggingFace client implementieren
4. **Subtask 1.3**: Authentication setup
5. **Subtask 2.2**: Provider factory pattern
6. **Subtask 2.3**: Enhanced config loading
7. **Subtask 3.1**: Error handling
8. **Subtask 3.2**: Fallback mechanisms
9. **Subtask 3.3**: Logging enhancement
10. **Subtask 4.1**: Testing
11. **Subtask 4.2**: Documentation
12. **Subtask 4.3**: Example configurations

## Notizen
- Jeder Subtask sollte einzeln implementiert und getestet werden
- Bestehende Ollama-Funktionalität als Fallback beibehalten
- User experience sollte sich nicht ändern
- Konfiguration über config.json sollte weiterhin einfach bleiben 