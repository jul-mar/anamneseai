## Relevant Files

- `backend/graph.py` - Main graph implementation file to be completely replaced with enhanced logic
- `backend/database.py` - New database layer for SQLite operations and schema management (CREATED)
- `backend/medical_history.db` - SQLite database file for persistent storage (CREATED)
- `backend/questions.json` - Enhanced question configuration with evaluation criteria (UPDATED)
- `backend/models.py` - Data models and dataclasses for medical chat state and configuration (CREATED)
- `backend/question_manager.py` - Question management system with JSON parsing and validation (CREATED)
- `backend/answer_evaluator.py` - LLM-based answer evaluation system (CREATED)
- `backend/main.py` - FastAPI endpoints that need integration with new graph system
- `backend/config.json` - Configuration file that may need database settings
- `backend/medical_history.db` - SQLite database file for persistent storage
- `old/new_graph2.py` - Reference implementation containing the enhanced logic to migrate

### Notes

- The current UV package management system should be maintained throughout the migration
- Existing OpenAI GPT-4o-mini integration must be preserved
- Frontend compatibility is critical - no changes to frontend API contracts
- Database operations should include proper error handling and fallback mechanisms

## Tasks

- [x] 1.0 Setup Database Infrastructure and Models
  - [x] 1.1 Create SQLite database schema with medical_sessions, answered_questions, and conversation_history tables
  - [x] 1.2 Implement database.py module with connection management and CRUD operations
  - [x] 1.3 Create models.py with MedicalChatState dataclass and MedicalChatbotConfig
  - [x] 1.4 Add database initialization logic to application startup
  - [x] 1.5 Implement database migration and schema validation functions
  - [x] 1.6 Add error handling for database connection failures with fallback mechanisms

- [x] 2.0 Implement Enhanced Question Management System
  - [x] 2.1 Update questions.json with criteria fields for each question
  - [x] 2.2 Create question loader function to parse JSON with validation criteria
  - [x] 2.3 Implement LLM-based answer evaluation function against predefined criteria
  - [x] 2.4 Build retry logic system with maximum 3 attempts per question
  - [x] 2.5 Create helpful guidance generation for insufficient answers
  - [x] 2.6 Add question progression tracking and completion detection

- [x] 3.0 Develop Advanced Graph Logic with State Management
  - [x] 3.1 Replace current graph.py with enhanced LangGraph implementation from new_graph2.py
  - [x] 3.2 Implement ask_question node with welcome message preservation
  - [x] 3.3 Create evaluate_response node with criteria checking
  - [x] 3.4 Build handle_sufficient_response node for successful answers
  - [x] 3.5 Implement handle_insufficient_response node with retry logic
  - [x] 3.6 Add graph flow management with proper state transitions
  - [x] 3.7 Preserve initial question flow ("What is reason for your consultation? Fever or Cough?")

- [x] 4.0 Integrate Database Persistence with API Endpoints
  - [x] 4.1 Update /api/session/start endpoint to create database sessions
  - [x] 4.2 Modify /api/chat endpoint to store all messages in conversation_history
  - [x] 4.3 Implement session tracking with unique session IDs
  - [x] 4.4 Add answer storage in answered_questions table with summaries
  - [x] 4.5 Ensure backward compatibility with existing frontend JSON response format
  - [x] 4.6 Add comprehensive error handling for database operations in API layer

- [ ] 5.0 Implement Medical Summary Generation and Session Completion
  - [ ] 5.1 Create clinical summary generation function using OpenAI GPT-4o-mini
  - [ ] 5.2 Implement per-question summary creation and storage
  - [ ] 5.3 Build comprehensive medical history summary for completed sessions
  - [ ] 5.4 Add session completion detection and final summary generation
  - [ ] 5.5 Implement summary retrieval endpoints for healthcare providers
  - [ ] 5.6 Add session status tracking and completion timestamps 