# QuestionnAIre - AI Patient History Chatbot

## What is it?
A sophisticated chatbot designed to interview patients and gather their medical history prior to a doctor's appointment. The application uses a Large Language Model (LLM) to ask a series of predefined questions, evaluate the patient's answers for completeness, and ask clarifying follow-up questions when necessary.

## Architecture
The application is now split into two main components:
- **Backend**: A Python-based [FastAPI](https://fastapi.tiangolo.com/) server that handles all the core logic, including chat state management, interaction with the LLM, and serving the API.
- **Frontend**: A static, vanilla JavaScript single-page application that provides the user interface for the chat.

This separation allows for independent development, scaling, and deployment of the backend and frontend.

## Getting Started

### Prerequisites
- Python 3.8+
- An Ollama server (or other LLM provider) running and accessible to the backend.

### 1. Backend Setup
First, set up and run the backend server.

**a. Install dependencies:**
Navigate to the project root and install the required Python packages from the `backend/requirements.txt` file. It's recommended to use a virtual environment.
```bash
# Create and activate a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

**b. Configure the LLM:**
Copy the `backend/config.example.json` to `backend/config.json` and edit it to point to your desired LLM model.
```bash
cp backend/config.example.json backend/config.json
```
Example `config.json`:
```json
{
  "provider": "ollama",
  "model_name": "gemma3:4b-it-qat",
  "ollama": {
    "host": "http://localhost:11434"
  }
}
```
If you are using HuggingFace, you also need to set the `HF_TOKEN` environment variable.

**c. Run the backend server:**
From the project root directory, run the `main.py` script using `uvicorn`.
```bash
uvicorn backend.main:app --hot 0.0.0.0 --port 8000
```
The backend API is now running and accessible at `http://localhost:8000`.

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

# What is it for?
Patients often wait a lot of time in the waiting room in hospitals or privat practices. At the same time doctors dont have enough time for doing a thorough patient history. The patient could use the time waiting talking to an AI Chat bot which gives the doctor a summary of the most important facts before he sees the patient.

# MVP to dos
- building a Chat interface (done)
- giving the Chatbot memory
- introduction 
- one example question
- AI has to collect all the answers
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