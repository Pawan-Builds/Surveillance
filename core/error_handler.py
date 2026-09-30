import logging
import requests.exceptions
from datetime import datetime
from core.config_manager import ConfigManager

class ErrorHandler:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging configuration"""
        log_file = self.config.get('logging.file', 'wormgpt.log')
        log_level = self.config.get('logging.level', 'INFO')
        
        logging.basicConfig(
            filename=log_file,
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
    def handle_request_error(self, error, payload_type="unknown"):
        """Handle request errors with proper logging"""
        timestamp = datetime.now().isoformat()
        
        if isinstance(error, requests.exceptions.Timeout):
            message = f"Timeout while exfiltrating {payload_type}"
            logging.error(f"{timestamp} - {message}")
        elif isinstance(error, requests.exceptions.ConnectionError):
            message = f"Connection error while exfiltrating {payload_type}"
            logging.error(f"{timestamp} - {message}")
        elif isinstance(error, requests.exceptions.RequestException):
            message = f"Network Error while exfiltrating {payload_type}: {str(error)}"
            logging.error(f"{timestamp} - {message}")
        else:
            message = f"Unknown error while exfiltrating {payload_type}: {str(error)}"
            logging.error(f"{timestamp} - {message}")
            
        return message
