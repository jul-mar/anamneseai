#!/usr/bin/env python3
"""
Test script für die Hugging Face Integration
Demonstriert den einfachen Wechsel zwischen LLM-Providern
"""

import os
import json
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_huggingface_connection():
    """Test der Hugging Face Verbindung"""
    print("=== Hugging Face Integration Test ===\n")
    
    # Check HF_TOKEN
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("❌ HF_TOKEN nicht gesetzt")
        print("   Setzen Sie: export HF_TOKEN='your_token_here'")
        print("   Fallback: Mock-Client wird verwendet\n")
        return False
    else:
        print(f"✅ HF_TOKEN gesetzt: {hf_token[:10]}...\n")
    
    # Test verschiedene Modelle
    test_models = [
        "meta-llama/Llama-3.1-8B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3", 
        "google/gemma-2-9b-it"
    ]
    
    for model_name in test_models:
        print(f"Testing Model: {model_name}")
        try:
            client = InferenceClient(model=model_name, token=hf_token)
            
            # Simple test message
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, how are you?"}
            ]
            
            response = client.chat_completion(
                messages=messages,
                max_tokens=50,
                temperature=0.7
            )
            
            if response and response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                print(f"✅ Antwort: {content[:100] if content else 'Keine Antwort'}...")
            else:
                print("✅ Verbindung erfolgreich, aber keine Antwort erhalten")
            print()
            
        except Exception as e:
            print(f"❌ Fehler: {e}")
            print()
    
    return True

def test_config_loading():
    """Test der Konfigurationladung"""
    print("=== Konfigurations-Test ===\n")
    
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        
        print("✅ config.json erfolgreich geladen:")
        print(f"   Provider: {config.get('provider', 'nicht gesetzt')}")
        print(f"   Model: {config.get('model_name', 'nicht gesetzt')}")
        
        if config.get('provider') == 'huggingface':
            hf_config = config.get('huggingface', {})
            print(f"   HF API URL: {hf_config.get('api_url', 'nicht gesetzt')}")
            print(f"   Max Tokens: {hf_config.get('max_tokens', 'nicht gesetzt')}")
        
        print()
        return True
        
    except Exception as e:
        print(f"❌ Fehler beim Laden der config.json: {e}")
        print()
        return False

def show_config_examples():
    """Zeigt Konfigurationsbeispiele"""
    print("=== Konfigurationsbeispiele ===\n")
    
    examples = {
        "Hugging Face (Llama)": {
            "provider": "huggingface",
            "model_name": "meta-llama/Llama-3.1-8B-Instruct",
            "huggingface": {
                "max_tokens": 1000,
                "temperature": 0.7
            }
        },
        "Hugging Face (Mistral)": {
            "provider": "huggingface", 
            "model_name": "mistralai/Mistral-7B-Instruct-v0.3",
            "huggingface": {
                "max_tokens": 1000,
                "temperature": 0.7
            }
        },
        "Ollama (Fallback)": {
            "provider": "ollama",
            "model_name": "gemma3:4b-it-qat",
            "ollama": {
                "host": "http://localhost:11434"
            }
        }
    }
    
    for name, config in examples.items():
        print(f"**{name}:**")
        print(json.dumps(config, indent=2))
        print()

def main():
    """Hauptfunktion"""
    print("🤖 Hugging Face Integration Test\n")
    print("Dieses Skript testet die neue LLM-Provider-Funktionalität\n")
    
    # Test Konfiguration
    config_ok = test_config_loading()
    
    # Test Hugging Face Verbindung (nur wenn HF_TOKEN gesetzt)
    if os.getenv("HF_TOKEN"):
        hf_ok = test_huggingface_connection()
    else:
        print("⚠️  HF_TOKEN nicht gesetzt - Hugging Face Test übersprungen")
        print("   Die Anwendung wird mit Mock-Client laufen\n")
        hf_ok = False
    
    # Zeige Konfigurationsbeispiele
    show_config_examples()
    
    # Zusammenfassung
    print("=== Zusammenfassung ===")
    print(f"Konfiguration: {'✅' if config_ok else '❌'}")
    print(f"Hugging Face: {'✅' if hf_ok else '⚠️  (Mock-Client)'}")
    print()
    
    if config_ok:
        print("🚀 Die Anwendung kann gestartet werden mit:")
        print("   python questionnAIre.py")
    else:
        print("⚠️  Bitte config.json überprüfen und korrigieren")
    
    print("\n📖 Dokumentation: README-HuggingFace-Migration.md")

if __name__ == "__main__":
    main() 