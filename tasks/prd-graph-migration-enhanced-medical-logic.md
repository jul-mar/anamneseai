# PRD: Enhanced Medical History Graph Migration

## Introduction/Overview

This PRD outlines the migration from the current simple graph.py implementation to an enhanced medical history collection system based on the logic from new_graph2.py. The goal is to implement a sophisticated conversation management system with database persistence, intelligent question evaluation, and retry logic while maintaining the existing welcome flow and OpenAI GPT-4o-mini integration.

**Problem Statement**: The current graph.py implementation lacks structured conversation management, persistent storage, and sophisticated answer evaluation, limiting the quality and completeness of medical history collection.

**Solution**: Replace the current graph.py with an enhanced system that provides structured question flow, answer validation against criteria, retry mechanisms, and SQLite database persistence.

## Goals

1. **Enhanced Conversation Management**: Implement structured medical question flow with intelligent evaluation
2. **Data Persistence**: Store all medical conversations and answers in SQLite database for future reference
3. **Improved Answer Quality**: Validate patient responses against predefined criteria with retry logic
4. **Backward Compatibility**: Maintain existing FastAPI endpoints and frontend compatibility
5. **Better Medical Records**: Generate clinical summaries and maintain complete conversation history

## User Stories

1. **As a patient**, I want the system to ask follow-up questions when my answers are incomplete, so that I provide comprehensive medical information.

2. **As a healthcare provider**, I want patient responses stored persistently in a database, so that I can review complete medical histories later.

3. **As a patient**, I want the conversation to continue with the familiar welcome message, so that the experience feels consistent.

4. **As a healthcare provider**, I want each patient response evaluated against medical criteria, so that I receive complete and useful information.

5. **As a system administrator**, I want the migration to work with existing OpenAI integration and UV dependency management, so that deployment is seamless.

## Functional Requirements

### Core System Migration

1. **Replace Graph Implementation**: Replace backend/graph.py entirely with new logic based on new_graph2.py architecture
2. **Maintain Welcome Flow**: Preserve the existing welcome message: "Welcome to QuestionnAIre. I'm here to ask a few questions about your health before your appointment. Let's start."
3. **Preserve Initial Question**: Keep the current first question: "What is reason for your consultation? Fever or Cough?"
4. **Transition to Enhanced Flow**: After the initial question, switch to the new question evaluation system

### Database Implementation

5. **SQLite Database Setup**: Implement SQLite database with tables for:
   - `medical_sessions` (session tracking)
   - `answered_questions` (question responses with summaries)
   - `conversation_history` (complete chat log)

6. **Session Management**: Create database sessions for each user conversation with unique session IDs

7. **Data Persistence**: Store all user responses, AI messages, and generated summaries in the database

### Question Management System

8. **Enhanced Question Structure**: Implement questions with criteria validation from questions.json:
   ```json
   {
     "id": "symptom_duration",
     "question": "How long have you been experiencing this symptom?",
     "criteria": [
       "Must include a time period (days, weeks, months)",
       "Must be specific (not vague terms like 'recently')"
     ]
   }
   ```

9. **Answer Evaluation**: Use LLM to evaluate each response against predefined criteria

10. **Retry Logic**: Implement maximum 3 retry attempts per question with helpful guidance

### State Management

11. **Enhanced State Tracking**: Implement MedicalChatState dataclass with:
    - Current question index
    - Retry count
    - Evaluation results
    - Session completion status

12. **Graph Flow Management**: Create nodes for:
    - ask_question
    - evaluate_response
    - handle_sufficient_response
    - handle_insufficient_response

### API Integration

13. **FastAPI Compatibility**: Maintain existing API endpoints (`/api/session/start`, `/api/chat`) with enhanced functionality

14. **OpenAI Integration**: Preserve GPT-4o-mini integration for both conversation and evaluation

15. **Response Format**: Maintain current JSON response format for frontend compatibility

### Medical Summary Generation

16. **Clinical Summaries**: Generate medical summaries for each completed question using LLM

17. **Session Completion**: Create comprehensive medical history summary when all questions are answered

## Non-Goals (Out of Scope)

1. **Frontend Changes**: No modifications to the existing frontend interface required
2. **Authentication System**: User authentication/login system implementation
3. **HIPAA Compliance**: Full medical privacy compliance implementation (future consideration)
4. **Multi-language Support**: Translation or internationalization features
5. **Real-time Collaboration**: Multi-user or provider collaboration features
6. **Integration with EMR Systems**: External electronic medical record system integration

## Design Considerations

### Database Schema
```sql
-- Sessions table for tracking conversations
medical_sessions (
  id INTEGER PRIMARY KEY,
  user_id TEXT,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  is_complete BOOLEAN
)

-- Question responses with medical summaries
answered_questions (
  id INTEGER PRIMARY KEY,
  session_id INTEGER,
  question_id TEXT,
  question_text TEXT,
  user_response TEXT,
  summary TEXT,
  answered_at TIMESTAMP
)

-- Complete conversation log
conversation_history (
  id INTEGER PRIMARY KEY,
  session_id INTEGER,
  role TEXT,
  message TEXT,
  timestamp TIMESTAMP
)
```

### Configuration Structure
```python
@dataclass
class MedicalChatbotConfig:
    conversation_model: str = "gpt-4o-mini"
    evaluation_model: str = "gpt-4o-mini"
    max_retries: int = 3
    questions_file: str = "backend/questions.json"
    database_file: str = "medical_history.db"
```

## Technical Considerations

### Dependencies
- Maintain existing LangChain and LangGraph dependencies
- Add SQLite3 support (built into Python)
- Preserve OpenAI integration via langchain-openai
- Keep UV package management system

### File Structure Changes
- Replace `backend/graph.py` entirely
- Update `backend/questions.json` with criteria fields
- Add database initialization in startup
- Maintain existing `backend/main.py` API structure

### Migration Strategy
1. **Phase 1**: Implement new graph logic alongside existing (feature flag)
2. **Phase 2**: Update questions.json with criteria
3. **Phase 3**: Switch API endpoints to use new system
4. **Phase 4**: Remove old graph.py implementation

### Error Handling
- Database connection failures should fallback gracefully
- LLM evaluation failures should allow question progression
- Invalid JSON responses should trigger retry with simpler evaluation

## Success Metrics

### Primary Metrics
1. **Conversation Completion Rate**: Increase from current baseline to >85%
2. **Answer Quality Score**: LLM-evaluated answer completeness >90%
3. **Database Storage Success**: 100% of conversations stored successfully
4. **Response Time**: Maintain <3 second average response time

### Secondary Metrics
1. **Question Retry Rate**: Track retry frequency per question type
2. **Session Duration**: Monitor average time to complete medical history
3. **System Reliability**: 99.9% uptime with database persistence
4. **Clinical Summary Quality**: Healthcare provider satisfaction survey

### Technical Metrics
1. **API Compatibility**: 100% backward compatibility with existing frontend
2. **Migration Success**: Zero downtime deployment
3. **Database Performance**: Query response time <100ms
4. **OpenAI Integration**: Maintain current LLM response quality

## Open Questions

1. **Data Retention Policy**: How long should medical conversation data be stored in the database?

2. **User Identification**: Should we implement a more robust user ID system beyond simple string identifiers?

3. **Question Customization**: Should healthcare providers be able to customize questions and criteria per specialty?

4. **Backup Strategy**: What backup and recovery procedures should be implemented for the SQLite database?

5. **Performance Optimization**: Should we implement caching for frequently evaluated answer patterns?

6. **Monitoring**: What logging and monitoring should be implemented for the new evaluation system?

7. **Testing Strategy**: Should we implement A/B testing to compare old vs new conversation flows?

8. **Scalability**: Should we plan for PostgreSQL migration for higher patient volumes?

## Implementation Priority

### High Priority (Must Have)
- Database implementation and session management
- Enhanced question evaluation system
- Retry logic with max attempts
- Clinical summary generation

### Medium Priority (Should Have)
- Comprehensive error handling
- Performance optimization
- Enhanced logging and monitoring

### Low Priority (Could Have)
- Advanced analytics and reporting
- Question customization interface
- Backup automation 