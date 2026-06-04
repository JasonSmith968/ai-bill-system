"""Flask-SocketIO initialization with Redis message queue for cross-process broadcasting."""

import os
import logging
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)

socketio = SocketIO()


def init_socketio(app):
    """Bind SocketIO to the Flask app.

    Uses Redis as message queue when available, enabling cross-process
    broadcasting between Gunicorn workers and Celery workers.
    """
    redis_url = app.config.get('REDIS_URL', os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))

    socketio.init_app(
        app,
        # SECURITY: fail closed — never default to wildcard '*'
        cors_allowed_origins=app.config.get('CORS_ORIGINS') or [],
        async_mode='threading',
        message_queue=redis_url,
        logger=False,
        engineio_logger=False,
    )

    # Import events to register handlers
    from websocket import events  # noqa: F401

    logger.info("SocketIO initialized (async_mode=threading, message_queue=%s)", redis_url)
    return socketio
