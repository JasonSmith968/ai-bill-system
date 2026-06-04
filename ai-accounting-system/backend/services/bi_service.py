"""BI Data Aggregation Service — centralized analytics for the BI dashboard.

All methods take user_id and return structured dicts ready for API consumption.
Reuses existing detection functions from agent_service where applicable.
"""

import logging
from datetime import date, timedelta
from collections import defaultdict
from sqlalchemy import func, extract
from extensions import db
from models.transaction import Transaction, Category

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Monthly Trend
# ------------------------------------------------------------------
def get_monthly_trend(user_id, months=12):
    """Monthly income/expense trend with 3-period moving average."""
    today = date.today()
    start = date(today.year, today.today().month, 1) - timedelta(days=30 * (months - 1))
    start = date(start.year, start.month, 1)

    rows = db.session.query(
        extract('year', Transaction.date).label('y'),
        extract('month', Transaction.date).label('m'),
        Transaction.type,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start
    ).group_by('y', 'm', Transaction.type).order_by('y', 'm').all()

    month_data = defaultdict(lambda: {'income': 0, 'expense': 0})
    for r in rows:
        key = f"{int(r.y)}-{int(r.m):02d}"
        month_data[key]['income' if r.type == 'income' else 'expense'] = float(r.total)

    labels = sorted(month_data.keys())
    income = [month_data[l]['income'] for l in labels]
    expense = [month_data[l]['expense'] for l in labels]

    def moving_avg(arr, window=3):
        result = []
        for i in range(len(arr)):
            start_idx = max(0, i - window + 1)
            result.append(round(sum(arr[start_idx:i + 1]) / (i - start_idx + 1), 2))
        return result

    return {
        'labels': labels,
        'income': income,
        'expense': expense,
        'moving_avg_income': moving_avg(income),
        'moving_avg_expense': moving_avg(expense),
    }


# ------------------------------------------------------------------
# Cash Flow
# ------------------------------------------------------------------
def get_cash_flow(user_id, months=6):
    """Cash flow analysis: income, expense, net, cumulative."""
    today = date.today()
    start = date(today.year, today.month, 1) - timedelta(days=30 * (months - 1))
    start = date(start.year, start.month, 1)

    rows = db.session.query(
        extract('year', Transaction.date).label('y'),
        extract('month', Transaction.date).label('m'),
        Transaction.type,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start
    ).group_by('y', 'm', Transaction.type).order_by('y', 'm').all()

    month_data = defaultdict(lambda: {'income': 0, 'expense': 0})
    for r in rows:
        key = f"{int(r.y)}-{int(r.m):02d}"
        month_data[key]['income' if r.type == 'income' else 'expense'] = float(r.total)

    labels = sorted(month_data.keys())
    income = [month_data[l]['income'] for l in labels]
    expense = [month_data[l]['expense'] for l in labels]
    net = [round(i - e, 2) for i, e in zip(income, expense)]

    cumulative = []
    running = 0
    for n in net:
        running += n
        cumulative.append(round(running, 2))

    return {
        'labels': labels,
        'income': income,
        'expense': expense,
        'net': net,
        'cumulative': cumulative,
    }


# ------------------------------------------------------------------
# Forecast
# ------------------------------------------------------------------
def forecast_next_month(user_id):
    """Predict next month's expense using simple linear regression on last 6 months."""
    trend = get_monthly_trend(user_id, months=6)
    if len(trend['expense']) < 3:
        return {
            'predicted_expense': 0,
            'predicted_income': 0,
            'confidence': 0,
            'trend': 'stable',
            'monthly_data': trend,
        }

    def _linreg(y_vals):
        n = len(y_vals)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(y_vals) / n
        ss_xy = sum((x[i] - x_mean) * (y_vals[i] - y_mean) for i in range(n))
        ss_xx = sum((x[i] - x_mean) ** 2 for i in range(n))
        if ss_xx == 0:
            return y_mean, 0, 0
        slope = ss_xy / ss_xx
        intercept = y_mean - slope * x_mean
        # R-squared
        ss_res = sum((y_vals[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))
        ss_tot = sum((y_vals[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0
        return slope * n + intercept, slope, max(0, min(1, r_squared))

    pred_exp, slope_exp, r2_exp = _linreg(trend['expense'])
    pred_inc, slope_inc, r2_inc = _linreg(trend['income'])

    avg_exp = sum(trend['expense']) / len(trend['expense'])
    trend_dir = 'rising' if slope_exp > avg_exp * 0.05 else ('falling' if slope_exp < -avg_exp * 0.05 else 'stable')

    return {
        'predicted_expense': round(max(0, pred_exp), 2),
        'predicted_income': round(max(0, pred_inc), 2),
        'confidence': round((r2_exp + r2_inc) / 2, 3),
        'trend': trend_dir,
        'monthly_data': trend,
    }


# ------------------------------------------------------------------
# Category Composition
# ------------------------------------------------------------------
def get_category_composition(user_id, months=3):
    """Category breakdown with MoM percentage change."""
    today = date.today()
    curr_start = date(today.year, today.month, 1)
    prev_start = (curr_start - timedelta(days=1)).replace(day=1)
    lookback_start = prev_start - timedelta(days=30 * (months - 2))
    lookback_start = date(lookback_start.year, lookback_start.month, 1)

    rows = db.session.query(
        Category.name,
        Category.color,
        Category.icon,
        extract('year', Transaction.date).label('y'),
        extract('month', Transaction.date).label('m'),
        func.sum(Transaction.amount).label('total')
    ).join(Category, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.date >= lookback_start
    ).group_by(Category.name, Category.color, Category.icon, 'y', 'm').all()

    cat_current = defaultdict(float)
    cat_prev = defaultdict(float)
    cat_meta = {}
    for r in rows:
        key = r.name
        cat_meta[key] = {'color': r.color, 'icon': r.icon}
        period = f"{int(r.y)}-{int(r.m):02d}"
        curr_key = f"{today.year}-{today.month:02d}"
        prev_key = f"{prev_start.year}-{prev_start.month:02d}"
        if period == curr_key:
            cat_current[key] += float(r.total)
        elif period == prev_key:
            cat_prev[key] += float(r.total)

    total_curr = sum(cat_current.values()) or 1
    categories = []
    for name, amount in sorted(cat_current.items(), key=lambda x: -x[1]):
        prev_amount = cat_prev.get(name, 0)
        mom_change = round(amount - prev_amount, 2)
        mom_pct = round(mom_change / max(prev_amount, 1) * 100, 1)
        categories.append({
            'name': name,
            'color': cat_meta.get(name, {}).get('color', '#6B7280'),
            'icon': cat_meta.get(name, {}).get('icon', 'tag'),
            'amount': round(amount, 2),
            'percentage': round(amount / total_curr * 100, 1),
            'mom_change': mom_change,
            'mom_change_pct': mom_pct,
        })

    return {
        'categories': categories,
        'total': round(total_curr, 2),
    }


# ------------------------------------------------------------------
# Anomaly Detection
# ------------------------------------------------------------------
def detect_spending_anomalies(user_id, months=3):
    """Enhanced anomaly detection with calendar heatmap data."""
    from services.agent_service import detect_anomalies
    anomalies = detect_anomalies(user_id, months)

    today = date.today()
    start = today - timedelta(days=30 * months)
    daily_totals = defaultdict(float)
    rows = db.session.query(
        Transaction.date,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.date >= start
    ).group_by(Transaction.date).all()

    for r in rows:
        daily_totals[r.date] = float(r.total)

    all_amounts = list(daily_totals.values())
    mean = sum(all_amounts) / len(all_amounts) if all_amounts else 0
    std = (sum((x - mean) ** 2 for x in all_amounts) / len(all_amounts)) ** 0.5 if all_amounts else 1
    threshold = mean + 2 * std

    heatmap = []
    for d, amount in sorted(daily_totals.items()):
        z = (amount - mean) / max(std, 1)
        level = 'high' if z > 2.5 else ('warning' if z > 1.5 else 'normal')
        heatmap.append({'date': d.isoformat(), 'amount': round(amount, 2), 'level': level})

    return {
        'anomalies': anomalies,
        'daily_heatmap': heatmap,
        'stats': {'mean': round(mean, 2), 'std': round(std, 2), 'threshold': round(threshold, 2)},
    }


# ------------------------------------------------------------------
# Budget Risk
# ------------------------------------------------------------------
def get_budget_risk(user_id):
    """Budget utilization vs suggested allocation."""
    from services.agent_service import compute_budget_allocation
    budgets = compute_budget_allocation(user_id)

    today = date.today()
    curr_start = date(today.year, today.month, 1)
    actuals = db.session.query(
        Category.name,
        func.sum(Transaction.amount).label('total')
    ).join(Category, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user_id,
        Transaction.type == 'expense',
        Transaction.date >= curr_start
    ).group_by(Category.name).all()

    actual_map = {r.name: float(r.total) for r in actuals}
    total_budget = 0
    total_actual = 0
    categories = []

    for b in budgets:
        name = b.get('category', b.get('name', ''))
        budget_amt = b.get('suggested_budget', b.get('amount', 0))
        actual_amt = actual_map.get(name, 0)
        utilization = round(actual_amt / max(budget_amt, 1) * 100, 1)
        risk = 'over' if utilization > 100 else ('warning' if utilization > 80 else 'safe')
        total_budget += budget_amt
        total_actual += actual_amt
        categories.append({
            'name': name,
            'budget': round(budget_amt, 2),
            'actual': round(actual_amt, 2),
            'utilization': utilization,
            'risk_level': risk,
        })

    return {
        'categories': sorted(categories, key=lambda x: -x['utilization']),
        'total_budget': round(total_budget, 2),
        'total_actual': round(total_actual, 2),
        'overall_utilization': round(total_actual / max(total_budget, 1) * 100, 1),
    }


# ------------------------------------------------------------------
# Subscription Waste
# ------------------------------------------------------------------
def detect_subscription_waste(user_id):
    """Detect potentially wasted or expensive subscriptions."""
    from services.agent_service import detect_subscriptions
    subs = detect_subscriptions(user_id, months=3)

    today = date.today()
    total_monthly = sum(s.get('monthly_cost', 0) for s in subs)
    total_annual = sum(s.get('annual_cost', 0) for s in subs)

    enhanced = []
    waste_flags = []
    for s in subs:
        last = s.get('last_date', '')
        days_since = (today - date.fromisoformat(last)).days if last else 999
        is_unused = days_since > 45 and s.get('avg_interval_days', 30) <= 35
        is_expensive = s.get('monthly_cost', 0) > total_monthly * 0.3 and total_monthly > 0

        status = 'active'
        reason = ''
        if is_unused:
            status = 'possibly_unused'
            reason = f'超过 {days_since} 天未使用'
            waste_flags.append(f"{s['name']}: {reason}")
        elif is_expensive:
            status = 'expensive'
            reason = f"占月订阅费 {s['monthly_cost'] / max(total_monthly, 1) * 100:.0f}%"
            waste_flags.append(f"{s['name']}: {reason}")

        enhanced.append({**s, 'status': status, 'waste_reason': reason})

    waste_score = min(100, len(waste_flags) * 20 + (10 if total_annual > 5000 else 0))

    return {
        'subscriptions': enhanced,
        'total_annual': round(total_annual, 2),
        'total_monthly': round(total_monthly, 2),
        'waste_score': waste_score,
        'recommendations': waste_flags,
    }


# ------------------------------------------------------------------
# Financial Health
# ------------------------------------------------------------------
def get_financial_health(user_id):
    """Composite financial health score (0-100)."""
    today = date.today()
    curr_start = date(today.year, today.month, 1)
    six_months_ago = curr_start - timedelta(days=180)

    # Income & expense for last 6 months
    rows = db.session.query(
        extract('year', Transaction.date).label('y'),
        extract('month', Transaction.date).label('m'),
        Transaction.type,
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= six_months_ago
    ).group_by('y', 'm', Transaction.type).all()

    monthly = defaultdict(lambda: {'income': 0, 'expense': 0})
    for r in rows:
        key = f"{int(r.y)}-{int(r.m):02d}"
        monthly[key]['income' if r.type == 'income' else 'expense'] = float(r.total)

    incomes = [v['income'] for v in monthly.values()]
    expenses = [v['expense'] for v in monthly.values()]

    # Savings rate (40% weight)
    total_income = sum(incomes) or 1
    total_expense = sum(expenses)
    savings_rate = (total_income - total_expense) / total_income
    savings_score = min(100, max(0, savings_rate * 200))  # 50% savings = 100 score

    # Expense stability (20% weight) — low variance = high score
    if len(expenses) >= 2:
        avg_exp = sum(expenses) / len(expenses)
        variance = sum((e - avg_exp) ** 2 for e in expenses) / len(expenses)
        cv = (variance ** 0.5) / max(avg_exp, 1)  # coefficient of variation
        stability_score = max(0, 100 - cv * 100)
    else:
        stability_score = 50

    # Category diversification (20% weight)
    comp = get_category_composition(user_id, months=3)
    num_cats = len(comp['categories'])
    max_pct = max((c['percentage'] for c in comp['categories']), default=100)
    div_score = min(100, num_cats * 12) * (1 - max(0, max_pct - 40) / 60)

    # Income consistency (20% weight)
    if len(incomes) >= 2:
        avg_inc = sum(incomes) / len(incomes)
        inc_var = sum((i - avg_inc) ** 2 for i in incomes) / len(incomes)
        inc_cv = (inc_var ** 0.5) / max(avg_inc, 1)
        income_score = max(0, 100 - inc_cv * 80)
    else:
        income_score = 50

    total_score = round(
        savings_score * 0.4 + stability_score * 0.2 + div_score * 0.2 + income_score * 0.2
    )
    total_score = max(0, min(100, total_score))

    if total_score >= 80:
        level = 'excellent'
    elif total_score >= 60:
        level = 'good'
    elif total_score >= 40:
        level = 'moderate'
    elif total_score >= 20:
        level = 'warning'
    else:
        level = 'danger'

    recommendations = []
    if savings_rate < 0.1:
        recommendations.append('储蓄率过低，建议控制支出，目标储蓄率 20% 以上')
    if max_pct > 50:
        recommendations.append(f'支出过于集中在单一分类（{max_pct:.0f}%），建议分散消费')
    if stability_score < 40:
        recommendations.append('月度支出波动较大，建议制定预算控制')

    return {
        'score': total_score,
        'level': level,
        'components': {
            'savings_rate': {'value': round(savings_rate * 100, 1), 'score': round(savings_score), 'weight': 40},
            'expense_stability': {'value': round(stability_score, 1), 'score': round(stability_score), 'weight': 20},
            'diversification': {'value': round(div_score, 1), 'score': round(div_score), 'weight': 20},
            'income_consistency': {'value': round(income_score, 1), 'score': round(income_score), 'weight': 20},
        },
        'recommendations': recommendations,
    }


# ------------------------------------------------------------------
# Full BI Summary
# ------------------------------------------------------------------
def generate_bi_summary(user_id):
    """Generate the complete BI data package."""
    result = {}
    for name, fn in [
        ('trend', lambda: get_monthly_trend(user_id)),
        ('cash_flow', lambda: get_cash_flow(user_id)),
        ('forecast', lambda: forecast_next_month(user_id)),
        ('category_composition', lambda: get_category_composition(user_id)),
        ('anomalies', lambda: detect_spending_anomalies(user_id)),
        ('budget_risk', lambda: get_budget_risk(user_id)),
        ('subscriptions', lambda: detect_subscription_waste(user_id)),
        ('health', lambda: get_financial_health(user_id)),
    ]:
        try:
            result[name] = fn()
        except Exception as e:
            logger.error(f"BI summary section '{name}' failed: {e}")
            result[name] = {'error': str(e)}
    return result
