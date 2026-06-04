"""Unified error response helpers for SSE streams and JSON endpoints."""

import json


def sse_error(message):
    """Unified SSE error event format: {"type": "error", "message": "..."}"""
    return f'data: {json.dumps({"type": "error", "message": message})}\n\n'
