import subprocess
import os
import time
import re
from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager

class ADBManager:
    def __init__(self, config_manager: ConfigManager, db_manager: DatabaseManager):
        self.config = config_manager
        self.db = db_manager
        self.device_id = None

    def connect(self):
        """Connect to the first available device."""
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
        devices = re.findall(r'(\w+)\s+device', result.stdout)
        if devices:
            self.device_id = devices[0]
            print(f"[*] Connected to device: {self.device_id}")
            return True
        else:
            print("[!] No devices found. Ensure ADB is running and device is connected.")
            return False

    def install_apk(self, apk_path):
        """Install APK without user interaction."""
        print(f"[*] Installing {apk_path}...")
        cmd = ['adb', '-s', self.device_id, 'install', '-r', apk_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if 'Success' in result.stdout:
            print("[+] APK Installed successfully.")
            return True
        else:
            print(f"[!] Installation failed: {result.stderr}")
            return False

    def run_background_service(self, package_name):
        """Start the app as a background service."""
        print(f"[*] Starting service for {package_name}...")
        cmd = ['adb', '-s', self.device_id, 'shell', 'am', 'startservice', '-n', f'{package_name}/.Service']
        subprocess.run(cmd)

    def clear_logs(self):
        """Clear system logs to hide activity."""
        subprocess.run(['adb', '-s', self.device_id, 'logcat', '-c'])

    def get_active_processes(self):
        """List running processes."""
        result = subprocess.run(['adb', '-s', self.device_id, 'shell', 'ps'], capture_output=True, text=True)
        return result.stdout

    def dump_heap(self, process_name):
        """Dump heap memory for analysis."""
        print(f"[*] Dumping heap for {process_name}...")
        # Requires root typically
        cmd = ['adb', '-s', self.device_id, 'shell', 'su', '-c', f'cat /proc/{process_name}/maps']
        subprocess.run(cmd)