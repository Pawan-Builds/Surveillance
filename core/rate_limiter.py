import os
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis

class RateLimiter:
    def __init__(self, app: Flask, config_manager, storage_uri=None):
        self.app = app
        self.config = config_manager
        
        # Configure storage
        if storage_uri:
            try:
                self.storage = redis.from_url(storage_uri)
            except Exception:
                self.storage = "memory://"
        else:
            self.storage = "memory://"
            
        # Initialize limiter with the correct arguments
        if storage_uri:
            self.limiter = Limiter(
                get_remote_address,
                app=app,
                storage_uri=storage_uri,
                default_limits=self.config.get('rate_limiting.default_limits', "200 per day, 50 per hour")
            )
        else:
            self.limiter = Limiter(
                get_remote_address,
                app=app,
                storage_uri="memory://",
                default_limits=self.config.get('rate_limiting.default_limits', "200 per day, 50 per hour")
            )
        
    def apply_limits(self, view_func, limits):
        """Apply rate limits to a view function"""
        return self.limiter.limit(limits)(view_func)
