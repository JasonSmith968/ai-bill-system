"""AI-related Celery tasks — LLM analysis, agent execution, workflow orchestration."""

import json
import logging
import traceback
from celery_app import celery

logger = logging.getLogger(__name__)


def _update_task_record(task_id, status, result=None, error=None):
    """Update the TaskRecord in DB (runs inside Flask app context via ContextTask)."""
    from models.task_record import TaskRecord
    from extensions import db
    from datetime import datetime

    record = TaskRecord.query.filter_by(task_id=task_id).first()
    if not record:
        return
    record.status = status
    if status == 'running':
        record.started_at = datetime.utcnow()
    elif status in ('success', 'failed'):
        record.completed_at = datetime.utcnow()
    if result is not None:
        record.result = result
    if error is not None:
        record.error = error
    db.session.commit()


@celery.task(bind=True, queue='ai', max_retries=3, soft_time_limit=120, time_limit=150,
             name='tasks.ai_tasks.run_llm_analysis')
def run_llm_analysis(self, user_id, prompt, agent_name='finance'):
    """Run an LLM analysis task.

    Args:
        user_id: Owner of the analysis
        prompt: The prompt to send to the LLM
        agent_name: Which agent context to use

    Returns:
        dict with 'content', 'usage', 'model'
    """
    _update_task_record(self.request.id, 'running')

    try:
        from services.llm_client import get_llm_client
        from agents.memory import AgentMemoryService
        from agents.prompt_manager import get_prompt_manager

        llm = get_llm_client()
        pm = get_prompt_manager()
        memory = AgentMemoryService()

        # Build messages with system prompt + user context
        profile = memory.get_profile(user_id)
        system_prompt = pm.get_system_prompt(agent_name, user_profile=profile)
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt},
        ]

        result = llm.chat(messages)
        output = {
            'content': result['content'],
            'usage': result.get('usage', {}),
            'model': result.get('model', ''),
        }

        _update_task_record(self.request.id, 'success', result=output)
        return output

    except Exception as exc:
        logger.error(f"run_llm_analysis failed: {exc}")
        _update_task_record(self.request.id, 'failed', error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery.task(bind=True, queue='ai', max_retries=3, soft_time_limit=120, time_limit=150,
             name='tasks.ai_tasks.run_agent_task')
def run_agent_task(self, user_id, agent_name, task, params=None):
    """Run a specific agent with given task and params.

    Returns:
        dict — AgentResult.to_dict()
    """
    _update_task_record(self.request.id, 'running')

    try:
        from agents import get_manager
        from agents.base import AgentContext

        context = AgentContext(user_id=user_id)
        manager = get_manager()
        result = manager.run(agent_name, context, task=task, **(params or {}))

        output = {
            'result': result.to_dict(),
            'call_chain': context.call_chain,
        }

        _update_task_record(self.request.id, 'success', result=output)
        return output

    except Exception as exc:
        logger.error(f"run_agent_task failed: {exc}")
        _update_task_record(self.request.id, 'failed', error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery.task(bind=True, queue='ai', max_retries=2, soft_time_limit=180, time_limit=210,
             name='tasks.ai_tasks.run_workflow')
def run_workflow(self, user_id, workflow_name, params=None):
    """Execute a named workflow.

    Returns:
        dict with 'steps' (list of step results) and 'call_chain'
    """
    _update_task_record(self.request.id, 'running')

    try:
        from agents import get_manager
        from agents.base import AgentContext

        context = AgentContext(user_id=user_id)
        manager = get_manager()

        steps = []
        for event in manager.execute_workflow(workflow_name, context, **(params or {})):
            steps.append(event)

        output = {
            'steps': steps,
            'call_chain': context.call_chain,
        }

        _update_task_record(self.request.id, 'success', result=output)
        return output

    except Exception as exc:
        logger.error(f"run_workflow failed: {exc}")
        _update_task_record(self.request.id, 'failed', error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery.task(bind=True, queue='ai', max_retries=2, soft_time_limit=120, time_limit=150,
             name='tasks.ai_tasks.stream_llm_chat')
def stream_llm_chat(self, user_id, messages, sid):
    """Stream LLM chat response via SocketIO.

    Args:
        user_id: User ID
        messages: Chat message history
        sid: SocketIO session ID to push chunks to
    """
    _update_task_record(self.request.id, 'running')

    try:
        from services.llm_client import get_llm_client
        from websocket.events import emit_stream_chunk, emit_task_update

        llm = get_llm_client()
        emit_task_update(self.request.id, 'running', {'message': '正在生成...'})

        full_content = ''
        for chunk in llm.chat_stream(messages):
            full_content += chunk
            emit_stream_chunk(sid, chunk)

        emit_task_update(self.request.id, 'success', {'content': full_content})
        _update_task_record(self.request.id, 'success', result={'content': full_content})
        return {'content': full_content}

    except Exception as exc:
        logger.error(f"stream_llm_chat failed: {exc}")
        _update_task_record(self.request.id, 'failed', error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
