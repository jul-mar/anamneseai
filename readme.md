# QuestionnAIre - AI Patient History Chatbot

## What is it?
A sophisticated chatbot designed to interview patients and gather their medical history prior to a doctor's appointment. The application uses **LangGraph** to create a flexible, stateful graph that orchestrates the conversation flow. This allows for a more dynamic and robust interaction compared to a linear script.

## Architecture
The application is split into two main components:
- **Backend**: A Python-based [FastAPI](https://fastapi.tiangolo.com/) server that handles the core logic. It now uses LangGraph to manage the chat state and conversation flow.
- **Frontend**: A static, vanilla JavaScript single-page application that provides the user interface for the chat.

The core of the backend is the `anamnesis_graph` defined in `backend/graph.py`. This graph defines the nodes (steps in the conversation) and edges (logic for moving between steps). The session management in `backend/main.py` now stores the state of this graph for each user.

## Getting Started

### Prerequisites
- Python 3.9+
- An OpenAI API key (for GPT-4o-mini)
- [UV](https://docs.astral.sh/uv/) package manager (recommended) or pip

### Quick Setup with UV (Recommended)

**1. Install UV:**
```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# or with pip
pip install uv
```

**2. Run the setup script:**
```bash
# Run the automated setup script
./setup-uv.sh
```

This will automatically:
- Initialize the UV project
- Create a virtual environment
- Install all dependencies
- Set up the project structure

### Manual Setup

### 1. Backend Setup
First, set up and run the backend server.

**a. Install dependencies:**

**With UV (recommended):**
```bash
# Initialize and sync dependencies
uv sync
```

**With pip (traditional):**
```bash
# Create and activate a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

**b. Configure Environment Variables:**
The backend requires an OpenAI API key to access GPT-4o-mini. Create a `.env` file in the project root directory and add your token:
```bash
# In your project root, create a .env file
touch .env
```
Add the following line to the `.env` file:
```
OPENAI_API_KEY="your_openai_api_key_here"
```
The application uses `gpt-4o-mini` by default. You can change this in `backend/config.json` if needed.

**c. Run the backend server:**

**With UV:**
```bash
uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**With pip/traditional setup:**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

**Or use the convenient start script:**
```bash
./start.sh
```

The `--reload` flag is optional but helpful for development. The backend API is now running and accessible at `http://localhost:8000`.

### 2. Frontend Setup
In a **separate terminal**, navigate to the `frontend` directory and start a simple Python HTTP server to serve the static files.

```bash
cd frontend
python -m http.server 8080
```
> **Note:** Any simple web server can be used. Python's built-in module is just a convenient option for local development.

### 3. Access the Application
Open your web browser and navigate to:
**[http://localhost:8080](http://localhost:8080)**

You can now interact with the QuestionnAIre chatbot.

## UV Commands Reference

If you're using UV for package management, here are some useful commands:

```bash
# Add a new dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Remove a dependency
uv remove <package-name>

# Update dependencies
uv sync

# Run a command in the virtual environment
uv run <command>

# Activate the virtual environment
uv shell

# Show project information
uv tree
```

## Debug Mode
The application includes a debug mode that allows you to step through the conversation graph.
- **Toggle Debug Mode:** Send a POST request to `/api/debug/toggle`.
- **Continue to next step:** When paused in debug mode, send a POST request to `/api/debug/continue` to advance the conversation.

# What is it for?
Patients often wait a lot of time in the waiting room in hospitals or privat practices. At the same time doctors dont have enough time for doing a thorough patient history. The patient could use the time waiting talking to an AI Chat bot which gives the doctor a summary of the most important facts before he sees the patient.

# MVP to dos
- building a Chat interface (done)
- giving the Chatbot memory (done with LangGraph)
- introduction 
- one example question (done)
- AI has to collect all the answers (done)
- verification of the answers
- create a summary of the answers when all questions are answered

# Plan:
- implement LLM checking if the answer satisfies the critiria
- one question with sub questions
- saving the answer if critiria is met
-

## Configuring the LLM Model

You can select which LLM model the application uses by editing the `config.json` file in the project root. For example:

```json
{
  "model_name": "gemini-2.5"
}
```

- Change the value of `model_name` to any supported model (e.g., `gemini-2.5`, `gemma3`, etc.).
- If the specified model is not available, the application will log an error and fall back to the default model.
- If `config.json` is missing or does not contain a `model_name`, the default model will be used.

### Example: config.json

```
{
  "model_name": "gemini-2.5"
}
```

### Example: .env (not currently used, but for reference)

```
# LLM_MODEL_NAME=gemini-2.5
```

> **Note:** The current implementation uses `config.json` for model selection. If you wish to switch to environment variable configuration in the future, use the `.env` example above and update the code accordingly.

### Fallback Behavior and Default Model

- If the model specified in `config.json` is missing, invalid, or not available on the server, the application will log an error and automatically use the default model (`gemma3:4b-it-qat`).
- If `config.json` is missing or does not contain a `model_name`, the default model will be used.
- The selected model name is logged at startup for developer visibility.

### Troubleshooting Tips for Model Configuration

- **config.json missing:** Ensure that `config.json` exists in the project root. If missing, copy the sample from the documentation or create a new one with a `model_name` key.
- **model_name typo:** Double-check the spelling of the model name in `config.json`. It must match the name of a model available on your LLM server.
- **Model not available:** If you specify a model that is not available on the server, the app will log an error and use the default model. Check the list of available models on your server.
- **Server not running:** If the LLM server (e.g., Ollama) is not running, the app will fall back to a mock client and may not provide real responses.
- **Permission errors:** Make sure the app has read permissions for `config.json`.
- **Changes not taking effect:** Restart the app after changing `config.json` to ensure the new model is loaded.