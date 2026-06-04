"""SocketIO event handlers — connect, chat, agent, workflow, task subscription."""

import json
import logging
from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from websocket import socketio

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------

@socketio.on('connect')
def handle_connect():
    """Authenticate and register the client.

    Expects JWT token in query string: ?token=<jwt>
    """
    from utils.jwt_helper import verify_token

    token = request.args.get('token', '')
    if not token:
        logger.warning("SocketIO connect rejected: no token")
        return False  # Reject

    try:
        payload = verify_token(token)
        if not payload:
            return False
        user_id = payload.get('user_id')
        if not user_id:
            return False
        # Store user_id and tenant_id on the session
        from flask_socketio import session
        session['user_id'] = user_id
        session['tenant_id'] = payload.get('tenant_id')
        join_room(f'user_{user_id}')
        logger.info(f"SocketIO connected: user={user_id} sid={request.sid}")
        emit('connected', {'user_id': user_id, 'sid': request.sid})
    except Exception as e:
        logger.warning(f"SocketIO auth failed: {e}")
        return False


@socketio.on('disconnect')
def handle_disconnect():
    from flask_socketio import session
    user_id = session.get('user_id')
    if user_id:
        leave_room(f'user_{user_id}')
    logger.info(f"SocketIO disconnected: user={user_id} sid={request.sid}")


# ---------------------------------------------------------------------------
# Task subscription
# ---------------------------------------------------------------------------

@socketio.on('subscribe_task')
def handle_subscribe_task(data):
    """Subscribe to updates for a specific Celery task."""
    try:
        task_id = data.get('task_id')
        if task_id:
            join_room(f'task_{task_id}')
            emit('subscribed', {'task_id': task_id})
    except Exception as e:
        logger.error(f"subscribe_task error: {e}")
        emit('error', {'message': '订阅任务失败'})


@socketio.on('unsubscribe_task')
def handle_unsubscribe_task(data):
    try:
        task_id = data.get('task_id')
        if task_id:
            leave_room(f'task_{task_id}')
    except Exception as e:
        logger.error(f"unsubscribe_task error: {e}")


# ---------------------------------------------------------------------------
# Chat via WebSocket (alternative to SSE)
# ---------------------------------------------------------------------------

@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle a chat message — dispatch to LLM via Celery and stream back.

    Frontend sends: { message: str }
    Backend emits:  llm_chunk { content } → llm_done { content } | llm_error { error }
    """
    from flask_socketio import session

    user_id = session.get('user_id')
    if not user_id:
        emit('llm_error', {'error': '未认证'})
        return

    message = data.get('message', '').strip()
    if not message:
        emit('llm_error', {'error': '消息不能为空'})
        return

    # Build messages for LLM
    messages = [{'role': 'user', 'content': message}]

    try:
        from services.llm_client import get_llm_client
        from agents.prompt_manager import get_prompt_manager
        from agents.memory import AgentMemoryService

        llm = get_llm_client()
        pm = get_prompt_manager()
        memory = AgentMemoryService()

        profile = memory.get_profile(user_id)
        system_prompt = pm.get_system_prompt('finance', user_profile=profile)
        full_messages = [
            {'role': 'system', 'content': system_prompt},
            *messages,
        ]

        full_content = ''
        for chunk in llm.chat_stream(full_messages):
            full_content += chunk
            emit('llm_chunk', {'content': chunk})

        emit('llm_done', {'content': full_content})

    except Exception as e:
        logger.error(f"WebSocket chat error: {e}")
        emit('llm_error', {'error': '处理失败，请重试'})


# ---------------------------------------------------------------------------
# Agent run via WebSocket
# ---------------------------------------------------------------------------

@socketio.on('agent_run')
def handle_agent_run(data):
    """Run an agent and stream results via WebSocket.

    Frontend sends: { agent: str, task: str, params: dict }
    Backend emits:  agent_start → agent_done | agent_error
    """
    from flask_socketio import session

    user_id = session.get('user_id')
    if not user_id:
        emit('agent_error', {'error': '未认证'})
        return

    agent_name = data.get('agent', '')
    task = data.get('task', '')
    params = data.get('params', {})

    if not agent_name:
        emit('agent_error', {'error': '请指定 agent'})
        return

    try:
        from agents import get_manager
        from agents.base import AgentContext

        context = AgentContext(user_id=user_id)
        manager = get_manager()

        emit('agent_start', {'agent': agent_name, 'task': task})

        result = manager.run(agent_name, context, task=task, **params)

        emit('agent_done', {
            'agent': agent_name,
            'result': result.to_dict(),
            'call_chain': context.call_chain,
            'duration_ms': result.duration_ms,
        })

    except Exception as e:
        logger.error(f"WebSocket agent_run error: {e}")
        emit('agent_error', {'error': 'Agent 执行失败'})


# ---------------------------------------------------------------------------
# Workflow run via WebSocket
# ---------------------------------------------------------------------------

@socketio.on('workflow_run')
def handle_workflow_run(data):
    """Execute a workflow and stream step events via WebSocket.

    Frontend sends: { workflow_name: str, params: dict }
    Backend emits:  workflow_step (per step) → workflow_done | workflow_error
    """
    from flask_socketio import session

    user_id = session.get('user_id')
    if not user_id:
        emit('workflow_error', {'error': '未认证'})
        return

    workflow_name = data.get('workflow_name', '')
    params = data.get('params', {})

    if not workflow_name:
        emit('workflow_error', {'error': '请指定工作流'})
        return

    try:
        from agents import get_manager
        from agents.base import AgentContext

        context = AgentContext(user_id=user_id)
        manager = get_manager()

        for event in manager.execute_workflow(workflow_name, context, **params):
            emit('workflow_step', event)

        emit('workflow_done', {
            'workflow': workflow_name,
            'call_chain': context.call_chain,
        })

    except Exception as e:
        logger.error(f"WebSocket workflow_run error: {e}")
        emit('workflow_error', {'error': '工作流执行失败'})


# ---------------------------------------------------------------------------
# Global SocketIO error handler
# ---------------------------------------------------------------------------

@socketio.on_error_default
def default_error_handler(e):
    logger.error(f"SocketIO default error: {e}")
    emit('error', {'message': '服务器内部错误'})


# ---------------------------------------------------------------------------
# Utility functions (called from Celery tasks)
# ---------------------------------------------------------------------------

def emit_task_update(task_id, status, data=None):
    """Emit a task status update to subscribers. Safe to call from Celery workers
    because SocketIO uses Redis as message queue for cross-process delivery."""
    payload = {'task_id': task_id, 'status': status}
    if data:
        payload.update(data)
    socketio.emit('task_update', payload, room=f'task_{task_id}')


def emit_stream_chunk(sid, chunk):
    """Push an LLM stream chunk to a specific client session."""
    socketio.emit('llm_chunk', {'content': chunk}, room=sid)


def emit_user_event(user_id, event, data):
    """Push an event to a specific user's room."""
    socketio.emit(event, data, room=f'user_{user_id}')
