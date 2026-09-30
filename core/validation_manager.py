import re
import json
from flask import request, jsonify
from core.config_manager import ConfigManager

class ValidationManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        
    def validate_session_id(self, session_id):
        """Validate session_id format"""
        if not session_id or not re.match(r'^[a-zA-Z0-9]{8,64}$', session_id):
            return False, "Invalid session_id format"
        return True, None
        
    def validate_payload_size(self, payload):
        """Validate payload size"""
        max_size = self.config.get('c2.max_payload_size', 1048576)  # 1MB default
        if len(str(payload)) > max_size:
            return False, f"Payload too large. Max size: {max_size} bytes"
        return True, None
        
    def validate_json(self, data):
        """Validate JSON data"""
        try:
            json.loads(data)
            return True, None
        except (ValueError, TypeError):
            return False, "Invalid JSON format"
