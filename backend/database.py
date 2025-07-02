import sqlite3
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class MedicalHistoryDatabase:
    """SQLite database layer for medical history collection system"""
    
    def __init__(self, db_file: str = "backend/medical_history.db"):
        self.db_file = db_file
        self.connection_healthy = True
        self.fallback_mode = False
        self.fallback_data = {}  # In-memory fallback storage
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.db_file) if os.path.dirname(self.db_file) else ".", exist_ok=True)
            
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Create medical_sessions table for tracking conversations
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS medical_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    is_complete BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # Create answered_questions table for question responses with summaries
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS answered_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    question_id TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    user_response TEXT NOT NULL,
                    summary TEXT,
                    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES medical_sessions (id)
                )
            ''')
            
            # Create conversation_history table for complete chat log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES medical_sessions (id)
                )
            ''')
            
            conn.commit()
            conn.close()
            
            # Run migrations and validate schema
            self.migrate_database()
            if not self.validate_schema():
                logger.warning("Database schema validation failed after initialization")
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            logger.warning("Switching to fallback mode - data will be stored in memory only")
            self.connection_healthy = False
            self.fallback_mode = True
    
    def create_session(self, user_id: str) -> int:
        """Create a new medical session and return session ID"""
        if self.fallback_mode:
            # Fallback: use in-memory storage
            session_id = len(self.fallback_data.get('sessions', [])) + 1
            if 'sessions' not in self.fallback_data:
                self.fallback_data['sessions'] = []
            self.fallback_data['sessions'].append({
                'id': session_id,
                'user_id': user_id,
                'started_at': datetime.now().isoformat(),
                'completed_at': None,
                'is_complete': False
            })
            logger.info(f"Created session {session_id} in fallback mode")
            return session_id
        
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO medical_sessions (user_id) VALUES (?)', (user_id,))
            session_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            if session_id is None:
                raise RuntimeError("Failed to create session - no ID returned")
            return session_id
            
        except Exception as e:
            logger.error(f"Database error in create_session: {e}")
            logger.warning("Switching to fallback mode")
            self.fallback_mode = True
            self.connection_healthy = False
            return self.create_session(user_id)  # Retry in fallback mode
    
    def save_answered_question(self, session_id: int, question_id: str, 
                             question_text: str, user_response: str, summary: str = ""):
        """Save a completed question with user response and medical summary"""
        if self.fallback_mode:
            # Fallback: use in-memory storage
            if 'answered_questions' not in self.fallback_data:
                self.fallback_data['answered_questions'] = []
            self.fallback_data['answered_questions'].append({
                'session_id': session_id,
                'question_id': question_id,
                'question_text': question_text,
                'user_response': user_response,
                'summary': summary,
                'answered_at': datetime.now().isoformat()
            })
            logger.info(f"Saved answered question in fallback mode for session {session_id}")
            return
        
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO answered_questions 
                (session_id, question_id, question_text, user_response, summary)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, question_id, question_text, user_response, summary))
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Database error in save_answered_question: {e}")
            logger.warning("Switching to fallback mode")
            self.fallback_mode = True
            self.connection_healthy = False
            self.save_answered_question(session_id, question_id, question_text, user_response, summary)
    
    def save_conversation_message(self, session_id: int, role: str, message: str):
        """Save a message to conversation history (role: 'user' or 'assistant')"""
        if self.fallback_mode:
            # Fallback: use in-memory storage
            if 'conversation_history' not in self.fallback_data:
                self.fallback_data['conversation_history'] = []
            self.fallback_data['conversation_history'].append({
                'session_id': session_id,
                'role': role,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
            return
        
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO conversation_history (session_id, role, message)
                VALUES (?, ?, ?)
            ''', (session_id, role, message))
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Database error in save_conversation_message: {e}")
            logger.warning("Switching to fallback mode")
            self.fallback_mode = True
            self.connection_healthy = False
            self.save_conversation_message(session_id, role, message)
    
    def complete_session(self, session_id: int):
        """Mark a session as completed"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE medical_sessions 
            SET completed_at = CURRENT_TIMESTAMP, is_complete = TRUE
            WHERE id = ?
        ''', (session_id,))
        conn.commit()
        conn.close()
    
    def get_session(self, session_id: int) -> Optional[Dict]:
        """Get session details by ID"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, user_id, started_at, completed_at, is_complete
            FROM medical_sessions WHERE id = ?
        ''', (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "user_id": row[1],
                "started_at": row[2],
                "completed_at": row[3],
                "is_complete": bool(row[4])
            }
        return None
    
    def get_conversation_history(self, session_id: int) -> List[Dict]:
        """Get complete conversation history for a session"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT role, message, timestamp
            FROM conversation_history 
            WHERE session_id = ?
            ORDER BY timestamp ASC
        ''', (session_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {"role": row[0], "message": row[1], "timestamp": row[2]            }
            for row in rows
        ]
    
    def validate_schema(self) -> bool:
        """Validate that all required tables exist with correct structure"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Check if all required tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row[0] for row in cursor.fetchall()}
            required_tables = {'medical_sessions', 'answered_questions', 'conversation_history'}
            
            if not required_tables.issubset(existing_tables):
                missing_tables = required_tables - existing_tables
                logger.error(f"Missing database tables: {missing_tables}")
                conn.close()
                return False
            
            # Validate medical_sessions table structure
            cursor.execute("PRAGMA table_info(medical_sessions)")
            sessions_columns = {row[1]: row[2] for row in cursor.fetchall()}
            required_sessions_columns = {
                'id': 'INTEGER',
                'user_id': 'TEXT',
                'started_at': 'TIMESTAMP',
                'completed_at': 'TIMESTAMP',
                'is_complete': 'BOOLEAN'
            }
            
            for col_name, col_type in required_sessions_columns.items():
                if col_name not in sessions_columns:
                    logger.error(f"Missing column {col_name} in medical_sessions table")
                    conn.close()
                    return False
            
            # Validate answered_questions table structure
            cursor.execute("PRAGMA table_info(answered_questions)")
            questions_columns = {row[1]: row[2] for row in cursor.fetchall()}
            required_questions_columns = {
                'id': 'INTEGER',
                'session_id': 'INTEGER',
                'question_id': 'TEXT',
                'question_text': 'TEXT',
                'user_response': 'TEXT',
                'summary': 'TEXT',
                'answered_at': 'TIMESTAMP'
            }
            
            for col_name, col_type in required_questions_columns.items():
                if col_name not in questions_columns:
                    logger.error(f"Missing column {col_name} in answered_questions table")
                    conn.close()
                    return False
            
            # Validate conversation_history table structure
            cursor.execute("PRAGMA table_info(conversation_history)")
            history_columns = {row[1]: row[2] for row in cursor.fetchall()}
            required_history_columns = {
                'id': 'INTEGER',
                'session_id': 'INTEGER',
                'role': 'TEXT',
                'message': 'TEXT',
                'timestamp': 'TIMESTAMP'
            }
            
            for col_name, col_type in required_history_columns.items():
                if col_name not in history_columns:
                    logger.error(f"Missing column {col_name} in conversation_history table")
                    conn.close()
                    return False
            
            conn.close()
            logger.info("Database schema validation successful")
            return True
            
        except Exception as e:
            logger.error(f"Database schema validation failed: {e}")
            return False
    
    def migrate_database(self) -> bool:
        """Perform database migrations to update schema if needed"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Get current schema version (if versioning table exists)
            try:
                cursor.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
                current_version = cursor.fetchone()
                current_version = current_version[0] if current_version else 0
            except sqlite3.OperationalError:
                # Schema version table doesn't exist, create it
                cursor.execute('''
                    CREATE TABLE schema_version (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version INTEGER NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute("INSERT INTO schema_version (version) VALUES (0)")
                current_version = 0
            
            target_version = 1  # Current target schema version
            
            if current_version < target_version:
                logger.info(f"Migrating database from version {current_version} to {target_version}")
                
                # Migration from version 0 to 1 (initial schema)
                if current_version == 0:
                    # Tables are already created in init_database()
                    # This migration just updates the version
                    cursor.execute("INSERT INTO schema_version (version) VALUES (1)")
                    logger.info("Applied migration: Initial schema setup")
                
                conn.commit()
                logger.info(f"Database migration completed to version {target_version}")
            else:
                logger.info(f"Database already at target version {target_version}")
            
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Database migration failed: {e}")
            return False
    
    def backup_database(self, backup_path: Optional[str] = None) -> bool:
        """Create a backup of the database"""
        if backup_path is None:
            backup_path = f"{self.db_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            import shutil
            shutil.copy2(self.db_file, backup_path)
            logger.info(f"Database backup created: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get database information and statistics"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Get table counts
            cursor.execute("SELECT COUNT(*) FROM medical_sessions")
            sessions_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM answered_questions")
            questions_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM conversation_history")
            messages_count = cursor.fetchone()[0]
            
            # Get schema version
            try:
                cursor.execute("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
                schema_version = cursor.fetchone()
                schema_version = schema_version[0] if schema_version else 0
            except sqlite3.OperationalError:
                schema_version = 0
            
            # Get database file size
            file_size = os.path.getsize(self.db_file) if os.path.exists(self.db_file) else 0
            
            conn.close()
            
            return {
                "database_file": self.db_file,
                "schema_version": schema_version,
                "file_size_bytes": file_size,
                "sessions_count": sessions_count,
                "answered_questions_count": questions_count,
                "conversation_messages_count": messages_count,
                "last_modified": datetime.fromtimestamp(os.path.getmtime(self.db_file)).isoformat() if os.path.exists(self.db_file) else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}
    
    def test_connection(self) -> bool:
        """Test database connection health"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def attempt_recovery(self) -> bool:
        """Attempt to recover from fallback mode to normal database operations"""
        if not self.fallback_mode:
            return True
            
        try:
            # Test if database is now accessible
            if self.test_connection():
                logger.info("Database connection recovered, attempting to sync fallback data")
                
                # Try to sync fallback data to database
                success = self._sync_fallback_to_db()
                if success:
                    self.fallback_mode = False
                    self.connection_healthy = True
                    logger.info("Successfully recovered from fallback mode")
                    return True
                else:
                    logger.warning("Database accessible but failed to sync fallback data")
                    return False
            else:
                logger.info("Database still not accessible")
                return False
                
        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")
            return False
    
    def _sync_fallback_to_db(self) -> bool:
        """Sync fallback data to database (private method)"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Sync sessions
            for session in self.fallback_data.get('sessions', []):
                cursor.execute('''
                    INSERT OR IGNORE INTO medical_sessions 
                    (id, user_id, started_at, completed_at, is_complete)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session['id'], session['user_id'], session['started_at'], 
                     session['completed_at'], session['is_complete']))
            
            # Sync answered questions
            for question in self.fallback_data.get('answered_questions', []):
                cursor.execute('''
                    INSERT OR IGNORE INTO answered_questions 
                    (session_id, question_id, question_text, user_response, summary, answered_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (question['session_id'], question['question_id'], question['question_text'],
                     question['user_response'], question['summary'], question['answered_at']))
            
            # Sync conversation history
            for message in self.fallback_data.get('conversation_history', []):
                cursor.execute('''
                    INSERT OR IGNORE INTO conversation_history 
                    (session_id, role, message, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (message['session_id'], message['role'], message['message'], message['timestamp']))
            
            conn.commit()
            conn.close()
            
            # Clear fallback data after successful sync
            self.fallback_data = {}
            logger.info("Fallback data successfully synced to database")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync fallback data to database: {e}")
            return False
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get database health status and fallback information"""
        return {
            "connection_healthy": self.connection_healthy,
            "fallback_mode": self.fallback_mode,
            "fallback_data_count": {
                "sessions": len(self.fallback_data.get('sessions', [])),
                "answered_questions": len(self.fallback_data.get('answered_questions', [])),
                "conversation_messages": len(self.fallback_data.get('conversation_history', []))
            },
            "database_accessible": self.test_connection()
        }
    
    def get_answered_questions(self, session_id: int) -> List[Dict]:
        """Get all answered questions for a session"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT question_id, question_text, user_response, summary, answered_at
            FROM answered_questions
            WHERE session_id = ?
            ORDER BY answered_at ASC
        ''', (session_id,))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "question_id": row[0],
                "question_text": row[1],
                "user_response": row[2],
                "summary": row[3],
                "answered_at": row[4]
            }
            for row in rows
        ] 