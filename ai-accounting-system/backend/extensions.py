import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()

# Use Redis for rate limiting if available, fallback to in-memory
_rate_limit_storage = os.environ.get(
    'RATELIMIT_STORAGE_URI',
    os.environ.get('REDIS_URL', 'memory://')
)

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri=_rate_limit_storage,
)

# Cache — initialized later in app factory via init_cache()
from cache import cache

# SocketIO — initialized later in app factory via init_socketio()
from websocket import socketio
