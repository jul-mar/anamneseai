## Relevant Files


- `anamneseai.py` or `questionnAIre.py` - Main application logic where the LLM model is selected and used.
- `.env` or `config.json` - Configuration file for specifying the model name.
- `readme.md` - Documentation for developers on how to configure the model.

### Notes

- Update or create a sample config file if one does not exist.
- Ensure documentation is clear for junior developers.

## Tasks

- [ ] 1.0 Add configuration support for model selection
  - [x] 1.1 Decide on configuration method: environment variable (e.g., `LLM_MODEL_NAME`) or config file (e.g., `config.json`) (Chosen: config file)
  - [ ] 1.2 If using `.env`, add `LLM_MODEL_NAME` to `.env` and update `.gitignore` if needed
  - [x] 1.3 If using `config.json`, create the file with a `model_name` key and provide a sample
  - [x] 1.4 Implement code to read the model name from the chosen configuration at app startup
  - [x] 1.5 Add logic to default to the current model if no config is found

- [ ] 2.0 Refactor LLM service to use the configured model at startup
  - [x] 2.1 Update the LLM service/class to accept the model name as a parameter
  - [x] 2.2 Pass the configured model name to the LLM service when initializing the app
  - [x] 2.3 Ensure all LLM API calls use the selected model
  - [x] 2.4 Log the selected model name at startup for developer visibility

- [ ] 3.0 Implement fallback logic for unavailable/misconfigured models
  - [x] 3.1 Add error handling for invalid or unavailable model names
  - [x] 3.2 If the specified model is unavailable, log a clear error message
  - [x] 3.3 Fallback to a default model if the configured model cannot be used
  - [x] 3.4 Test fallback logic by specifying an invalid model in the config

- [ ] 4.0 Document configuration and usage for developers
  - [x] 4.1 Update `readme.md` with instructions for configuring the model
  - [x] 4.2 Provide examples for both `.env` and `config.json` methods
  - [x] 4.3 Document the fallback behavior and default model
  - [x] 4.4 Add troubleshooting tips for common configuration errors

- [ ] 5.0 Test model switching and fallback behavior
  - [x] 5.1 Manually test switching between at least two models (e.g., Gemini 2.5 and gemma3)
  - [ ] 5.2 Test with a missing or invalid config to ensure fallback works
  - [ ] 5.3 Verify that the selected model is used for all LLM requests
  - [ ] 5.4 (Optional) Add automated tests for configuration and fallback logic if feasible

---
I have generated the high-level tasks based on the PRD. Ready to generate the sub-tasks? Respond with 'Go' to proceed. 