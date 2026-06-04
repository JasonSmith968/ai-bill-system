"""Centralized logging configuration for the AI Accounting System.

Uses ConcurrentRotatingFileHandler for thread-safe log rotation on all
platforms (Windows [WinError 32] fix). Falls back to stdlib
RotatingFileHandler when concurrent-log-handler is not installed.
"""

import os
import logging
import logging.handlers
from datetime import datetime

try:
    from concurrent_log_handler import ConcurrentRotatingFileHandler as _FileHandler
except ImportError:
    _FileHandler = logging.handlers.RotatingFileHandler


def _make_handler(log_dir, filename, level, formatter, max_bytes=10 * 1024 * 1024):
    """Create a file handler with thread-safe rotation."""
    handler = _FileHandler(
        os.path.join(log_dir, filename),
        maxBytes=max_bytes,
        backupCount=10,
        encoding='utf-8',
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def setup_logging(app):
    """Configure application logging with file rotation and separation."""
    log_dir = app.config.get('LOG_DIR', 'logs')
    log_level = app.config.get('LOG_LEVEL', 'INFO')

    # Create logs directory
    os.makedirs(log_dir, exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Formatters
    detailed_fmt = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s [%(name)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    access_fmt = logging.Formatter(
        '[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if app.debug else logging.INFO)
    console.setFormatter(detailed_fmt)
    root_logger.addHandler(console)

    # Error log file (ERROR and above)
    root_logger.addHandler(_make_handler(log_dir, 'error.log', logging.ERROR, detailed_fmt))

    # Application log file (INFO and above)
    root_logger.addHandler(_make_handler(log_dir, 'app.log', logging.INFO, detailed_fmt))

    # Access log file (dedicated)
    access_logger = logging.getLogger('access')
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False
    access_logger.addHandler(_make_handler(log_dir, 'access.log', logging.INFO, access_fmt))

    # Business event logger
    biz_logger = logging.getLogger('business')
    biz_logger.setLevel(logging.INFO)
    biz_logger.propagate = False
    biz_logger.addHandler(_make_handler(log_dir, 'business.log', logging.INFO, detailed_fmt))

    # Agent execution logger
    agent_logger = logging.getLogger('agent')
    agent_logger.setLevel(logging.INFO)
    agent_logger.propagate = False
    agent_logger.addHandler(_make_handler(log_dir, 'agent.log', logging.INFO, detailed_fmt))

    handler_type = type(root_logger.handlers[-1]).__name__
    app.logger.info(f"Logging initialized: level={log_level}, dir={log_dir}, handler={handler_type}")

    return app
