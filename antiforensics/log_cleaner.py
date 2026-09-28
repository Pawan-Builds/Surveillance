import subprocess
import os
from core.config_manager import ConfigManager

class LogCleaner:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def clean_system_logs(self):
        """Clear system logs to remove traces."""
        print("Cleaning system logs...")
        # Clear logcat
        subprocess.run(['adb', 'logcat', '-c'], stdout=subprocess.DEVNULL)
        # Clear dmesg
        subprocess.run(['adb', 'shell', 'dmesg', '-c'], stdout=subprocess.DEVNULL)
        # Clear specific app logs
        subprocess.run(['adb', 'shell', 'logcat', '-b', 'all', '-d'], stdout=subprocess.DEVNULL)