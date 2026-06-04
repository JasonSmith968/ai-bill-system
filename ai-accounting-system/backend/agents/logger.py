"""Structured logging for agent executions."""

import collections
import logging
from datetime import datetime


class AgentLogger:
    """Logs agent executions to memory, file, and database."""

    def __init__(self, max_history=200):
        self._history = collections.deque(maxlen=max_history)
        self._logger = logging.getLogger('agent')

    def log_execution(self, context, result):
        entry = {
            'request_id': context.request_id,
            'user_id': context.user_id,
            'agent': result.agent_name,
            'success': result.success,
            'duration_ms': result.duration_ms,
            'error': result.error or None,
            'output_keys': list(result.data.keys()),
            'timestamp': datetime.utcnow().isoformat()
        }
        self._history.appendleft(entry)

        level = logging.INFO if result.success else logging.WARNING
        self._logger.log(
            level,
            f"Agent[{result.agent_name}] {'OK' if result.success else 'FAIL'} "
            f"{result.duration_ms:.0f}ms req={context.request_id}"
        )

        self._persist_to_db(entry)

    def get_recent(self, limit=50):
        return list(self._history)[:limit]

    def get_by_request(self, request_id):
        return [e for e in self._history if e['request_id'] == request_id]

    def _persist_to_db(self, entry):
        try:
            from models.agent_log import AgentExecutionLog
            from extensions import db
            log = AgentExecutionLog(
                request_id=entry['request_id'],
                user_id=entry['user_id'],
                agent_name=entry['agent'],
                success=entry['success'],
                duration_ms=entry['duration_ms'],
                error_message=entry.get('error'),
                output_keys=entry.get('output_keys', []),
                created_at=datetime.utcnow()
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            pass
