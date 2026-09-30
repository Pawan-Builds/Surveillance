# Replace your core/secure_comms.py with this improved version:
import os
import ssl
import datetime
from flask import Flask
from flask_socketio import SocketIO
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

class SecureCommunications:
    def __init__(self, config_manager):
        self.config = config_manager
        
    def get_ssl_context(self):
        """Create SSL context for secure communications"""
        # Get certificate paths from config or use defaults
        cert_file = self.config.get('c2.ssl_cert', 'certs/server.crt')
        key_file = self.config.get('c2.ssl_key', 'certs/server.key')
        
        # Ensure paths are strings
        if cert_file is None:
            cert_file = 'certs/server.crt'
        if key_file is None:
            key_file = 'certs/server.key'
            
        # Create certs directory if it doesn't exist
        cert_dir = os.path.dirname(cert_file)
        if cert_dir:
            os.makedirs(cert_dir, exist_ok=True)
        
        # Generate self-signed certificates if they don't exist
        if not os.path.exists(cert_file) or not os.path.exists(key_file):
            self._generate_self_signed_cert(cert_file, key_file)
            
        # Create SSL context
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        
        return context
        
    def _generate_self_signed_cert(self, cert_file, key_file):
        """Generate a self-signed certificate for development/testing"""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Surveillance Framework"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("127.0.0.1"),
                x509.DNSName(self.config.get('c2.host', '0.0.0.0')),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write certificate and key to files
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
            
        with open(key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
            
        print(f"[+] Generated self-signed certificate: {cert_file}")
        print(f"[+] Generated private key: {key_file}")
        
    def start_secure_server(self, app: Flask, host: str, port: int, socketio: SocketIO):
        """Get SSL context for secure communications"""
    # This method should only return the SSL context, not start the server
        return self.get_ssl_context()
            
    def _check_ssl_certificates(self):
        """Check if SSL certificates are valid"""
        cert_file = self.config.get('c2.ssl_cert', 'certs/server.crt')
        key_file = self.config.get('c2.ssl_key', 'certs/server.key')
        
        if not os.path.exists(cert_file) or not os.path.exists(key_file):
            return False
            
        try:
            # Load and validate certificate
            with open(cert_file, 'rb') as f:
                cert_data = f.read()
            cert = x509.load_pem_x509_certificate(cert_data)
            
            # Check if certificate is expired
            if cert.not_valid_after < datetime.datetime.now():
                return False
                
            return True
        except Exception:
            return False
