import os
import shutil
from core.config_manager import ConfigManager

class SecureDelete:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def delete_file_securely(self, file_path: str, passes: int = 3):
        """Overwrite file multiple times before deleting."""
        if not os.path.exists(file_path):
            return

        # Get file size
        size = os.path.getsize(file_path)
        
        # Overwrite with random data
        with open(file_path, 'wb') as f:
            f.write(os.urandom(size))
        
        # Delete
        os.remove(file_path)
        print(f"Securely deleted {file_path}")