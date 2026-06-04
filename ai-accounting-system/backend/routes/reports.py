import io
import json
import logging
import requests
from datetime import date, timedelta
from calendar import monthrange
from sqlalchemy import func, extract
from flask import Blueprint, request, jsonify, send_file, current_app, Response, stream_with_context
from extensions import db
from models.transaction import Transaction, Category
from utils.jwt_helper import token_required

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__)


def _month_range(year, month):
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _prev_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _detect_anomalies(daily_trend, categories, month_expense, avg_daily):
    """Detect spending anomalies with severity levels."""
    anomalies = []

    # 1. Daily spending spikes (>3x average)
    if avg_daily > 0:
        for d in daily_trend:
            if d['amount'] > avg_daily * 3 and d['amount'] > 0:
                anomalies.append({
                    'type': 'spike', 'severity': 'high',
                    'title': f'{d["day"]}日消费异常偏高',
                    'detail': f'当日支出 ¥{d["amount"]:,.0f}，是日均 ¥{avg_daily:,.0f} 的 {d["amount"]/avg_daily:.1f} 倍',
                    'icon': 'alert-triangle'
                })

    # 2. Category concentration risk
    if categories and month_expense > 0:
        top = categories[0]
        if top['percentage'] > 50:
            anomalies.append({
                'type': 'concentration', 'severity': 'high',
                'title': f'{top["name"]}支出占比过高',
                'detail': f'占总支出 {top["percentage"]}%，消费结构单一，风险集中',
                'icon': 'alert-circle'
            })
        elif top['percentage'] > 40:
            anomalies.append({
                'type': 'concentration', 'severity': 'medium',
                'title': f'{top["name"]}支出偏高',
                'detail': f'占总支出 {top["percentage"]}%，建议适当分散消费',
                'icon': 'info'
            })

    # 3. No-income month
    # 4. Negative balance handled in frontend from summary data

    return anomalies


def _compute_risk_score(summary, categories, comparison):
    """Compute a 0-100 financial health risk score. Lower = healthier."""
    score = 50  # baseline

    # Savings rate impact
    sr = summary.get('savings_rate', 0)
    if sr >= 30:
        score -= 20
    elif sr >= 10:
        score -= 5
    elif sr < 0:
        score += 25

    # Category concentration
    if categories:
        top_pct = categories[0].get('percentage', 0)
        if top_pct > 50:
            score += 15
        elif top_pct > 40:
            score += 8

    # Month-over-month trend
    exp_pct = comparison.get('expense_change_pct', 0)
    if exp_pct > 30:
        score += 15
    elif exp_pct > 15:
        score += 8
    elif exp_pct < -10:
        score -= 5

    return max(0, min(100, score))


def _risk_level(score):
    if score <= 25:
        return 'excellent', '财务状况优秀'
    elif score <= 45:
        return 'good', '财务状况良好'
    elif score <= 65:
        return 'moderate', '需要关注'
    elif score <= 80:
        return 'warning', '存在风险'
    else:
        return 'danger', '财务风险较高'


@reports_bp.route('/monthly', methods=['GET'])
@token_required
def get_monthly_report():
    """Get comprehensive monthly report data with anomaly detection."""
    user = request.current_user
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', date.today().month, type=int)

    start, end = _month_range(year, month)
    prev_year, prev_month = _prev_month(year, month)
    prev_start, prev_end = _month_range(prev_year, prev_month)

    # --- Current month aggregates ---
    month_income = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= start, Transaction.date <= end
    ).scalar() or 0)

    month_expense = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= start, Transaction.date <= end
    ).scalar() or 0)

    month_count = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.date >= start, Transaction.date <= end
    ).count()

    income_count = Transaction.query.filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= start, Transaction.date <= end
    ).count()

    # --- Previous month ---
    prev_income = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= prev_start, Transaction.date <= prev_end
    ).scalar() or 0)

    prev_expense = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= prev_start, Transaction.date <= prev_end
    ).scalar() or 0)

    # --- Category breakdown ---
    cat_stats = db.session.query(
        Category.name, Category.icon, Category.color,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= start, Transaction.date <= end
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

    categories = []
    for s in cat_stats:
        amount = float(s.total)
        categories.append({
            'name': s.name, 'icon': s.icon, 'color': s.color,
            'amount': amount, 'count': s.count,
            'percentage': round(amount / month_expense * 100, 1) if month_expense > 0 else 0
        })

    # --- Income categories ---
    income_cat_stats = db.session.query(
        Category.name, Category.icon, Category.color,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= start, Transaction.date <= end
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

    income_categories = []
    for s in income_cat_stats:
        amount = float(s.total)
        income_categories.append({
            'name': s.name, 'icon': s.icon, 'color': s.color,
            'amount': amount, 'count': s.count,
            'percentage': round(amount / month_income * 100, 1) if month_income > 0 else 0
        })

    # --- Daily trends ---
    days_in_month = monthrange(year, month)[1]

    daily_expenses = db.session.query(
        Transaction.date, func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= start, Transaction.date <= end
    ).group_by(Transaction.date).order_by(Transaction.date).all()

    daily_incomes = db.session.query(
        Transaction.date, func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= start, Transaction.date <= end
    ).group_by(Transaction.date).order_by(Transaction.date).all()

    daily_trend = []
    daily_income_trend = []
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        exp_amt = next((float(de.total) for de in daily_expenses if de.date == d), 0)
        inc_amt = next((float(di.total) for di in daily_incomes if di.date == d), 0)
        daily_trend.append({'date': d.isoformat(), 'day': day, 'amount': exp_amt})
        daily_income_trend.append({'date': d.isoformat(), 'day': day, 'amount': inc_amt})

    # --- Weekly breakdown ---
    weekly = []
    for week_idx in range(4):
        week_start_day = week_idx * 7 + 1
        week_end_day = min(week_start_day + 6, days_in_month)
        week_exp = sum(d['amount'] for d in daily_trend[week_start_day - 1:week_end_day])
        week_inc = sum(d['amount'] for d in daily_income_trend[week_start_day - 1:week_end_day])
        weekly.append({
            'label': f'第{week_idx + 1}周',
            'range': f'{week_start_day}日-{week_end_day}日',
            'expense': week_exp, 'income': week_inc
        })
    # Handle remaining days
    if days_in_month > 28:
        remaining_exp = sum(d['amount'] for d in daily_trend[28:])
        remaining_inc = sum(d['amount'] for d in daily_income_trend[28:])
        if weekly:
            weekly[-1]['expense'] += remaining_exp
            weekly[-1]['income'] += remaining_inc
            weekly[-1]['range'] = f'29日-{days_in_month}日'

    # --- Computed metrics ---
    days_elapsed = (min(date.today(), end) - start).days + 1
    avg_daily = month_expense / days_elapsed if days_elapsed > 0 else 0
    top_day = max(daily_trend, key=lambda x: x['amount']) if daily_trend else None
    avg_transaction = month_expense / month_count if month_count > 0 else 0

    # --- Anomaly detection ---
    anomalies = _detect_anomalies(daily_trend, categories, month_expense, avg_daily)

    # --- Risk scoring ---
    summary = {
        'income': month_income, 'expense': month_expense,
        'balance': month_income - month_expense, 'count': month_count,
        'income_count': income_count,
        'avg_daily': round(avg_daily, 2),
        'avg_transaction': round(avg_transaction, 2),
        'savings_rate': round((month_income - month_expense) / month_income * 100, 1) if month_income > 0 else 0
    }
    comparison = {
        'prev_month': f'{prev_year}-{prev_month:02d}',
        'income_change': round(month_income - prev_income, 2),
        'income_change_pct': round((month_income - prev_income) / prev_income * 100, 1) if prev_income > 0 else 0,
        'expense_change': round(month_expense - prev_expense, 2),
        'expense_change_pct': round((month_expense - prev_expense) / prev_expense * 100, 1) if prev_expense > 0 else 0,
        'prev_income': prev_income, 'prev_expense': prev_expense
    }

    risk_score = _compute_risk_score(summary, categories, comparison)
    risk_level, risk_label = _risk_level(risk_score)

    # --- Recent transactions ---
    recent = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.date >= start, Transaction.date <= end
    ).order_by(Transaction.date.desc(), Transaction.created_at.desc()).limit(50).all()

    return jsonify({
        'year': year, 'month': month,
        'summary': summary,
        'comparison': comparison,
        'categories': categories,
        'income_categories': income_categories,
        'daily_trend': daily_trend,
        'daily_income_trend': daily_income_trend,
        'weekly': weekly,
        'top_spending_day': top_day,
        'anomalies': anomalies,
        'risk': {'score': risk_score, 'level': risk_level, 'label': risk_label},
        'transactions': [t.to_dict() for t in recent]
    })


@reports_bp.route('/ai-analysis', methods=['POST'])
@token_required
def get_ai_analysis():
    """Generate streaming AI analysis for the monthly report."""
    user = request.current_user
    data = request.get_json() or {}
    year = data.get('year', date.today().year)
    month = data.get('month', date.today().month)

    start, end = _month_range(year, month)
    prev_year, prev_month = _prev_month(year, month)
    prev_start, prev_end = _month_range(prev_year, prev_month)

    month_income = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= start, Transaction.date <= end
    ).scalar() or 0)

    month_expense = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= start, Transaction.date <= end
    ).scalar() or 0)

    prev_expense = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= prev_start, Transaction.date <= prev_end
    ).scalar() or 0)

    cat_stats = db.session.query(
        Category.name, func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= start, Transaction.date <= end
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

    # Daily data for anomaly detection
    daily_expenses = db.session.query(
        Transaction.date, func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= start, Transaction.date <= end
    ).group_by(Transaction.date).all()

    days_in_month = monthrange(year, month)[1]
    days_elapsed = (min(date.today(), end) - start).days + 1
    avg_daily = month_expense / days_elapsed if days_elapsed > 0 else 0
    daily_amounts = [float(d.total) for d in daily_expenses]
    max_daily = max(daily_amounts) if daily_amounts else 0

    cats_text = ', '.join(f'{c.name} ¥{float(c.total):,.0f}({float(c.total)/month_expense*100:.0f}%)' for c in cat_stats) if month_expense > 0 else '无'
    balance = month_income - month_expense
    savings_rate = (balance / month_income * 100) if month_income > 0 else 0

    prompt = f"""作为资深个人财务顾问，请为用户生成 {year}年{month}月 的深度月度财务分析报告。

## 核心数据
- 本月收入：¥{month_income:,.2f}
- 本月支出：¥{month_expense:,.2f}
- 本月结余：¥{balance:,.2f}
- 储蓄率：{savings_rate:.1f}%
- 交易笔数：{len(daily_amounts)}天有消费记录
- 日均支出：¥{avg_daily:,.0f}
- 单日最高：¥{max_daily:,.0f}
- 上月支出：¥{prev_expense:,.0f}
- 环比变化：{((month_expense - prev_expense) / prev_expense * 100) if prev_expense > 0 else 0:+.1f}%
- 分类明细：{cats_text}

请用Markdown格式输出以下内容，每个部分2-4句话，数据驱动、具体可操作：

## 📊 月度财务总结
总结整体财务状况，指出关键指标表现。

## 🔍 消费结构分析
分析各分类占比是否合理，指出主要消费方向。

## ⚠️ 风险预警
识别潜在风险：分类集中度、消费趋势、超支风险等。

## 💡 节省建议
3-5条针对用户实际消费模式的具体节省建议。

## 🎯 下月规划
给出具体的预算分配建议和理财目标。"""

    api_key = current_app.config.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        analysis = _local_analysis(month_income, month_expense, prev_expense, cat_stats, year, month, avg_daily, max_daily)
        return jsonify({'analysis': analysis, 'source': 'local'})

    def generate():
        try:
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
            payload = {
                'model': current_app.config.get('LLM_MODEL', 'deepseek-chat'),
                'messages': [
                    {'role': 'system', 'content': '你是资深个人财务分析师。用中文回答，Markdown格式。语言专业、温暖、有洞察力。用数据说话。'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.7, 'max_tokens': 2500, 'stream': True
            }
            with requests.post(
                current_app.config['DEEPSEEK_API_URL'],
                headers=headers, json=payload, timeout=120, stream=True
            ) as resp:
                if resp.status_code != 200:
                    from utils.error_helpers import sse_error
                    yield sse_error('AI 分析不可用，使用本地分析')
                    fallback = _local_analysis(month_income, month_expense, prev_expense, cat_stats, year, month, avg_daily, max_daily)
                    yield f'data: {json.dumps({"content": fallback})}\n\n'
                    yield 'data: [DONE]\n\n'
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
                        content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if content:
                            yield f'data: {json.dumps({"content": content})}\n\n'
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"AI analysis stream error: {e}")
            from utils.error_helpers import sse_error
            yield sse_error('AI 分析异常，使用本地分析')
            fallback = _local_analysis(month_income, month_expense, prev_expense, cat_stats, year, month, avg_daily, max_daily)
            yield f'data: {json.dumps({"content": fallback})}\n\n'
            yield 'data: [DONE]\n\n'

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


def _local_analysis(income, expense, prev_expense, cat_stats, year, month, avg_daily, max_daily):
    """Rule-based fallback analysis."""
    balance = income - expense
    sr = (balance / income * 100) if income > 0 else 0
    exp_chg = expense - prev_expense

    lines = ['## 📊 月度财务总结\n']
    if income > 0:
        if sr >= 30:
            lines.append(f'{year}年{month}月财务表现**优秀**。收入 ¥{income:,.0f}，支出 ¥{expense:,.0f}，结余 ¥{balance:,.0f}，储蓄率 **{sr:.1f}%**，远超健康标准(20%)。')
        elif sr >= 10:
            lines.append(f'{year}年{month}月收支基本平衡。收入 ¥{income:,.0f}，支出 ¥{expense:,.0f}，结余 ¥{balance:,.0f}，储蓄率 {sr:.1f}%，建议向20%目标努力。')
        elif sr >= 0:
            lines.append(f'{year}年{month}月结余偏低。收入 ¥{income:,.0f}，支出 ¥{expense:,.0f}，仅结余 ¥{balance:,.0f}，储蓄率仅 {sr:.1f}%，需要控制支出。')
        else:
            lines.append(f'{year}年{month}月**入不敷出**。收入 ¥{income:,.0f}，支出 ¥{expense:,.0f}，超支 ¥{abs(balance):,.0f}，财务状况需要立即调整。')

    if prev_expense > 0:
        pct = exp_chg / prev_expense * 100
        arrow = '↑' if exp_chg > 0 else '↓'
        lines.append(f'环比上月支出{arrow} **{abs(pct):.1f}%**。日均消费 ¥{avg_daily:,.0f}，单日峰值 ¥{max_daily:,.0f}。')

    lines.append('\n## 🔍 消费结构分析\n')
    if cat_stats:
        top3 = cat_stats[:3]
        for c in top3:
            pct = float(c.total) / expense * 100 if expense > 0 else 0
            bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
            lines.append(f'- **{c.name}**：¥{float(c.total):,.0f}（{pct:.0f}%）{bar}')
        if float(top3[0].total) / expense * 100 > 45:
            lines.append(f'\n> 消费过度集中于{top3[0].name}，建议分散消费以降低风险。')

    lines.append('\n## ⚠️ 风险预警\n')
    risks = []
    if balance < 0:
        risks.append(f'- 🔴 **超支风险**：本月超支 ¥{abs(balance):,.0f}，需立即控制消费')
    if cat_stats and expense > 0:
        top_pct = float(cat_stats[0].total) / expense * 100
        if top_pct > 50:
            risks.append(f'- 🔴 **集中风险**：{cat_stats[0].name}占比 {top_pct:.0f}%，消费结构单一')
    if exp_chg > 0 and prev_expense > 0 and exp_chg / prev_expense > 0.25:
        risks.append(f'- 🟡 **增长风险**：环比支出增长 {exp_chg/prev_expense*100:.0f}%，需关注趋势')
    if max_daily > avg_daily * 3 and avg_daily > 0:
        risks.append(f'- 🟡 **波动风险**：单日峰值 ¥{max_daily:,.0f} 是日均的 {max_daily/avg_daily:.1f} 倍')
    if not risks:
        risks.append('- ✅ 本月财务状况健康，未检测到明显风险')
    lines.extend(risks)

    lines.append('\n## 💡 节省建议\n')
    if cat_stats and expense > 0:
        top_name = cat_stats[0].name
        tips = {
            '餐饮': ['自己做饭替代外卖，每月可省30-50%餐饮开支', '使用超市优惠券和满减活动', '带便当上班，健康又省钱'],
            '交通': ['优先公共交通，长途拼车', '短途步行或骑行', '错峰出行享受优惠票价'],
            '购物': ['列购物清单，避免冲动消费', '大件商品等大促再买', '多平台比价后下单'],
            '娱乐': ['选择免费户外活动替代付费娱乐', '利用团购和会员折扣', '设定月度娱乐预算上限'],
        }
        suggestions = tips.get(top_name, [f'关注{top_name}类支出，设定月度预算', '记录每笔消费明细', '区分"想要"和"需要"'])
        for i, tip in enumerate(suggestions, 1):
            lines.append(f'{i}. {tip}')
    lines.append(f'{len(cat_stats) + 1}. 使用50/30/20法则：50%必要、30%个人、20%储蓄')

    lines.append('\n## 🎯 下月规划\n')
    if balance > 0:
        lines.append(f'- **储蓄目标**：结余 ¥{balance:,.0f}，建议50%定存，30%基金，20%灵活备用')
        lines.append(f'- **消费预算**：建议下月支出 ≤ ¥{expense * 0.9:,.0f}（降低10%）')
    else:
        lines.append(f'- **紧缩预算**：下月支出目标 ≤ ¥{income * 0.75:,.0f}（收入的75%）')
        lines.append('- **紧急措施**：暂停所有非必要消费，优先填补超支')
    lines.append('- **应急基金**：目标建立3-6个月生活费的应急储备')
    lines.append('- **记账习惯**：保持每日记账，每周复盘一次')

    return '\n'.join(lines)


@reports_bp.route('/export/excel', methods=['GET'])
@token_required
def export_excel():
    """Export monthly report as styled Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    user = request.current_user
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', date.today().month, type=int)
    start, end = _month_range(year, month)

    month_income = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= start, Transaction.date <= end
    ).scalar() or 0)

    month_expense = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= start, Transaction.date <= end
    ).scalar() or 0)

    transactions = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.date >= start, Transaction.date <= end
    ).order_by(Transaction.date.desc()).all()

    cat_stats = db.session.query(
        Category.name, Category.color,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= start, Transaction.date <= end
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

    wb = Workbook()

    hdr_font = Font(name='Microsoft YaHei', size=11, bold=True, color='FFFFFF')
    hdr_fill = PatternFill(start_color='1E293B', end_color='1E293B', fill_type='solid')
    accent_fill = PatternFill(start_color='6366F1', end_color='6366F1', fill_type='solid')
    border = Border(
        left=Side(style='thin', color='E2E8F0'), right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'), bottom=Side(style='thin', color='E2E8F0')
    )
    money_fmt = '#,##0.00'

    # Sheet 1: Overview
    ws = wb.active
    ws.title = '月报概览'
    ws.sheet_properties.tabColor = '6366F1'

    ws.merge_cells('A1:F1')
    ws['A1'] = f'{user.username} · {year}年{month}月 财务报告'
    ws['A1'].font = Font(name='Microsoft YaHei', size=16, bold=True, color='1E293B')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 45

    ws.merge_cells('A2:F2')
    ws['A2'] = f'生成于 {date.today().isoformat()} · AI 智能记账系统'
    ws['A2'].font = Font(name='Microsoft YaHei', size=10, color='64748B')
    ws['A2'].alignment = Alignment(horizontal='center')

    # Summary row
    row = 4
    for col, label in enumerate(['总收入', '总支出', '结余', '储蓄率', '交易笔数', '日均支出'], 1):
        c = ws.cell(row=row, column=col, value=label)
        c.font = hdr_font; c.fill = accent_fill; c.alignment = Alignment(horizontal='center'); c.border = border

    row = 5
    sr = f'{(month_income - month_expense) / month_income * 100:.1f}%' if month_income > 0 else '0%'
    days_e = (min(date.today(), end) - start).days + 1
    vals = [month_income, month_expense, month_income - month_expense, sr, len(transactions), round(month_expense / max(days_e, 1), 2)]
    for col, val in enumerate(vals, 1):
        c = ws.cell(row=row, column=col, value=val)
        c.alignment = Alignment(horizontal='center'); c.border = border
        if isinstance(val, (int, float)):
            c.number_format = money_fmt

    # Category table
    row = 7
    ws.cell(row=row, column=1, value='支出分类明细').font = Font(name='Microsoft YaHei', size=13, bold=True, color='1E293B')
    row += 1
    for col, h in enumerate(['排名', '分类', '金额', '笔数', '占比'], 1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = hdr_font; c.fill = hdr_fill; c.alignment = Alignment(horizontal='center'); c.border = border

    for i, cat in enumerate(cat_stats, 1):
        row += 1
        pct = float(cat.total) / month_expense * 100 if month_expense > 0 else 0
        ws.cell(row=row, column=1, value=i).border = border
        ws.cell(row=row, column=2, value=cat.name).border = border
        c = ws.cell(row=row, column=3, value=float(cat.total))
        c.number_format = money_fmt; c.border = border
        ws.cell(row=row, column=4, value=cat.count).border = border
        c2 = ws.cell(row=row, column=5, value=f'{pct:.1f}%')
        c2.alignment = Alignment(horizontal='center'); c2.border = border

    for col, w in enumerate([8, 15, 15, 10, 10], 1):
        ws.column_dimensions[get_column_letter(col)].width = w

    # Sheet 2: Transactions
    ws2 = wb.create_sheet('交易明细')
    ws2.sheet_properties.tabColor = '10B981'
    for col, h in enumerate(['日期', '类型', '分类', '金额', '描述', '备注'], 1):
        c = ws2.cell(row=1, column=col, value=h)
        c.font = hdr_font; c.fill = hdr_fill; c.alignment = Alignment(horizontal='center'); c.border = border

    for i, t in enumerate(transactions, 2):
        ws2.cell(row=i, column=1, value=t.date.isoformat()).border = border
        tc = ws2.cell(row=i, column=2, value='收入' if t.type == 'income' else '支出')
        tc.border = border; tc.alignment = Alignment(horizontal='center')
        tc.font = Font(name='Microsoft YaHei', color='10B981' if t.type == 'income' else 'EF4444')
        ws2.cell(row=i, column=3, value=t.category.name if t.category else '未分类').border = border
        ac = ws2.cell(row=i, column=4, value=float(t.amount))
        ac.number_format = money_fmt; ac.border = border
        ws2.cell(row=i, column=5, value=t.description or '').border = border
        ws2.cell(row=i, column=6, value=t.note or '').border = border

    for col, w in enumerate([12, 8, 12, 12, 25, 25], 1):
        ws2.column_dimensions[get_column_letter(col)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
        download_name=f'report_{year}_{month:02d}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
