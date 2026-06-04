import logging
from datetime import datetime, date, timedelta
from sqlalchemy import func
from flask import Blueprint, request, jsonify
from extensions import db
from models.user import User
from models.transaction import Transaction, Category
from utils.jwt_helper import token_required
from security.rbac import require_permission

logger = logging.getLogger(__name__)
biz_logger = logging.getLogger('business')

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/users', methods=['GET'])
@token_required
@require_permission('user:list')
def get_users():
    """List users with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    keyword = request.args.get('keyword')

    query = User.query
    if keyword:
        query = query.filter(
            (User.username.contains(keyword)) | (User.email.contains(keyword))
        )

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'users': [u.to_dict() for u in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages
    })


@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@token_required
@require_permission('user:read')
def get_user(user_id):
    """Get user details with stats."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    total_transactions = Transaction.query.filter_by(user_id=user_id).count()
    total_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'income'
    ).scalar() or 0
    total_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense'
    ).scalar() or 0

    return jsonify({
        'user': user.to_dict(),
        'stats': {
            'total_transactions': total_transactions,
            'total_income': float(total_income),
            'total_expense': float(total_expense)
        }
    })


@admin_bp.route('/users/<int:user_id>/status', methods=['PUT'])
@token_required
@require_permission('user:update_status')
def update_user_status(user_id):
    """Update user status (active/admin)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404

    data = request.get_json()
    admin_user = request.current_user

    if 'is_active' in data:
        user.is_active = data['is_active']
        biz_logger.info(
            f"Admin action: {admin_user.username} set user {user.username} "
            f"active={data['is_active']}"
        )

    if 'is_admin' in data:
        user.is_admin = data['is_admin']
        biz_logger.info(
            f"Admin action: {admin_user.username} set user {user.username} "
            f"admin={data['is_admin']}"
        )

    db.session.commit()

    return jsonify({
        'message': '更新成功',
        'user': user.to_dict()
    })


@admin_bp.route('/stats', methods=['GET'])
@token_required
@require_permission('user:list')
def get_admin_stats():
    """Get admin dashboard statistics."""
    today = date.today()

    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    new_users_today = User.query.filter(func.date(User.created_at) == today).count()

    total_transactions = Transaction.query.count()
    today_transactions = Transaction.query.filter(func.date(Transaction.date) == today).count()

    today_income = db.session.query(func.sum(Transaction.amount)).filter(
        func.date(Transaction.date) == today, Transaction.type == 'income'
    ).scalar() or 0

    today_expense = db.session.query(func.sum(Transaction.amount)).filter(
        func.date(Transaction.date) == today, Transaction.type == 'expense'
    ).scalar() or 0

    week_ago = today - timedelta(days=7)
    weekly_registrations = db.session.query(
        func.date(User.created_at).label('date'),
        func.count(User.id).label('count')
    ).filter(User.created_at >= week_ago).group_by(func.date(User.created_at)).all()

    return jsonify({
        'users': {
            'total': total_users,
            'active': active_users,
            'new_today': new_users_today
        },
        'transactions': {
            'total': total_transactions,
            'today': today_transactions,
            'today_income': float(today_income),
            'today_expense': float(today_expense)
        },
        'weekly_registrations': [
            {'date': str(r.date), 'count': r.count}
            for r in weekly_registrations
        ]
    })


@admin_bp.route('/categories', methods=['GET'])
@token_required
@require_permission('category:manage')
def get_all_categories():
    """List all categories."""
    categories = Category.query.order_by(Category.type, Category.name).all()
    return jsonify({'categories': [c.to_dict() for c in categories]})


@admin_bp.route('/categories', methods=['POST'])
@token_required
@require_permission('category:manage')
def create_category():
    """Create a new category."""
    data = request.get_json()

    if not data.get('name') or not data.get('type'):
        return jsonify({'error': '请填写分类名称和类型'}), 400

    category = Category(
        name=data['name'],
        type=data['type'],
        icon=data.get('icon', 'tag'),
        color=data.get('color', '#6B7280')
    )

    db.session.add(category)
    db.session.commit()

    biz_logger.info(
        f"Admin action: {request.current_user.username} created category: {data['name']}"
    )

    return jsonify({
        'message': '创建成功',
        'category': category.to_dict()
    }), 201


@admin_bp.route('/categories/<int:category_id>', methods=['PUT'])
@token_required
@require_permission('category:manage')
def update_category(category_id):
    """Update a category."""
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'error': '分类不存在'}), 404

    data = request.get_json()

    if data.get('name'):
        category.name = data['name']
    if data.get('icon'):
        category.icon = data['icon']
    if data.get('color'):
        category.color = data['color']

    db.session.commit()

    biz_logger.info(
        f"Admin action: {request.current_user.username} updated category id={category_id}"
    )

    return jsonify({
        'message': '更新成功',
        'category': category.to_dict()
    })


@admin_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@token_required
@require_permission('category:manage')
def delete_category(category_id):
    """Delete a category."""
    category = Category.query.get(category_id)
    if not category:
        return jsonify({'error': '分类不存在'}), 404

    if category.is_default:
        return jsonify({'error': '默认分类不能删除'}), 400

    db.session.delete(category)
    db.session.commit()

    biz_logger.info(
        f"Admin action: {request.current_user.username} deleted category: {category.name}"
    )

    return jsonify({'message': '删除成功'})
