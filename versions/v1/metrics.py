"""
V1 Metrics Database Module
Handles session tracking and metrics collection for V1 voice agent.
"""

import sqlite3
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class MetricsDatabase:
    """SQLite-based metrics database for tracking voice agent sessions"""
    
    def __init__(self, db_path: str = "v1_metrics.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with required tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    duration_seconds REAL,
                    total_exchanges INTEGER DEFAULT 0,
                    total_errors INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                )
            """)
            
            # Conversation exchanges table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_exchanges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    user_input TEXT,
                    ai_response TEXT,
                    processing_time REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            # Errors table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    error_type TEXT,
                    severity TEXT,
                    error_message TEXT,
                    context TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            # Network metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS network_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    latency REAL,
                    jitter REAL,
                    packet_loss REAL,
                    buffer_size INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            conn.close()
    
    def create_session(self, session_id: str) -> bool:
        """Create a new session record"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sessions (session_id, start_time, status)
                    VALUES (?, CURRENT_TIMESTAMP, 'active')
                """, (session_id,))
                conn.commit()
                logger.info(f"Created session: {session_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            return False
    
    def end_session(self, session_id: str, duration_seconds: float, 
                   total_exchanges: int = 0, total_errors: int = 0) -> bool:
        """End a session and record final metrics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE sessions 
                    SET end_time = CURRENT_TIMESTAMP,
                        duration_seconds = ?,
                        total_exchanges = ?,
                        total_errors = ?,
                        status = 'completed'
                    WHERE session_id = ?
                """, (duration_seconds, total_exchanges, total_errors, session_id))
                conn.commit()
                logger.info(f"Ended session: {session_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to end session {session_id}: {e}")
            return False
    
    def record_metrics(self, session_id: str, metrics: Dict[str, Any]) -> bool:
        """Record general metrics for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Record network metrics if present
                if 'network' in metrics:
                    network = metrics['network']
                    cursor.execute("""
                        INSERT INTO network_metrics 
                        (session_id, latency, jitter, packet_loss, buffer_size)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        session_id,
                        network.get('latency', 0),
                        network.get('jitter', 0),
                        network.get('packet_loss', 0),
                        network.get('buffer_size', 0)
                    ))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to record metrics for session {session_id}: {e}")
            return False
    
    def record_conversation_exchange(self, session_id: str, user_input: str, 
                                   ai_response: str, processing_time: float) -> bool:
        """Record a conversation exchange"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO conversation_exchanges 
                    (session_id, user_input, ai_response, processing_time)
                    VALUES (?, ?, ?, ?)
                """, (session_id, user_input, ai_response, processing_time))
                
                # Update session exchange count
                cursor.execute("""
                    UPDATE sessions 
                    SET total_exchanges = total_exchanges + 1
                    WHERE session_id = ?
                """, (session_id,))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to record conversation exchange for session {session_id}: {e}")
            return False
    
    def record_error(self, session_id: str, error_type: str, severity: str, 
                    error_message: str, context: Dict = None) -> bool:
        """Record an error for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO errors 
                    (session_id, error_type, severity, error_message, context)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id, 
                    error_type, 
                    severity, 
                    error_message,
                    json.dumps(context) if context else None
                ))
                
                # Update session error count
                cursor.execute("""
                    UPDATE sessions 
                    SET total_errors = total_errors + 1
                    WHERE session_id = ?
                """, (session_id,))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to record error for session {session_id}: {e}")
            return False
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent sessions with basic metrics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        session_id,
                        start_time,
                        end_time,
                        duration_seconds,
                        total_exchanges,
                        total_errors,
                        status
                    FROM sessions 
                    ORDER BY start_time DESC 
                    LIMIT ?
                """, (limit,))
                
                sessions = []
                for row in cursor.fetchall():
                    sessions.append({
                        'session_id': row['session_id'],
                        'start_time': row['start_time'],
                        'end_time': row['end_time'],
                        'duration_seconds': row['duration_seconds'],
                        'total_exchanges': row['total_exchanges'],
                        'total_errors': row['total_errors'],
                        'status': row['status']
                    })
                
                return sessions
        except Exception as e:
            logger.error(f"Failed to get recent sessions: {e}")
            return []
    
    def get_session_metrics(self, session_id: str) -> Dict:
        """Get detailed metrics for a specific session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get session info
                cursor.execute("""
                    SELECT * FROM sessions WHERE session_id = ?
                """, (session_id,))
                session = cursor.fetchone()
                
                if not session:
                    return {'error': 'Session not found'}
                
                # Get conversation exchanges
                cursor.execute("""
                    SELECT * FROM conversation_exchanges 
                    WHERE session_id = ? 
                    ORDER BY timestamp
                """, (session_id,))
                exchanges = [dict(row) for row in cursor.fetchall()]
                
                # Get errors
                cursor.execute("""
                    SELECT * FROM errors 
                    WHERE session_id = ? 
                    ORDER BY timestamp
                """, (session_id,))
                errors = [dict(row) for row in cursor.fetchall()]
                
                # Get network metrics
                cursor.execute("""
                    SELECT * FROM network_metrics 
                    WHERE session_id = ? 
                    ORDER BY timestamp
                """, (session_id,))
                network_metrics = [dict(row) for row in cursor.fetchall()]
                
                return {
                    'session': dict(session),
                    'exchanges': exchanges,
                    'errors': errors,
                    'network_metrics': network_metrics
                }
        except Exception as e:
            logger.error(f"Failed to get session metrics for {session_id}: {e}")
            return {'error': str(e)}
    
    def get_aggregated_metrics(self, hours: int = 24) -> Dict:
        """Get aggregated metrics for the specified time period"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Calculate time threshold
                threshold = datetime.now() - timedelta(hours=hours)
                
                # Get session count
                cursor.execute("""
                    SELECT COUNT(*) as total_sessions,
                           COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
                           COUNT(CASE WHEN status = 'active' THEN 1 END) as active_sessions
                    FROM sessions 
                    WHERE start_time >= ?
                """, (threshold.isoformat(),))
                session_stats = cursor.fetchone()
                
                # Get total exchanges
                cursor.execute("""
                    SELECT COUNT(*) as total_exchanges,
                           AVG(processing_time) as avg_processing_time
                    FROM conversation_exchanges ce
                    JOIN sessions s ON ce.session_id = s.session_id
                    WHERE s.start_time >= ?
                """, (threshold.isoformat(),))
                exchange_stats = cursor.fetchone()
                
                # Get error stats
                cursor.execute("""
                    SELECT COUNT(*) as total_errors,
                           error_type,
                           severity
                    FROM errors e
                    JOIN sessions s ON e.session_id = s.session_id
                    WHERE s.start_time >= ?
                    GROUP BY error_type, severity
                """, (threshold.isoformat(),))
                error_stats = [dict(row) for row in cursor.fetchall()]
                
                return {
                    'period_hours': hours,
                    'sessions': dict(session_stats),
                    'exchanges': dict(exchange_stats),
                    'errors': error_stats
                }
        except Exception as e:
            logger.error(f"Failed to get aggregated metrics: {e}")
            return {'error': str(e)}
    
    def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up old data to prevent database bloat"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Calculate cutoff date
                cutoff = datetime.now() - timedelta(days=days)
                
                # Delete old sessions and related data
                cursor.execute("DELETE FROM sessions WHERE start_time < ?", (cutoff.isoformat(),))
                cursor.execute("DELETE FROM conversation_exchanges WHERE timestamp < ?", (cutoff.isoformat(),))
                cursor.execute("DELETE FROM errors WHERE timestamp < ?", (cutoff.isoformat(),))
                cursor.execute("DELETE FROM network_metrics WHERE timestamp < ?", (cutoff.isoformat(),))
                
                conn.commit()
                logger.info(f"Cleaned up data older than {days} days")
                return True
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return False

# Global metrics database instance
_metrics_db = None

def get_metrics_db() -> MetricsDatabase:
    """Get the global metrics database instance"""
    global _metrics_db
    if _metrics_db is None:
        _metrics_db = MetricsDatabase()
    return _metrics_db 