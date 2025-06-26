# Migration zur Hugging Face Inference API

Dieses Dokument erklärt, wie Sie die Anwendung von Ollama zur Hugging Face Inference API migrieren und einfach zwischen verschiedenen LLM-Anbietern wechseln können.

## Überblick

Die neue Version unterstützt mehrere LLM-Provider:
- **Hugging Face Inference API**: Cloud-basierte Modelle ohne lokale Installation
- **Ollama**: Lokale Modelle (Fallback/Kompatibilität)

## Schnellstart: Hugging Face Setup

### 1. Hugging Face Token einrichten

Erstellen Sie einen Account auf [huggingface.co](https://huggingface.co) und generieren Sie einen Access Token:

1. Gehen Sie zu: https://huggingface.co/settings/tokens
2. Erstellen Sie einen neuen Token mit "Read" Berechtigung
3. Erstellen Sie eine `.env` Datei:

```bash
# Kopieren Sie die Vorlage
cp env.example .env

# Bearbeiten Sie die .env Datei
nano .env
```

4. Tragen Sie Ihren Token in die `.env` Datei ein:
```bash
# .env
HF_TOKEN=your_actual_token_here
```

### 2. Konfiguration anpassen

Bearbeiten Sie `config.json`:

```json
{
  "provider": "huggingface",
  "model_name": "meta-llama/Llama-3.1-8B-Instruct",
  "huggingface": {
    "api_url": "https://api-inference.huggingface.co/models/",
    "max_tokens": 1000,
    "temperature": 0.7
  },
  "ollama": {
    "host": "http://localhost:11434"
  }
}
```

### 3. Anwendung starten

```bash
python questionnAIre.py
```

## Konfigurationsoptionen

### Provider-Auswahl

Ändern Sie das `provider` Feld in `config.json`:

- `"huggingface"`: Nutzt Hugging Face Inference API
- `"ollama"`: Nutzt lokale Ollama-Installation

### Empfohlene Modelle

#### Für medizinische Anwendungen:

**Hugging Face:**
```json
{
  "provider": "huggingface",
  "model_name": "meta-llama/Llama-3.1-8B-Instruct"
}
```

**Alternative Modelle:**
- `"mistralai/Mistral-7B-Instruct-v0.3"`
- `"google/gemma-2-9b-it"`
- `"microsoft/DialoGPT-large"`

**Ollama (Fallback):**
```json
{
  "provider": "ollama",
  "model_name": "gemma3:4b-it-qat"
}
```

### Konfiguration Beispiele

In `config-examples.json` finden Sie vorkonfigurierte Beispiele für verschiedene Setups:

```bash
# Kopieren Sie ein Beispiel:
cp config-examples.json config.json

# Bearbeiten Sie die gewünschte Konfiguration
nano config.json
```

## Einfacher LLM-Wechsel

### Zwischen Providern wechseln

1. **Zu Hugging Face wechseln:**
   ```json
   {
     "provider": "huggingface",
     "model_name": "meta-llama/Llama-3.1-8B-Instruct"
   }
   ```

2. **Zu Ollama wechseln:**
   ```json
   {
     "provider": "ollama", 
     "model_name": "gemma3:4b-it-qat"
   }
   ```

### Modell innerhalb eines Providers wechseln

**Hugging Face Modelle:**
```json
{
  "provider": "huggingface",
  "model_name": "mistralai/Mistral-7B-Instruct-v0.3"
}
```

**Ollama Modelle:**
```json
{
  "provider": "ollama",
  "model_name": "llama3.1:8b-instruct"
}
```

## Fehlerbehandlung und Fallbacks

### Automatische Fallbacks

Die Anwendung implementiert automatische Fallbacks:

1. **Kein HF_TOKEN**: Wechselt zu Mock-Client mit Hinweismeldungen
2. **Provider nicht verfügbar**: Wechselt zu Ollama
3. **Modell nicht gefunden**: Nutzt Default-Modell
4. **API-Fehler**: Zeigt Fehlermeldungen, funktioniert weiter

### Debugging

Aktivieren Sie Debug-Logs in der Anwendung:

```bash
# Die Anwendung zeigt detaillierte Startup-Logs
python questionnAIre.py
```

Logs zeigen:
- Gewählten Provider und Modell
- Verbindungsstatus
- API-Aufrufe (bei Fehlern)

## Vorteile der Migration

### Hugging Face Inference API
✅ **Keine lokale Installation** - Modelle laufen in der Cloud  
✅ **Große Modellauswahl** - Zugang zu neuesten Modellen  
✅ **Automatische Updates** - Immer aktuelle Modellversionen  
✅ **Skalierbarkeit** - Keine Hardware-Limitierungen  

### Ollama (Fallback)
✅ **Lokale Kontrolle** - Vollständige Datenkontrolle  
✅ **Offline-Betrieb** - Funktioniert ohne Internet  
✅ **Anpassbarkeit** - Eigene Modell-Fine-tuning  

## Troubleshooting

### Häufige Probleme

**1. "Import huggingface_hub could not be resolved"**
```bash
pip install huggingface_hub
```

**2. "HF_TOKEN environment variable not set"**
```bash
# Erstellen Sie eine .env Datei
cp env.example .env

# Bearbeiten Sie die .env Datei und tragen Sie Ihren Token ein:
# HF_TOKEN=your_actual_token_here
```

**3. "Model not found" oder API-Fehler**
- Prüfen Sie den Modellnamen in der Hugging Face Model Hub
- Stellen Sie sicher, dass das Modell öffentlich verfügbar ist
- Prüfen Sie Ihre Token-Berechtigung

**4. "Provider not available"**
- Die Anwendung wechselt automatisch zu Ollama als Fallback
- Prüfen Sie Ihre Internetverbindung für Hugging Face

### Support

Bei Problemen:
1. Prüfen Sie die Startup-Logs der Anwendung
2. Validieren Sie Ihre `config.json` Syntax
3. Testen Sie verschiedene Modelle
4. Nutzen Sie Ollama als Fallback während des Debugging

## Performance-Tipps

### Modellauswahl
- **Kleinere Modelle** (7B Parameter) für schnellere Antworten
- **Größere Modelle** (13B+ Parameter) für bessere Qualität
- **Spezialisierte Modelle** für medizinische Domänen

### Konfiguration optimieren
```json
{
  "huggingface": {
    "max_tokens": 500,     // Kürzere Antworten = schneller
    "temperature": 0.3     // Weniger Kreativität = konsistenter
  }
}
```

Die Migration ist vollständig abwärtskompatibel - bestehende Ollama-Setups funktionieren weiterhin ohne Änderungen. 