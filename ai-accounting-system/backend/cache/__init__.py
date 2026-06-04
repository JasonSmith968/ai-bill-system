"""Flask-Caching initialization with Redis backend."""

import os
import logging
from flask_caching import Cache

logger = logging.getLogger(__name__)

cache = Cache()


def init_cache(app):
    """Bind the cache to the Flask app."""
    cache.init_app(app)
    logger.info("Cache initialized (type=%s, timeout=%s)",
                app.config.get('CACHE_TYPE', 'RedisCache'),
                app.config.get('CACHE_DEFAULT_TIMEOUT', 300))
    return cache
