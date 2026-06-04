import json
import logging
import requests
from flask import Blueprint, request, jsonify, current_app, Response, stream_with_context
from utils.jwt_helper import token_required
from services.agent_service import (
    run_full_analysis, detect_subscriptions, detect_fixed_expenses,
    detect_anomalies, detect_high_frequency, compute_budget_allocation,
    _categorize_tags, build_agent_prompt, call_llm_analysis,
    generate_local_explanation
)

logger = logging.getLogger(__name__)

agent_bp = Blueprint('agent', __name__)


@agent_bp.route('/analyze', methods=['POST'])
@token_required
def analyze():
    """Run full agent analysis (Rule Engine + LLM)."""
    user = request.current_user
    data = request.get_json() or {}
    period = data.get('period', 3)

    try:
        result = run_full_analysis(user.id, period)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Agent analysis failed: {e}")
        return jsonify({'error': '分析失败，请稍后重试'}), 500


@agent_bp.route('/analyze/stream', methods=['POST'])
@token_required
def analyze_stream():
    """Stream LLM analysis via SSE."""
    user = request.current_user
    data = request.get_json() or {}
    period = data.get('period', 3)

    def generate():
        try:
            # First: run rule engine
            from services.agent_service import run_full_analysis
            result = run_full_analysis(user.id, period)

            # Send rule engine results first
            yield f'data: {json.dumps({"type": "data", "payload": {k: v for k, v in result.items() if k not in ("ai_content", "source")}})}\n\n'

            # Then stream LLM if available
            api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
            if not api_key:
                yield f'data: {json.dumps({"type": "content", "payload": result.get("ai_content", "")})}\n\n'
                yield f'data: {json.dumps({"type": "done"})}\n\n'
                return

            prompt = build_agent_prompt(user.id, result)
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
            payload = {
                'model': current_app.config.get('LLM_MODEL', 'deepseek-chat'),
                'messages': [
                    {'role': 'system', 'content': '你是AI财务Agent。用中文，Markdown格式。专业简洁有洞察。'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.7, 'max_tokens': 2000, 'stream': True
            }

            with requests.post(
                current_app.config['DEEPSEEK_API_URL'],
                headers=headers, json=payload, timeout=120, stream=True
            ) as resp:
                if resp.status_code != 200:
                    fallback = generate_local_explanation(result)
                    yield f'data: {json.dumps({"type": "content", "payload": fallback})}\n\n'
                else:
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

            yield f'data: {json.dumps({"type": "done"})}\n\n'

        except Exception as e:
            logger.error(f"Agent stream error: {e}")
            from utils.error_helpers import sse_error
            yield sse_error('分析失败')

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


@agent_bp.route('/subscriptions', methods=['GET'])
@token_required
def get_subscriptions():
    """Get detected subscriptions."""
    user = request.current_user
    months = request.args.get('months', 3, type=int)
    return jsonify({'subscriptions': detect_subscriptions(user.id, months)})


@agent_bp.route('/fixed-expenses', methods=['GET'])
@token_required
def get_fixed_expenses():
    """Get detected fixed expenses."""
    user = request.current_user
    months = request.args.get('months', 3, type=int)
    return jsonify({'fixed_expenses': detect_fixed_expenses(user.id, months)})


@agent_bp.route('/anomalies', methods=['GET'])
@token_required
def get_anomalies():
    """Get detected anomalies."""
    user = request.current_user
    months = request.args.get('months', 3, type=int)
    return jsonify({'anomalies': detect_anomalies(user.id, months)})


@agent_bp.route('/high-frequency', methods=['GET'])
@token_required
def get_high_frequency():
    """Get high-frequency spending patterns."""
    user = request.current_user
    days = request.args.get('days', 30, type=int)
    return jsonify({'high_frequency': detect_high_frequency(user.id, days)})


@agent_bp.route('/budget', methods=['GET'])
@token_required
def get_budget():
    """Get suggested budget allocation."""
    user = request.current_user
    months = request.args.get('months', 3, type=int)
    return jsonify({'budget': compute_budget_allocation(user.id, months)})


@agent_bp.route('/auto-tag', methods=['POST'])
@token_required
def auto_tag():
    """Auto-tag a transaction description."""
    data = request.get_json() or {}
    desc = data.get('description', '')
    note = data.get('note', '')
    category = data.get('category', '')
    amount = float(data.get('amount', 0))

    tags = _categorize_tags(desc, note, category, amount)
    return jsonify({'tags': tags})
