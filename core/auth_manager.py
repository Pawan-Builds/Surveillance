from functools import wraps
from flask import request, jsonify
from core.config_manager import ConfigManager

class AuthManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        
    def require_auth(self, f):
        """Decorator to require authentication"""
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.headers.get('X-Auth-Token')
            if not token or token != self.config.get('c2.auth_token'):
                return jsonify({'error': 'Unauthorized'}), 401
            return f(*args, **kwargs)
        return decorated
