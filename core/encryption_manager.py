import json
import os
import base64
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from core.config_manager import ConfigManager

class EncryptionManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.key = None
        self._initialize_encryption()
        
    def _initialize_encryption(self):
        """Initialize encryption with proper key management"""
        # Try to get key from config
        stored_key = self.config.get('database.encryption_key')
        
        if stored_key:
            try:
                # If it's a base64 encoded key, decode it
                self.key = base64.urlsafe_b64decode(stored_key.encode())
            except Exception:
                # If decoding fails, treat it as a password to derive a key
                self.key = self._derive_key_from_password(stored_key)
        else:
            # Generate a new key if none exists
            self.key = Fernet.generate_key()
            # Store the key in config for future use
            self.config.set('database.encryption_key', base64.urlsafe_b64encode(self.key).decode())
            print(f"[+] Generated new encryption key and stored in config")
            
        # Initialize Fernet cipher
        self.cipher = Fernet(self.key)
        
    def _derive_key_from_password(self, password, salt=None):
        """Derive encryption key from password using PBKDF2"""
        if salt is None:
            # Generate a random salt
            salt = os.urandom(16)
            # Store salt in config for future use
            self.config.set('database.encryption_salt', base64.urlsafe_b64encode(salt).decode())
        else:
            # Use provided salt or retrieve from config
            if isinstance(salt, str):
                salt = base64.urlsafe_b64decode(salt.encode())
        
        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
        
    def encrypt_data(self, data):
        """Encrypt data using Fernet (AES-128 in CBC mode)"""
        if data is None:
            return None
            
        try:
            # Convert data to JSON string if it's a dict or list
            if isinstance(data, (dict, list)):
                data = json.dumps(data)
            
            # Ensure data is bytes
            if isinstance(data, str):
                data = data.encode('utf-8')
                
            # Encrypt the data
            encrypted_data = self.cipher.encrypt(data)
            
            # Return base64 encoded encrypted data for storage
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            print(f"[!] Error encrypting data: {str(e)}")
            raise
            
    def decrypt_data(self, encrypted_data):
        """Decrypt data"""
        if encrypted_data is None:
            return None
            
        try:
            # Decode from base64 if needed
            if isinstance(encrypted_data, str):
                encrypted_data = base64.urlsafe_b64decode(encrypted_data.encode())
                
            # Decrypt the data
            decrypted_data = self.cipher.decrypt(encrypted_data)
            
            # Try to parse as JSON, otherwise return as string
            try:
                return json.loads(decrypted_data.decode('utf-8'))
            except json.JSONDecodeError:
                return decrypted_data.decode('utf-8')
        except Exception as e:
            print(f"[!] Error decrypting data: {str(e)}")
            raise
            
    def rotate_key(self, new_password=None):
        """Generate a new encryption key and optionally re-encrypt existing data"""
        if new_password:
            # Derive new key from password
            salt = os.urandom(16)
            self.config.set('database.encryption_salt', base64.urlsafe_b64encode(salt).decode())
            self.key = self._derive_key_from_password(new_password, salt)
        else:
            # Generate a completely new random key
            self.key = Fernet.generate_key()
            
        # Update the stored key
        self.config.set('database.encryption_key', base64.urlsafe_b64encode(self.key).decode())
        
        # Re-initialize cipher
        self.cipher = Fernet(self.key)
        
        return self.key
