import logging
import socket
import errno
from core.config_manager import ConfigManager

class PortManager:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.default_port = 8080  # Changed from 5000 to avoid conflicts
        self.min_port = 1024
        self.max_port = 65535
        
    def get_valid_port(self):
        """Get a valid port from the configuration"""
        port = self.config.get('c2.port', 8080)
    
    # Check if the port is available
        if self._is_port_available(port):
            return port
    
    # Try to find an available port
        for p in range(port, port + 100):
            if self._is_port_available(p):
                logging.warning(f"Port {port} is not available, using port {p} instead")
                return p
    
    # If no available port found, raise an exception
        raise RuntimeError("No available ports found")
    
    def _is_port_available(self, port):
        """Check if a port is available"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                return result != 0
        except Exception:
            return False
    
    def _find_available_port(self, start_port):
        """Find an available port starting from start_port"""
        for port in range(start_port, self.max_port):
            if self._is_port_available(port):
                print(f"[+] Using available port: {port}")
                return port
        raise RuntimeError(f"No available ports in range {start_port}-{self.max_port}")
