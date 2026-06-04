import json
import logging
import requests
from datetime import date, timedelta
from sqlalchemy import func, extract
from flask import Blueprint, request, jsonify, Response, current_app, stream_with_context
from extensions import db, limiter
from models.transaction import Transaction, Category
from utils.jwt_helper import token_required
from services import billing_service

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)


def _build_user_context(user_id):
    """Build financial context string from user's recent data."""
    today = date.today()
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    # This month stats
    month_income = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income',
        Transaction.date >= month_start, Transaction.date <= month_end
    ).scalar() or 0)

    month_expense = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense',
        Transaction.date >= month_start, Transaction.date <= month_end
    ).scalar() or 0)

    # Category breakdown
    cat_stats = db.session.query(
        Category.name,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense',
        Transaction.date >= month_start, Transaction.date <= month_end
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).limit(8).all()

    # Recent transactions
    recent = Transaction.query.filter_by(user_id=user_id).order_by(
        Transaction.date.desc(), Transaction.created_at.desc()
    ).limit(10).all()

    # Last 3 months trend
    trend_data = []
    for i in range(3):
        m = today.month - i
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        ms = date(y, m, 1)
        if m == 12:
            me = date(y + 1, 1, 1) - timedelta(days=1)
        else:
            me = date(y, m + 1, 1) - timedelta(days=1)
        exp = float(db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense',
            Transaction.date >= ms, Transaction.date <= me
        ).scalar() or 0)
        trend_data.append(f'{y}年{m}月支出¥{exp:,.0f}')

    # Build context
    lines = [f'【用户财务数据 - {today.isoformat()}】']
    lines.append(f'本月收入: ¥{month_income:,.2f}, 本月支出: ¥{month_expense:,.2f}, 结余: ¥{month_income - month_expense:,.2f}')

    if cat_stats:
        cats = ', '.join(f'{c.name}¥{float(c.total):,.0f}({float(c.total)/month_expense*100:.0f}%)' for c in cat_stats if month_expense > 0)
        lines.append(f'本月支出分类: {cats}')

    if trend_data:
        lines.append(f'近3月趋势: {" → ".join(reversed(trend_data))}')

    if recent:
        txns = []
        for t in recent[:5]:
            txns.append(f'{t.date} {"收入" if t.type == "income" else "支出"}¥{t.amount:,.0f}({t.category.name if t.category else "未分类"})')
        lines.append(f'最近交易: {"; ".join(txns)}')

    return '\n'.join(lines)


SYSTEM_PROMPT = """你是一位专业的AI财务助手，名叫"小财"。你的职责是帮助用户分析个人财务状况，提供消费建议和理财指导。

你的能力：
1. 分析用户的消费结构和趋势
2. 识别异常消费和潜在风险
3. 提供个性化的节省建议
4. 给出理财规划和投资建议
5. 回答各种财务相关问题

回答规则：
- 使用中文回答
- 使用 Markdown 格式化输出（标题、列表、加粗、表格等）
- 基于用户的实际财务数据进行分析，给出具体数字
- 语言亲切专业，像一位贴心的财务顾问
- 回答简洁有力，避免冗长
- 如果用户的问题超出财务范围，礼貌地引导回财务话题
- 适当使用 emoji 让回答更生动"""


@chat_bp.route('/send', methods=['POST'])
@token_required
@limiter.limit("30 per minute")
def send_message():
    """Send a message and get streaming AI response."""
    user = request.current_user

    # Check AI quota
    allowed, quota_details = billing_service.check_ai_quota(user.id)
    if not allowed:
        return jsonify({'error': quota_details.get('message', 'AI额度已用尽'), 'quota': quota_details}), 429

    data = request.get_json() or {}
    messages = data.get('messages', [])

    if not messages:
        return jsonify({'error': '消息不能为空'}), 400

    api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'AI 服务未配置'}), 503

    # Build user financial context
    user_context = _build_user_context(user.id)

    # Build full message list with system prompt + context
    full_messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'system', 'content': user_context}
    ]

    # Add conversation history (last 20 messages to stay within token limits)
    for msg in messages[-20:]:
        full_messages.append({
            'role': msg.get('role', 'user'),
            'content': msg.get('content', '')
        })

    def generate():
        try:
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            payload = {
                'model': current_app.config.get('LLM_MODEL', 'deepseek-chat'),
                'messages': full_messages,
                'temperature': 0.7,
                'max_tokens': 2000,
                'stream': True
            }

            api_url = current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')

            with requests.post(api_url, headers=headers, json=payload, timeout=120, stream=True) as resp:
                if resp.status_code != 200:
                    from utils.error_helpers import sse_error
                    yield sse_error(f'AI 服务返回错误: {resp.status_code}')
                    return

                for line in resp.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode('utf-8')
                    if not line_str.startswith('data: '):
                        continue
                    data_str = line_str[6:]
                    if data_str.strip() == '[DONE]':
                        yield 'data: [DONE]\n\n'
                        return

                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            yield f'data: {json.dumps({"content": content})}\n\n'
                    except json.JSONDecodeError:
                        continue

        except requests.Timeout:
            from utils.error_helpers import sse_error
            yield sse_error('AI 服务响应超时')
        except Exception as e:
            logger.error(f"Chat streaming error: {e}")
            from utils.error_helpers import sse_error
            yield sse_error('AI 服务异常，请稍后重试')

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@chat_bp.route('/quick-ask', methods=['POST'])
@token_required
@limiter.limit("30 per minute")
def quick_ask():
    """Non-streaming quick question for simple queries."""
    user = request.current_user

    # Check AI quota
    allowed, quota_details = billing_service.check_ai_quota(user.id)
    if not allowed:
        return jsonify({'error': quota_details.get('message', 'AI额度已用尽'), 'quota': quota_details}), 429

    data = request.get_json() or {}
    question = data.get('question', '')

    if not question:
        return jsonify({'error': '问题不能为空'}), 400

    api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        return jsonify({'reply': 'AI 服务未配置，请在 .env 中设置 DEEPSEEK_API_KEY。'}), 200

    user_context = _build_user_context(user.id)

    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': current_app.config.get('LLM_MODEL', 'deepseek-chat'),
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'system', 'content': user_context},
                {'role': 'user', 'content': question}
            ],
            'temperature': 0.7,
            'max_tokens': 1500
        }

        resp = requests.post(
            current_app.config['DEEPSEEK_API_URL'],
            headers=headers, json=payload, timeout=60
        )

        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            return jsonify({'reply': content})
        else:
            return jsonify({'error': f'AI 服务错误: {resp.status_code}'}), 502

    except Exception as e:
        logger.error(f"Quick ask error: {e}")
        return jsonify({'error': 'AI 服务异常'}), 500


@chat_bp.route('/suggestions', methods=['GET'])
@token_required
def get_suggestions():
    """Get quick question suggestions based on user data."""
    user = request.current_user
    today = date.today()
    month_start = today.replace(day=1)

    # Check if user has data this month
    has_data = db.session.query(func.count(Transaction.id)).filter(
        Transaction.user_id == user.id,
        Transaction.date >= month_start
    ).scalar() > 0

    if has_data:
        suggestions = [
            '分析一下我本月的消费结构',
            '我这个月有没有异常消费？',
            '给我一些省钱建议',
            '我的消费习惯健康吗？',
            '帮我制定下月预算',
            '分析我最近的消费趋势'
        ]
    else:
        suggestions = [
            '如何开始记账？',
            '给我一些理财入门建议',
            '如何制定月度预算？',
            '50/30/20法则是什么？',
            '如何建立应急基金？'
        ]

    return jsonify({'suggestions': suggestions})
