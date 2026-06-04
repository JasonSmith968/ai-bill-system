"""Unified Agent API v2 — single entry point for all agent operations.

Routes:
  POST /chat         — Natural language → AgentRouter dispatch + SSE streaming
  POST /run          — Direct agent call {agent, task, params}
  POST /workflow     — Execute workflow {workflow_name, params}
  POST /tools/execute — Call tool {tool_name, params}
  GET  /tools        — Available tool list
  GET  /memory       — User memories
  DELETE /memory/<key> — Delete memory
  GET  /templates    — Prompt templates (admin)
  PUT  /templates/<id> — Update template (admin)
"""

import json
import logging
from flask import Blueprint, request, jsonify, Response, stream_with_context
from utils.jwt_helper import token_required
from security.rbac import require_permission
from agents.base import AgentContext
from agents import get_manager

logger = logging.getLogger(__name__)

agent_v2_bp = Blueprint('agent_v2', __name__)


# ------------------------------------------------------------------
# POST /chat — Natural language entry point with SSE streaming
# ------------------------------------------------------------------
@agent_v2_bp.route('/chat', methods=['POST'])
@token_required
@require_permission('ai:call')
def chat():
    """Natural language entry — AgentRouter classifies intent and dispatches."""
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': '请输入消息'}), 400

    from flask import g
    context = AgentContext(
        user_id=request.current_user.id,
        request_id=g.get('request_id', ''),
    )
    manager = get_manager()

    # Classify intent
    route_result = manager.route(message, context)
    agent_name = route_result['agent']
    task = route_result['task']
    params = route_result.get('params', {})
    params['message'] = message

    def generate():
        try:
            yield f'data: {json.dumps({"type": "route", "agent": agent_name, "task": task, "confidence": route_result.get("confidence", 0), "source": route_result.get("source", "")})}\n\n'

            yield f'data: {json.dumps({"type": "agent_start", "agent": agent_name})}\n\n'

            result = manager.run(agent_name, context, task=task, **params)

            yield f'data: {json.dumps({"type": "agent_done", "agent": agent_name, "duration_ms": result.duration_ms})}\n\n'

            if result.success:
                # Stream the content
                content = result.data.get('content') or result.data.get('recommendations') or \
                          result.data.get('tax_advice') or result.data.get('investment_advice') or \
                          result.data.get('report') or result.data.get('summary') or ''

                if content:
                    # If it's a long string, stream it in chunks
                    chunk_size = 50
                    for i in range(0, len(content), chunk_size):
                        yield f'data: {json.dumps({"type": "content", "payload": content[i:i+chunk_size]})}\n\n'
                else:
                    yield f'data: {json.dumps({"type": "content", "payload": json.dumps(result.data, ensure_ascii=False)})}\n\n'
            else:
                from utils.error_helpers import sse_error
                yield sse_error(result.error)

            yield f'data: {json.dumps({"type": "done", "call_chain": context.call_chain})}\n\n'

        except Exception as e:
            logger.error(f"Agent v2 chat error: {e}")
            from utils.error_helpers import sse_error
            yield sse_error('处理失败，请重试')

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


# ------------------------------------------------------------------
# POST /run — Direct agent invocation
# ------------------------------------------------------------------
@agent_v2_bp.route('/run', methods=['POST'])
@token_required
@require_permission('ai:call')
def run_agent():
    """Directly run a specific agent with given task and params."""
    data = request.get_json() or {}
    agent_name = data.get('agent', '')
    task = data.get('task', '')
    params = data.get('params', {})

    if not agent_name:
        return jsonify({'error': '请指定 agent'}), 400

    from flask import g
    context = AgentContext(
        user_id=request.current_user.id,
        request_id=g.get('request_id', ''),
    )
    manager = get_manager()

    result = manager.run(agent_name, context, task=task, **params)

    return jsonify({
        'result': result.to_dict(),
        'call_chain': context.call_chain,
        'context_data': {k: context.get(k) for k in context.keys()
                         if not k.startswith('_')}
    })


# ------------------------------------------------------------------
# POST /workflow — Execute a named workflow
# ------------------------------------------------------------------
@agent_v2_bp.route('/workflow', methods=['POST'])
@token_required
@require_permission('ai:call')
def run_workflow():
    """Execute a named workflow with SSE streaming."""
    data = request.get_json() or {}
    workflow_name = data.get('workflow_name', '')
    params = data.get('params', {})

    if not workflow_name:
        return jsonify({'error': '请指定工作流名称'}), 400

    from flask import g
    context = AgentContext(
        user_id=request.current_user.id,
        request_id=g.get('request_id', ''),
    )
    manager = get_manager()

    def generate():
        try:
            for event in manager.execute_workflow(workflow_name, context, **params):
                yield f'data: {json.dumps(event)}\n\n'

            # Final context data
            yield f'data: {json.dumps({"type": "done", "call_chain": context.call_chain, "context_data": {k: context.get(k) for k in context.keys() if not k.startswith("_")}})}\n\n'

        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            from utils.error_helpers import sse_error
            yield sse_error(str(e))

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


# ------------------------------------------------------------------
# GET /workflows — List available workflows
# ------------------------------------------------------------------
@agent_v2_bp.route('/workflows', methods=['GET'])
@token_required
def list_workflows():
    """List available workflows."""
    from agents.workflow import get_workflow_engine
    engine = get_workflow_engine()
    return jsonify({'workflows': engine.list_workflows()})


# ------------------------------------------------------------------
# POST /tools/execute — Call a tool
# ------------------------------------------------------------------
@agent_v2_bp.route('/tools/execute', methods=['POST'])
@token_required
@require_permission('ai:call')
def execute_tool():
    """Execute a registered tool."""
    data = request.get_json() or {}
    tool_name = data.get('tool_name', '')
    params = data.get('params', {})

    if not tool_name:
        return jsonify({'error': '请指定工具名称'}), 400

    manager = get_manager()
    result = manager.tool_registry.execute(tool_name, user_id=request.current_user.id, **params)
    return jsonify(result)


# ------------------------------------------------------------------
# GET /tools — List available tools
# ------------------------------------------------------------------
@agent_v2_bp.route('/tools', methods=['GET'])
@token_required
def list_tools():
    """List available tools for the current user."""
    manager = get_manager()
    tools = manager.tool_registry.list_tools()
    return jsonify({'tools': tools})


# ------------------------------------------------------------------
# GET /agents — List all registered agents
# ------------------------------------------------------------------
@agent_v2_bp.route('/agents', methods=['GET'])
@token_required
def list_agents():
    """List all registered agents and their capabilities."""
    manager = get_manager()
    return jsonify({'agents': manager.list_agents()})


# ------------------------------------------------------------------
# GET /memory — User memories
# ------------------------------------------------------------------
@agent_v2_bp.route('/memory', methods=['GET'])
@token_required
def get_memories():
    """Get all memories for the current user."""
    from agents.memory import AgentMemoryService
    memory = AgentMemoryService()
    memory_type = request.args.get('type')
    memories = memory.get_all(request.current_user.id, memory_type)
    return jsonify({'memories': memories})


# ------------------------------------------------------------------
# DELETE /memory/<key> — Delete a memory
# ------------------------------------------------------------------
@agent_v2_bp.route('/memory/<key>', methods=['DELETE'])
@token_required
def delete_memory(key):
    """Delete a specific memory."""
    from agents.memory import AgentMemoryService
    memory = AgentMemoryService()
    deleted = memory.forget(request.current_user.id, key)
    if deleted:
        return jsonify({'message': '记忆已删除'})
    return jsonify({'error': '未找到该记忆'}), 404


# ------------------------------------------------------------------
# GET /templates — Prompt templates (admin only)
# ------------------------------------------------------------------
@agent_v2_bp.route('/templates', methods=['GET'])
@token_required
@require_permission('system:config')
def list_templates():
    """List all prompt templates (admin only)."""
    from models.prompt_template import PromptTemplate
    templates = PromptTemplate.query.order_by(PromptTemplate.name).all()
    return jsonify({'templates': [t.to_dict() for t in templates]})


# ------------------------------------------------------------------
# PUT /templates/<id> — Update a template (admin only)
# ------------------------------------------------------------------
@agent_v2_bp.route('/templates/<int:template_id>', methods=['PUT'])
@token_required
@require_permission('system:config')
def update_template(template_id):
    """Update a prompt template (admin only)."""
    from models.prompt_template import PromptTemplate
    from extensions import db

    tmpl = PromptTemplate.query.get(template_id)
    if not tmpl:
        return jsonify({'error': '模板不存在'}), 404

    data = request.get_json() or {}
    if 'template' in data:
        tmpl.template = data['template']
    if 'is_active' in data:
        tmpl.is_active = data['is_active']
    if 'variables' in data:
        tmpl.variables = data['variables']
    tmpl.version += 1

    db.session.commit()
    return jsonify({'template': tmpl.to_dict()})


# ------------------------------------------------------------------
# Monitoring endpoints
# ------------------------------------------------------------------

@agent_v2_bp.route('/monitor/dashboard', methods=['GET'])
@token_required
@require_permission('system:config')
def monitor_dashboard():
    """Agent monitoring dashboard — aggregated metrics."""
    from agents.monitoring import get_monitor
    period = request.args.get('period', '24h')
    monitor = get_monitor()
    return jsonify(monitor.get_dashboard_data(period))


@agent_v2_bp.route('/monitor/alerts', methods=['GET'])
@token_required
@require_permission('system:config')
def monitor_alerts():
    """Active alerts for agent health."""
    from agents.monitoring import get_monitor
    monitor = get_monitor()
    return jsonify({'alerts': monitor.get_alerts()})


@agent_v2_bp.route('/monitor/cost', methods=['GET'])
@token_required
@require_permission('system:config')
def monitor_cost():
    """Cost analysis for LLM usage."""
    from agents.monitoring import get_monitor
    period = request.args.get('period', '7d')
    monitor = get_monitor()
    return jsonify(monitor.get_cost_analysis(period))


@agent_v2_bp.route('/monitor/circuit-breakers', methods=['GET'])
@token_required
@require_permission('system:config')
def monitor_circuit_breakers():
    """Circuit breaker states for all agents."""
    from agents.circuit_breaker import get_all_breakers
    breakers = get_all_breakers()
    return jsonify({
        'circuit_breakers': [b.get_state() for b in breakers.values()]
    })


@agent_v2_bp.route('/monitor/traces', methods=['GET'])
@token_required
@require_permission('system:config')
def monitor_traces():
    """Recent LLM call traces (metadata only)."""
    from agents.llm_tracer import get_tracer
    limit = request.args.get('limit', 50, type=int)
    tracer = get_tracer()
    return jsonify({'traces': tracer.get_recent_traces(limit)})


# ------------------------------------------------------------------
# Prompt management endpoints (with registry + rollback)
# ------------------------------------------------------------------

@agent_v2_bp.route('/prompts/<name>/versions', methods=['GET'])
@token_required
@require_permission('system:config')
def prompt_versions(name):
    """List all versions of a prompt."""
    from agents.prompt_registry import get_prompt_registry
    registry = get_prompt_registry()
    return jsonify({'versions': registry.list_versions(name)})


@agent_v2_bp.route('/prompts/<name>/rollback', methods=['POST'])
@token_required
@require_permission('system:config')
def prompt_rollback(name):
    """Rollback a prompt to a specific version."""
    data = request.get_json() or {}
    version = data.get('version')
    if not version:
        return jsonify({'error': '请指定版本号'}), 400

    from agents.prompt_registry import get_prompt_registry
    registry = get_prompt_registry()
    success = registry.rollback(name, int(version))
    if success:
        return jsonify({'message': f'已回滚到 v{version}'})
    return jsonify({'error': '回滚失败，版本不存在'}), 404


@agent_v2_bp.route('/prompts/<name>/ab-stats', methods=['GET'])
@token_required
@require_permission('system:config')
def prompt_ab_stats(name):
    """A/B testing statistics for a prompt."""
    from agents.prompt_registry import get_prompt_registry
    registry = get_prompt_registry()
    return jsonify(registry.get_ab_stats(name))
