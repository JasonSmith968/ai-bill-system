"""
AI Auto-Accounting Agent Service
Rule Engine + LLM Hybrid Architecture

Layer 1: Rule Engine (fast, deterministic)
  - Pattern matching for merchants/descriptions
  - Frequency analysis for subscriptions
  - Amount threshold detection
  - Category-based tagging

Layer 2: LLM Analysis (deep, contextual)
  - Complex pattern recognition
  - Natural language explanations
  - Budget recommendations
  - Risk assessment
"""

import re
import logging
from datetime import date, timedelta
from collections import Counter, defaultdict
from sqlalchemy import func, extract
from flask import current_app
from extensions import db
from models.transaction import Transaction, Category

logger = logging.getLogger(__name__)

# ============================================================
# RULE ENGINE - Layer 1
# ============================================================

# Auto-tag rules: keyword -> tag
TAG_RULES = {
    '工作': {
        'keywords': ['打车', '滴滴', '出租车', '高铁', '火车', '飞机', '机票', '酒店', '出差',
                     '办公', '文具', '打印', '快递', '顺丰', '圆通', '中通', '韵达', '外卖工作餐',
                     '咖啡工作', '星巴克', '会议', '商务'],
        'categories': ['交通', '通讯'],
        'amount_range': (0, 5000)
    },
    '外卖': {
        'keywords': ['外卖', '美团', '饿了么', '肯德基', 'KFC', '麦当劳', '必胜客', '瑞幸',
                     '奶茶', '喜茶', '奈雪', '蜜雪冰城', '叮咚买菜', '盒马', '每日优鲜',
                     '食堂', '午餐', '晚餐', '早餐', '下午茶', '小吃', '烧烤', '火锅'],
        'categories': ['餐饮'],
        'amount_range': (0, 500)
    },
    '娱乐': {
        'keywords': ['电影', '游戏', 'KTV', '旅游', '门票', '演出', '健身', '游泳', '瑜伽',
                     '视频会员', '爱奇艺', '优酷', 'B站', '腾讯视频', '网飞', 'Netflix',
                     'Spotify', '音乐', '网易云', 'QQ音乐', '抖音', '密室', '剧本杀'],
        'categories': ['娱乐'],
        'amount_range': (0, 5000)
    },
    '学习': {
        'keywords': ['课程', '培训', '书籍', '学费', '考试', '报名', '教材', '网课',
                     '得到', '知乎', '极客时间', '慕课', 'Udemy', 'Coursera', '文具',
                     '考研', '雅思', '托福', 'PMP', '认证'],
        'categories': ['教育'],
        'amount_range': (0, 20000)
    },
    '投资': {
        'keywords': ['基金', '股票', '理财', '定期', '余额宝', '零钱通', '保险', '社保',
                     '公积金', '房贷', '房租', '还款', '贷款', '信用卡', '投资', '债券'],
        'categories': ['住房', '投资'],
        'amount_range': (0, 100000)
    }
}

# Subscription detection patterns
SUBSCRIPTION_PATTERNS = {
    '视频会员': {'keywords': ['爱奇艺', '优酷', '腾讯视频', 'B站', '网飞', 'Netflix', '芒果TV'], 'typical': [15, 25, 30, 35, 45]},
    '音乐会员': {'keywords': ['Spotify', '网易云', 'QQ音乐', 'Apple Music', '酷狗', '酷我'], 'typical': [8, 12, 15, 18, 25]},
    '云存储': {'keywords': ['iCloud', '百度网盘', '阿里云盘', 'OneDrive', 'Google One'], 'typical': [6, 12, 21, 68]},
    '工具订阅': {'keywords': ['ChatGPT', 'Copilot', 'Notion', 'Figma', 'Adobe', 'WPS', '印象笔记'], 'typical': [10, 20, 50, 100, 200]},
    '健身': {'keywords': ['健身房', 'Keep', '健身', '游泳'], 'typical': [50, 100, 200, 300, 500]},
    '通讯': {'keywords': ['话费', '流量', '宽带', '中国移动', '中国联通', '中国电信'], 'typical': [30, 50, 58, 88, 128, 198]},
}


def _text_match(text, keywords):
    """Check if text contains any keyword (case-insensitive)."""
    if not text:
        return []
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _categorize_tags(description, note, category_name, amount):
    """Rule-based auto-tagging. Returns list of tags with confidence."""
    text = f"{description or ''} {note or ''} {category_name or ''}"
    results = []
    for tag, rules in TAG_RULES.items():
        lo, hi = rules['amount_range']
        if not (lo <= amount <= hi):
            continue
        matched_kw = _text_match(text, rules['keywords'])
        cat_match = 1.0 if category_name in rules.get('categories', []) else 0.0
        if matched_kw:
            confidence = min(0.5 + len(matched_kw) * 0.15 + cat_match * 0.2, 1.0)
            results.append({'tag': tag, 'confidence': round(confidence, 2), 'reason': f'匹配关键词: {", ".join(matched_kw[:3])}'})
        elif cat_match > 0:
            results.append({'tag': tag, 'confidence': 0.3, 'reason': f'分类"{category_name}"匹配'})
    return sorted(results, key=lambda x: x['confidence'], reverse=True)


def detect_subscriptions(user_id, months=3):
    """Detect recurring subscription-like transactions."""
    today = date.today()
    start = today - timedelta(days=30 * months)

    transactions = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.date >= start
    ).order_by(Transaction.date).all()

    # Group by similar description + amount
    groups = defaultdict(list)
    for t in transactions:
        desc = (t.description or '').strip()
        if not desc:
            continue
        # Normalize key: description + amount bucket
        key = f"{desc}_{float(t.amount)}"
        groups[key].append(t)

    subscriptions = []
    for key, txns in groups.items():
        if len(txns) < 2:
            continue
        amounts = [float(t.amount) for t in txns]
        # Check if amounts are consistent (within 5%)
        avg_amt = sum(amounts) / len(amounts)
        if all(abs(a - avg_amt) / max(avg_amt, 1) < 0.05 for a in amounts):
            # Check for subscription patterns
            desc = txns[0].description or ''
            sub_type = None
            for sub_name, sub_info in SUBSCRIPTION_PATTERNS.items():
                if _text_match(desc, sub_info['keywords']):
                    sub_type = sub_name
                    break

            # Calculate interval
            dates = sorted([t.date for t in txns])
            if len(dates) >= 2:
                intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                avg_interval = sum(intervals) / len(intervals)
            else:
                avg_interval = 30

            # Determine frequency label
            if avg_interval <= 7:
                freq = '每周'
            elif avg_interval <= 14:
                freq = '每两周'
            elif avg_interval <= 35:
                freq = '每月'
            elif avg_interval <= 95:
                freq = '每季度'
            else:
                freq = '不规律'

            monthly_cost = avg_amt * (30 / max(avg_interval, 1))
            subscriptions.append({
                'name': desc,
                'amount': round(avg_amt, 2),
                'frequency': freq,
                'avg_interval_days': round(avg_interval),
                'occurrences': len(txns),
                'monthly_cost': round(monthly_cost, 2),
                'annual_cost': round(monthly_cost * 12, 2),
                'type': sub_type or '其他订阅',
                'last_date': dates[-1].isoformat(),
                'transactions': [{'id': t.id, 'date': t.date.isoformat(), 'amount': float(t.amount)} for t in txns[-5:]]
            })

    return sorted(subscriptions, key=lambda x: x['annual_cost'], reverse=True)


def detect_fixed_expenses(user_id, months=3):
    """Detect fixed/recurring expenses (rent, utilities, etc.)."""
    today = date.today()
    start = today - timedelta(days=30 * months)

    transactions = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.date >= start
    ).all()

    # Group by category + similar amount
    groups = defaultdict(list)
    for t in transactions:
        cat_name = t.category.name if t.category else '未分类'
        # Round amount to nearest 10 for grouping
        amt_bucket = round(float(t.amount) / 10) * 10
        key = f"{cat_name}_{amt_bucket}"
        groups[key].append(t)

    fixed = []
    for key, txns in groups.items():
        if len(txns) < 2:
            continue
        amounts = [float(t.amount) for t in txns]
        avg = sum(amounts) / len(amounts)
        # Fixed expenses: consistent amount, regular interval
        if all(abs(a - avg) / max(avg, 1) < 0.1 for a in amounts):
            dates = sorted([t.date for t in txns])
            intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                std_dev = (sum((x - avg_interval)**2 for x in intervals) / len(intervals)) ** 0.5
                # Low std_dev = regular pattern
                if std_dev < avg_interval * 0.3 and avg_interval <= 35:
                    cat_name = txns[0].category.name if txns[0].category else '未分类'
                    fixed.append({
                        'name': txns[0].description or cat_name,
                        'category': cat_name,
                        'amount': round(avg, 2),
                        'frequency': '每月' if 25 <= avg_interval <= 35 else f'每{round(avg_interval)}天',
                        'occurrences': len(txns),
                        'regularity': round(1 - std_dev / max(avg_interval, 1), 2),
                        'last_date': dates[-1].isoformat()
                    })

    return sorted(fixed, key=lambda x: x['amount'], reverse=True)


def detect_anomalies(user_id, months=3):
    """Detect anomalous spending based on historical patterns."""
    today = date.today()
    start = today - timedelta(days=30 * months)

    transactions = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.date >= start
    ).all()

    if not transactions:
        return []

    # Per-category statistics
    cat_stats = defaultdict(list)
    for t in transactions:
        cat_name = t.category.name if t.category else '未分类'
        cat_stats[cat_name].append(float(t.amount))

    anomalies = []
    # Recent 7 days transactions
    recent_start = today - timedelta(days=7)
    recent = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.date >= recent_start
    ).all()

    for t in recent:
        cat_name = t.category.name if t.category else '未分类'
        amounts = cat_stats.get(cat_name, [])
        if len(amounts) < 3:
            continue
        avg = sum(amounts) / len(amounts)
        std = (sum((x - avg)**2 for x in amounts) / len(amounts)) ** 0.5
        z_score = (float(t.amount) - avg) / max(std, 1)
        if z_score > 2.5:
            anomalies.append({
                'transaction_id': t.id,
                'date': t.date.isoformat(),
                'amount': float(t.amount),
                'category': cat_name,
                'description': t.description or '',
                'avg_amount': round(avg, 2),
                'z_score': round(z_score, 2),
                'severity': 'high' if z_score > 3.5 else 'medium',
                'reason': f'{cat_name}类平均消费 ¥{avg:,.0f}，本次 ¥{float(t.amount):,.0f}，偏离 {(z_score):.1f} 个标准差'
            })

    # Daily spending anomaly
    daily_totals = defaultdict(float)
    for t in transactions:
        daily_totals[t.date] += float(t.amount)

    if daily_totals:
        daily_vals = list(daily_totals.values())
        daily_avg = sum(daily_vals) / len(daily_vals)
        daily_std = (sum((x - daily_avg)**2 for x in daily_vals) / len(daily_vals)) ** 0.5

        for d, total in daily_totals.items():
            if d >= recent_start:
                z = (total - daily_avg) / max(daily_std, 1)
                if z > 2.5:
                    anomalies.append({
                        'transaction_id': None,
                        'date': d.isoformat(),
                        'amount': total,
                        'category': '日消费总计',
                        'description': f'{d} 日总消费',
                        'avg_amount': round(daily_avg, 2),
                        'z_score': round(z, 2),
                        'severity': 'high' if z > 3.5 else 'medium',
                        'reason': f'日均消费 ¥{daily_avg:,.0f}，当日 ¥{total:,.0f}，异常偏高'
                    })

    return sorted(anomalies, key=lambda x: x['z_score'], reverse=True)


def detect_high_frequency(user_id, days=30):
    """Detect high-frequency spending patterns."""
    today = date.today()
    start = today - timedelta(days=days)

    transactions = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.date >= start
    ).all()

    # Per-category frequency
    cat_counter = Counter()
    cat_amounts = defaultdict(float)
    for t in transactions:
        cat_name = t.category.name if t.category else '未分类'
        cat_counter[cat_name] += 1
        cat_amounts[cat_name] += float(t.amount)

    high_freq = []
    for cat, count in cat_counter.most_common():
        daily_rate = count / days
        if daily_rate >= 0.5:  # More than once every 2 days
            high_freq.append({
                'category': cat,
                'count': count,
                'daily_rate': round(daily_rate, 2),
                'total_amount': round(cat_amounts[cat], 2),
                'avg_amount': round(cat_amounts[cat] / count, 2),
                'level': '极高' if daily_rate >= 2 else '高',
                'suggestion': f'{cat}类 {days}天内消费 {count} 次，日均 {daily_rate:.1f} 次，建议控制频次'
            })

    return sorted(high_freq, key=lambda x: x['daily_rate'], reverse=True)


def compute_budget_allocation(user_id, months=3):
    """Compute suggested budget allocation based on historical spending."""
    today = date.today()
    start = today - timedelta(days=30 * months)

    cat_stats = db.session.query(
        Category.name, Category.color,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense',
        Transaction.date >= start
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

    total = sum(float(s.total) for s in cat_stats)
    if total == 0:
        return []

    budgets = []
    for s in cat_stats:
        amount = float(s.total)
        monthly_avg = amount / months
        pct = amount / total * 100
        # Suggested budget: 90% of average (encourage reduction)
        suggested = round(monthly_avg * 0.9, -1)  # Round to nearest 10
        budgets.append({
            'category': s.name,
            'color': s.color,
            'monthly_avg': round(monthly_avg, 2),
            'percentage': round(pct, 1),
            'suggested_budget': suggested,
            'savings_potential': round(monthly_avg - suggested, 2)
        })

    return budgets


# ============================================================
# LLM LAYER - Layer 2
# ============================================================

def build_agent_prompt(user_id, analysis_data):
    """Build a comprehensive prompt for LLM analysis."""
    s = analysis_data
    lines = ['请作为AI财务Agent，基于以下数据分析用户的消费模式并给出建议。\n']

    lines.append('## 基础数据')
    lines.append(f'- 分析周期: 近{s.get("period_months", 3)}个月')
    lines.append(f'- 总支出: ¥{s.get("total_expense", 0):,.0f}')
    lines.append(f'- 月均支出: ¥{s.get("monthly_avg_expense", 0):,.0f}')
    lines.append(f'- 总交易笔数: {s.get("total_count", 0)}')

    if s.get('subscriptions'):
        lines.append('\n## 检测到的订阅服务')
        for sub in s['subscriptions'][:5]:
            lines.append(f'- {sub["name"]}: ¥{sub["amount"]}/{sub["frequency"]}，年费 ¥{sub["annual_cost"]:,.0f}')

    if s.get('fixed_expenses'):
        lines.append('\n## 固定支出')
        for f in s['fixed_expenses'][:5]:
            lines.append(f'- {f["name"]}({f["category"]}): ¥{f["amount"]}/{f["frequency"]}')

    if s.get('anomalies'):
        lines.append('\n## 异常消费')
        for a in s['anomalies'][:5]:
            lines.append(f'- {a["date"]} {a["category"]}: ¥{a["amount"]:,.0f} (z-score: {a["z_score"]})')

    if s.get('high_frequency'):
        lines.append('\n## 高频消费')
        for h in s['high_frequency'][:5]:
            lines.append(f'- {h["category"]}: {h["count"]}次/{s.get("period_months", 3)}月，日均{h["daily_rate"]}次')

    if s.get('budget_allocation'):
        lines.append('\n## 预算分配建议')
        for b in s['budget_allocation'][:6]:
            lines.append(f'- {b["category"]}: 月均¥{b["monthly_avg"]:,.0f}({b["percentage"]}%) → 建议预算¥{b["suggested_budget"]:,.0f}')

    lines.append('\n请用Markdown格式输出以下内容：')
    lines.append('## 🤖 Agent 分析总结')
    lines.append('## 📋 自动标签分析')
    lines.append('## ⚠️ 风险提醒')
    lines.append('## 💰 预算优化建议')
    lines.append('## 🎯 行动计划')

    return '\n'.join(lines)


def call_llm_analysis(prompt):
    """Call DeepSeek LLM for deep analysis. Uses LLMClient abstraction."""
    try:
        from services.llm_client import get_llm_client
        llm = get_llm_client()
        messages = [
            {'role': 'system', 'content': '你是AI财务Agent，擅长分析消费模式、识别风险、制定预算。用中文回答，Markdown格式。专业、简洁、有洞察力。'},
            {'role': 'user', 'content': prompt}
        ]
        result = llm.chat(messages)
        return result.get('content') if result else None
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
    return None


def generate_local_explanation(analysis_data):
    """Local rule-based explanation (fallback)."""
    s = analysis_data
    lines = []

    lines.append('## 🤖 Agent 分析总结\n')
    total = s.get('total_expense', 0)
    monthly = s.get('monthly_avg_expense', 0)
    lines.append(f'近{s.get("period_months", 3)}个月共支出 **¥{total:,.0f}**，月均 **¥{monthly:,.0f}**。')

    if s.get('subscriptions'):
        annual_sub = sum(sub['annual_cost'] for sub in s['subscriptions'])
        lines.append(f'检测到 **{len(s["subscriptions"])}** 个订阅服务，年费合计 **¥{annual_sub:,.0f}**。')

    if s.get('anomalies'):
        high_count = sum(1 for a in s['anomalies'] if a['severity'] == 'high')
        if high_count:
            lines.append(f'发现 **{high_count}** 笔高风险异常消费，需要关注。')

    lines.append('\n## 📋 自动标签分析\n')
    if s.get('tag_analysis'):
        for tag_info in s['tag_analysis'][:5]:
            lines.append(f'- **{tag_info["tag"]}**: {tag_info["count"]}笔，¥{tag_info["total"]:,.0f}（置信度 {tag_info["avg_confidence"]:.0%}）')
    else:
        lines.append('- 暂无足够数据进行标签分析')

    lines.append('\n## ⚠️ 风险提醒\n')
    risks = []
    if s.get('anomalies'):
        for a in s['anomalies'][:3]:
            risks.append(f'- 🔴 {a["reason"]}')
    if s.get('high_frequency'):
        for h in s['high_frequency'][:2]:
            risks.append(f'- 🟡 {h["suggestion"]}')
    if s.get('subscriptions'):
        annual = sum(x['annual_cost'] for x in s['subscriptions'])
        if annual > monthly * 3:
            risks.append(f'- 🟡 订阅年费 ¥{annual:,.0f}，占月均支出的 {annual/monthly/12:.0%}')
    if not risks:
        risks.append('- ✅ 未检测到明显风险')
    lines.extend(risks)

    lines.append('\n## 💰 预算优化建议\n')
    if s.get('budget_allocation'):
        for b in s['budget_allocation'][:4]:
            if b['savings_potential'] > 0:
                lines.append(f'- **{b["category"]}**: 月均 ¥{b["monthly_avg"]:,.0f} → 建议 ¥{b["suggested_budget"]:,.0f}（可省 ¥{b["savings_potential"]:,.0f}）')

    lines.append('\n## 🎯 行动计划\n')
    lines.append('1. 审查并取消不常用的订阅服务')
    lines.append('2. 为高频消费类别设定每日/每周上限')
    lines.append('3. 对异常大额消费设置提醒阈值')
    lines.append('4. 每周复盘消费数据，持续优化')

    return '\n'.join(lines)


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def run_full_analysis(user_id, period_months=3):
    """Run complete agent analysis: Rule Engine + LLM."""
    today = date.today()
    start = today - timedelta(days=30 * period_months)

    # Rule Engine Layer
    total_expense = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense',
        Transaction.date >= start
    ).scalar() or 0)

    total_count = Transaction.query.filter(
        Transaction.user_id == user_id, Transaction.type == 'expense',
        Transaction.date >= start
    ).count()

    subscriptions = detect_subscriptions(user_id, period_months)
    fixed_expenses = detect_fixed_expenses(user_id, period_months)
    anomalies = detect_anomalies(user_id, period_months)
    high_frequency = detect_high_frequency(user_id, 30)
    budget_allocation = compute_budget_allocation(user_id, period_months)

    # Auto-tagging
    recent_txns = Transaction.query.filter(
        Transaction.user_id == user_id, Transaction.type == 'expense',
        Transaction.date >= start
    ).all()

    tag_counter = defaultdict(lambda: {'count': 0, 'total': 0, 'confidence_sum': 0})
    for t in recent_txns:
        cat_name = t.category.name if t.category else '未分类'
        tags = _categorize_tags(t.description, t.note, cat_name, float(t.amount))
        if tags:
            best = tags[0]
            tag_counter[best['tag']]['count'] += 1
            tag_counter[best['tag']]['total'] += float(t.amount)
            tag_counter[best['tag']]['confidence_sum'] += best['confidence']

    tag_analysis = []
    for tag, info in sorted(tag_counter.items(), key=lambda x: x[1]['total'], reverse=True):
        tag_analysis.append({
            'tag': tag,
            'count': info['count'],
            'total': round(info['total'], 2),
            'avg_confidence': round(info['confidence_sum'] / max(info['count'], 1), 2)
        })

    analysis_data = {
        'period_months': period_months,
        'total_expense': round(total_expense, 2),
        'monthly_avg_expense': round(total_expense / max(period_months, 1), 2),
        'total_count': total_count,
        'subscriptions': subscriptions,
        'fixed_expenses': fixed_expenses,
        'anomalies': anomalies,
        'high_frequency': high_frequency,
        'budget_allocation': budget_allocation,
        'tag_analysis': tag_analysis
    }

    # LLM Layer (optional, enhances with explanations)
    prompt = build_agent_prompt(user_id, analysis_data)
    llm_content = call_llm_analysis(prompt)

    if llm_content:
        analysis_data['ai_content'] = llm_content
        analysis_data['source'] = 'llm'
    else:
        analysis_data['ai_content'] = generate_local_explanation(analysis_data)
        analysis_data['source'] = 'local'

    return analysis_data
