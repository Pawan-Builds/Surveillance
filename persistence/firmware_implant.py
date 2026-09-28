import os
import json
from core.config_manager import ConfigManager

class FirmwareImplant:
    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def generate_module(self, session_id: str):
        """Generates a Linux Kernel Module (LKM) for persistence."""
        module_name = f"wormgpt_persist_{session_id[:8]}"
        
        # C Code for the Kernel Module
        kcode = f"""
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/moduleparam.h>

static int __init wormgpt_init(void) {{
    printk(KERN_INFO "WormGPT Firmware Implant Loaded: {session_id}\\n");
    // Logic to register as a system service or hook init process
    return 0;
}}

static void __exit wormgpt_exit(void) {{
    printk(KERN_INFO "WormGPT Firmware Implant Unloaded\\n");
}}

module_init(wormgpt_init);
module_exit(wormgpt_exit);
MODULE_LICENSE("GPL");
MODULE_AUTHOR("WormGPT");
"""
        
        with open(f"persistence/{module_name}.c", "w") as f:
            f.write(kcode)
            
        # Generate Makefile
        makefile = f"""
obj-m += {module_name}.o
all:
\tmake -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules
clean:
\tmake -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean
"""
        with open(f"persistence/Makefile", "w") as f:
            f.write(makefile)
            
        print(f"Generated Kernel Module: persistence/{module_name}.c")

    def compile_module(self):
        """Compiles the module using make."""
        os.system("cd persistence && make")