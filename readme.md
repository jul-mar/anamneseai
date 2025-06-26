# AI Chat for Patient history
QuestionnAIre

# What is it?
A Chatbot you can give a number of questions and it will ask these questions the patient, while verifying the questions and rephrasing them if the patient isnt answering them correctly.


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