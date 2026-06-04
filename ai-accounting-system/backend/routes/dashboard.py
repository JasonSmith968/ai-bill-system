import logging
from datetime import date, timedelta
from sqlalchemy import func, extract
from flask import Blueprint, request, jsonify
from extensions import db
from models.transaction import Transaction, Category
from utils.jwt_helper import token_required

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/summary', methods=['GET'])
@token_required
def get_summary():
    """Get financial summary (month, total, today)."""
    user = request.current_user
    today = date.today()

    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    month_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= month_start, Transaction.date <= month_end
    ).scalar() or 0

    month_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= month_start, Transaction.date <= month_end
    ).scalar() or 0

    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'income'
    ).scalar() or 0

    total_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense'
    ).scalar() or 0

    month_count = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.date >= month_start, Transaction.date <= month_end
    ).count()

    today_count = Transaction.query.filter(
        Transaction.user_id == user.id, Transaction.date == today
    ).count()

    today_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date == today
    ).scalar() or 0

    # Week: Monday to Sunday
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= week_start, Transaction.date <= week_end
    ).scalar() or 0

    return jsonify({
        'month': {
            'income': float(month_income),
            'expense': float(month_expense),
            'balance': float(month_income - month_expense),
            'count': month_count
        },
        'total': {
            'income': float(total_income),
            'expense': float(total_expense),
            'balance': float(total_income - total_expense)
        },
        'today': {
            'count': today_count,
            'expense': float(today_expense)
        },
        'week': {
            'expense': float(week_expense)
        }
    })


@dashboard_bp.route('/weekly', methods=['GET'])
@token_required
def get_weekly():
    """Get daily expense breakdown for the current week (Mon-Sun)."""
    user = request.current_user
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday

    days = []
    day_labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

    for i in range(7):
        d = week_start + timedelta(days=i)
        total = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id,
            Transaction.type == 'expense',
            Transaction.date == d
        ).scalar() or 0
        days.append({
            'date': d.isoformat(),
            'label': day_labels[i],
            'amount': float(total),
            'is_today': d == today
        })

    return jsonify({'days': days})


@dashboard_bp.route('/trend', methods=['GET'])
@token_required
def get_trend():
    """Get income/expense trend by month."""
    user = request.current_user
    months = request.args.get('months', 6, type=int)

    today = date.today()
    start_date = today - timedelta(days=30 * months)

    income_data = db.session.query(
        extract('year', Transaction.date).label('year'),
        extract('month', Transaction.date).label('month'),
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= start_date
    ).group_by('year', 'month').order_by('year', 'month').all()

    expense_data = db.session.query(
        extract('year', Transaction.date).label('year'),
        extract('month', Transaction.date).label('month'),
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= start_date
    ).group_by('year', 'month').order_by('year', 'month').all()

    result = {'labels': [], 'income': [], 'expense': []}

    current = start_date.replace(day=1)
    while current <= today:
        label = current.strftime('%Y-%m')
        result['labels'].append(label)

        income_amount = next(
            (float(d.total) for d in income_data
             if int(d.year) == current.year and int(d.month) == current.month), 0
        )
        expense_amount = next(
            (float(d.total) for d in expense_data
             if int(d.year) == current.year and int(d.month) == current.month), 0
        )

        result['income'].append(income_amount)
        result['expense'].append(expense_amount)

        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return jsonify(result)


@dashboard_bp.route('/category-stats', methods=['GET'])
@token_required
def get_category_stats():
    """Get category breakdown statistics."""
    user = request.current_user
    transaction_type = request.args.get('type', 'expense')
    month = request.args.get('month')

    query = db.session.query(
        Category.name, Category.icon, Category.color,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(
        Transaction, Transaction.category_id == Category.id
    ).filter(
        Transaction.user_id == user.id,
        Transaction.type == transaction_type
    )

    if month:
        year, mon = month.split('-')
        query = query.filter(
            extract('year', Transaction.date) == int(year),
            extract('month', Transaction.date) == int(mon)
        )

    stats = query.group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()
    total = sum(float(s.total) for s in stats)

    result = []
    for s in stats:
        amount = float(s.total)
        result.append({
            'name': s.name,
            'icon': s.icon,
            'color': s.color,
            'amount': amount,
            'count': s.count,
            'percentage': round(amount / total * 100, 1) if total > 0 else 0
        })

    return jsonify({
        'type': transaction_type,
        'total': total,
        'categories': result
    })


@dashboard_bp.route('/recent', methods=['GET'])
@token_required
def get_recent_transactions():
    """Get recent transactions."""
    user = request.current_user
    limit = min(request.args.get('limit', 10, type=int), 50)

    transactions = Transaction.query.filter_by(
        user_id=user.id
    ).order_by(
        Transaction.date.desc(), Transaction.created_at.desc()
    ).limit(limit).all()

    return jsonify({
        'transactions': [t.to_dict() for t in transactions]
    })


@dashboard_bp.route('/statistics', methods=['GET'])
@token_required
def get_statistics():
    """All-in-one statistics for the enterprise dashboard."""
    user = request.current_user
    today = date.today()

    # Month range
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    # Week range (Mon-Sun)
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # Yesterday
    yesterday = today - timedelta(days=1)

    # --- Aggregates ---
    def _sum_expense(start, end):
        return float(db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id, Transaction.type == 'expense',
            Transaction.date >= start, Transaction.date <= end
        ).scalar() or 0)

    def _sum_income(start, end):
        return float(db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user.id, Transaction.type == 'income',
            Transaction.date >= start, Transaction.date <= end
        ).scalar() or 0)

    today_expense = _sum_expense(today, today)
    yesterday_expense = _sum_expense(yesterday, yesterday)
    week_expense = _sum_expense(week_start, week_end)
    month_expense = _sum_expense(month_start, month_end)
    month_income = _sum_income(month_start, month_end)

    month_count = Transaction.query.filter(
        Transaction.user_id == user.id,
        Transaction.date >= month_start, Transaction.date <= month_end
    ).count()

    # --- Top category this month ---
    top_cat = db.session.query(
        Category.name, Category.color,
        func.sum(Transaction.amount).label('total')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= month_start, Transaction.date <= month_end
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).first()

    top_category = {
        'name': top_cat.name if top_cat else '暂无',
        'amount': float(top_cat.total) if top_cat else 0,
        'color': top_cat.color if top_cat else '#6B7280'
    } if top_cat else {'name': '暂无', 'amount': 0, 'color': '#6B7280'}

    # --- Category breakdown this month ---
    cat_stats = db.session.query(
        Category.name, Category.color,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= month_start, Transaction.date <= month_end
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

    categories = []
    for s in cat_stats:
        amount = float(s.total)
        categories.append({
            'name': s.name, 'color': s.color,
            'amount': amount, 'count': s.count,
            'percentage': round(amount / month_expense * 100, 1) if month_expense > 0 else 0
        })

    # --- Weekly daily breakdown ---
    weekly_days = []
    day_labels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    for i in range(7):
        d = week_start + timedelta(days=i)
        amt = _sum_expense(d, d)
        weekly_days.append({
            'label': day_labels[i], 'date': d.isoformat(),
            'amount': amt, 'is_today': d == today
        })

    # --- Monthly trend (6 months) ---
    months_count = 6
    trend_start = today - timedelta(days=30 * months_count)
    income_data = db.session.query(
        extract('year', Transaction.date).label('y'),
        extract('month', Transaction.date).label('m'),
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= trend_start
    ).group_by('y', 'm').order_by('y', 'm').all()

    expense_data = db.session.query(
        extract('year', Transaction.date).label('y'),
        extract('month', Transaction.date).label('m'),
        func.sum(Transaction.amount).label('total')
    ).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= trend_start
    ).group_by('y', 'm').order_by('y', 'm').all()

    trend_labels, trend_income, trend_expense = [], [], []
    cur = trend_start.replace(day=1)
    while cur <= today:
        label = cur.strftime('%Y-%m')
        trend_labels.append(label)
        trend_income.append(next(
            (float(d.total) for d in income_data
             if int(d.y) == cur.year and int(d.m) == cur.month), 0))
        trend_expense.append(next(
            (float(d.total) for d in expense_data
             if int(d.y) == cur.year and int(d.m) == cur.month), 0))
        cur = (cur.replace(month=cur.month + 1) if cur.month < 12
               else cur.replace(year=cur.year + 1, month=1))

    # --- Recent transactions ---
    recent = Transaction.query.filter_by(user_id=user.id).order_by(
        Transaction.date.desc(), Transaction.created_at.desc()
    ).limit(8).all()

    return jsonify({
        'today_expense': today_expense,
        'yesterday_expense': yesterday_expense,
        'week_expense': week_expense,
        'month_expense': month_expense,
        'month_income': month_income,
        'month_balance': month_income - month_expense,
        'month_count': month_count,
        'top_category': top_category,
        'categories': categories,
        'weekly': weekly_days,
        'trend': {
            'labels': trend_labels,
            'income': trend_income,
            'expense': trend_expense
        },
        'recent': [t.to_dict() for t in recent]
    })
