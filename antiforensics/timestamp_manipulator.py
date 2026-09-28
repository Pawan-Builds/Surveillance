import os
import stat
import time
from core.config_manager import ConfigManager

class TimestampManipulator:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def manipulate_timestamps(self, path: str, target_time: str):
        """Alter file access and modification times."""
        # Convert target time to timestamp
        t = time.mktime(time.strptime(target_time, "%Y-%m-%d %H:%M:%S"))
        
        # Logic to change mtime and atime
        os.utime(path, (t, t))
        print(f"Manipulated timestamps for {path}")

        # Also clear access time (atime) to hide access
        # On Linux: touch -a <file>
        os.system(f'touch -a "{path}"')