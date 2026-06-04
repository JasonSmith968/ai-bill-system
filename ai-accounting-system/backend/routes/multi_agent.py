"""Multi-agent API endpoints."""

import json
import logging
from flask import Blueprint, request, jsonify, Response, stream_with_context
from utils.jwt_helper import token_required
from agents.base import AgentContext
from agents import get_manager

logger = logging.getLogger(__name__)

multi_agent_bp = Blueprint('multi_agent', __name__)


@multi_agent_bp.route('/agents', methods=['GET'])
@token_required
def list_agents():
    """List all registered agents and their capabilities."""
    return jsonify({'agents': get_manager().list_agents()})


@multi_agent_bp.route('/chain', methods=['POST'])
@token_required
def run_chain():
    """Run a custom chain of agents specified in the request body."""
    data = request.get_json() or {}
    agent_names = data.get('agents', [])
    params = data.get('params', {})

    if not agent_names:
        return jsonify({'error': 'No agents specified'}), 400

    context = AgentContext(user_id=request.current_user.id)
    manager = get_manager()
    result = manager.run_chain(agent_names, context, **params)

    return jsonify({
        'result': result.to_dict(),
        'call_chain': context.call_chain,
        'context_data': {k: context.get(k) for k in context.keys()
                         if not k.startswith('_')}
    })


@multi_agent_bp.route('/analyze', methods=['POST'])
@token_required
def multi_agent_analyze():
    """Full analysis via multi-agent pipeline: Risk -> Recommendation."""
    data = request.get_json() or {}
    period = data.get('period', 3)

    context = AgentContext(user_id=request.current_user.id)
    manager = get_manager()
    result = manager.run_full_analysis(context, period)

    return jsonify(result)


@multi_agent_bp.route('/analyze/stream', methods=['POST'])
@token_required
def multi_agent_analyze_stream():
    """Streaming analysis via multi-agent pipeline with SSE."""
    data = request.get_json() or {}
    period = data.get('period', 3)

    def generate():
        try:
            context = AgentContext(user_id=request.current_user.id)
            manager = get_manager()
            events = []

            def yield_event(event):
                events.append(event)

            context.set('_yield_event', yield_event, 'system')

            # Run risk agent
            yield f'data: {json.dumps({"type": "agent_start", "agent": "risk"})}\n\n'

            risk_result = manager.run('risk', context, task='full_scan', months=period)

            yield f'data: {json.dumps({"type": "agent_done", "agent": "risk", "duration_ms": risk_result.duration_ms})}\n\n'

            # Send rule engine data
            rule_data = {k: context.get(k) for k in context.keys()
                         if not k.startswith('_') and k != 'recommendations'
                         and k != 'recommendation_source'}
            yield f'data: {json.dumps({"type": "data", "payload": rule_data})}\n\n'

            # Run recommendation agent
            yield f'data: {json.dumps({"type": "agent_start", "agent": "recommendation"})}\n\n'

            manager.run('recommendation', context, task='budget', months=period)

            # Try streaming LLM for recommendations
            from flask import current_app
            api_key = current_app.config.get('DEEPSEEK_API_KEY', '')

            if api_key:
                # Build prompt and stream LLM
                from services.agent_service import build_agent_prompt, generate_local_explanation
                analysis_data = {k: context.get(k) for k in context.keys()
                                 if not k.startswith('_')}
                analysis_data['period_months'] = period
                if not analysis_data.get('total_expense'):
                    analysis_data['total_expense'] = 0
                if not analysis_data.get('monthly_avg_expense'):
                    analysis_data['monthly_avg_expense'] = 0
                if not analysis_data.get('total_count'):
                    analysis_data['total_count'] = 0

                prompt = build_agent_prompt(context.user_id, analysis_data)

                import requests as req
                headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
                payload = {
                    'model': current_app.config.get('LLM_MODEL', 'deepseek-chat'),
                    'messages': [
                        {'role': 'system', 'content': '你是AI财务Agent，擅长分析消费模式、识别风险、制定预算。用中文回答，Markdown格式。专业、简洁、有洞察力。'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.7, 'max_tokens': 2000, 'stream': True
                }

                try:
                    with req.post(current_app.config['DEEPSEEK_API_URL'],
                                  headers=headers, json=payload, timeout=120, stream=True) as resp:
                        if resp.status_code == 200:
                            for line in resp.iter_lines():
                                if not line:
                                    continue
                                line_str = line.decode('utf-8')
                                if not line_str.startswith('data: '):
                                    continue
                                d = line_str[6:].strip()
                                if d == '[DONE]':
                                    break
                                try:
                                    chunk = json.loads(d)
                                    content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                    if content:
                                        yield f'data: {json.dumps({"type": "content", "payload": content})}\n\n'
                                except json.JSONDecodeError:
                                    continue
                        else:
                            # Fallback to local
                            local = generate_local_explanation(analysis_data)
                            yield f'data: {json.dumps({"type": "content", "payload": local})}\n\n'
                except Exception as e:
                    logger.error(f"LLM streaming failed: {e}")
                    local = generate_local_explanation(analysis_data)
                    yield f'data: {json.dumps({"type": "content", "payload": local})}\n\n'
            else:
                # No API key, use local explanation
                from services.agent_service import generate_local_explanation
                analysis_data = {k: context.get(k) for k in context.keys()
                                 if not k.startswith('_')}
                analysis_data['period_months'] = period
                local = generate_local_explanation(analysis_data)
                yield f'data: {json.dumps({"type": "content", "payload": local})}\n\n'

            yield f'data: {json.dumps({"type": "agent_done", "agent": "recommendation", "duration_ms": 0})}\n\n'
            yield f'data: {json.dumps({"type": "done", "call_chain": context.call_chain})}\n\n'

        except Exception as e:
            logger.error(f"Multi-agent stream error: {e}")
            from utils.error_helpers import sse_error
            yield sse_error('分析失败')

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


@multi_agent_bp.route('/logs', methods=['GET'])
@token_required
def get_agent_logs():
    """Get recent agent execution logs."""
    limit = request.args.get('limit', 50, type=int)
    logs = get_manager()._logger.get_recent(limit)
    return jsonify({'logs': logs})


@multi_agent_bp.route('/logs/<request_id>', methods=['GET'])
@token_required
def get_request_logs(request_id):
    """Get agent logs for a specific request (call chain)."""
    logs = get_manager()._logger.get_by_request(request_id)
    return jsonify({'request_id': request_id, 'logs': logs})
