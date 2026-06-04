import logging
from datetime import datetime, date
from flask import Blueprint, request, jsonify, g
from extensions import db
from models.transaction import Transaction, Category
from utils.jwt_helper import token_required

logger = logging.getLogger(__name__)
biz_logger = logging.getLogger('business')

transactions_bp = Blueprint('transactions', __name__)


def _resolve_tenant_id(user):
    """Resolve tenant_id for the current request.

    Resolution order:
    1. user.tenant_id (set on the User model)
    2. g.current_tenant (set by tenant_context middleware from JWT)
    3. First TenantMember record for this user
    4. First active Tenant in the system (fallback for single-tenant dev)

    Returns tenant_id or None.
    """
    # 1. Direct from user model
    tenant_id = getattr(user, 'tenant_id', None)
    if tenant_id:
        return tenant_id

    # 2. From tenant context middleware (JWT claim)
    tenant = getattr(g, 'current_tenant', None)
    if tenant:
        return tenant.id

    # 3. From TenantMember record
    from models.tenant import TenantMember
    membership = TenantMember.query.filter_by(user_id=user.id).first()
    if membership:
        return membership.tenant_id

    # 4. Fallback: first active tenant (dev convenience)
    from models.tenant import Tenant
    default_tenant = Tenant.query.first()
    if default_tenant:
        return default_tenant.id

    return None


def _resolve_category(category_id):
    """Validate that category_id exists and belongs to the current tenant.

    Returns (category_id, error_response) tuple.
    If valid: (category_id, None)
    If invalid: (None, (jsonify_error, status_code))
    """
    if category_id is None:
        return None, None

    try:
        category = Category.query.get(category_id)
    except Exception:
        # ObjectDeletedError: tenant auto-filter hides the row from
        # the current tenant, but the PK was in the identity map.
        return None, (jsonify({'error': '分类不存在'}), 400)

    if category is None:
        return None, (jsonify({'error': '分类不存在'}), 400)

    # Tenant isolation: category must belong to current tenant (or be global)
    tenant = getattr(g, 'current_tenant', None)
    if tenant and category.tenant_id is not None and category.tenant_id != tenant.id:
        return None, (jsonify({'error': '分类不属于当前租户'}), 400)

    return category_id, None


@transactions_bp.route('', methods=['GET'])
@token_required
def get_transactions():
    """List transactions with filters and pagination."""
    user = request.current_user
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    transaction_type = request.args.get('type')
    category_id = request.args.get('category_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword')

    query = Transaction.query.filter_by(user_id=user.id)

    if transaction_type:
        query = query.filter_by(type=transaction_type)
    if category_id:
        query = query.filter_by(category_id=category_id)
    if start_date:
        query = query.filter(Transaction.date >= datetime.strptime(start_date, '%Y-%m-%d').date())
    if end_date:
        query = query.filter(Transaction.date <= datetime.strptime(end_date, '%Y-%m-%d').date())
    if keyword:
        query = query.filter(
            (Transaction.description.contains(keyword)) |
            (Transaction.note.contains(keyword))
        )

    query = query.order_by(Transaction.date.desc(), Transaction.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'transactions': [t.to_dict() for t in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages
    })


@transactions_bp.route('', methods=['POST'])
@token_required
def create_transaction():
    """Create a new transaction."""
    user = request.current_user
    data = request.get_json()

    if not data.get('type') or not data.get('amount'):
        return jsonify({'error': '请填写交易类型和金额'}), 400

    if data['type'] not in ['income', 'expense']:
        return jsonify({'error': '交易类型无效'}), 400

    try:
        amount = float(data['amount'])
        if amount <= 0:
            return jsonify({'error': '金额必须大于0'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': '金额格式无效'}), 400

    # Resolve tenant_id — required for multi-tenant isolation
    tenant_id = _resolve_tenant_id(user)
    if not tenant_id:
        return jsonify({'error': '无法确定租户，请联系管理员'}), 403

    transaction_date = date.today()
    if data.get('date'):
        try:
            transaction_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': '日期格式无效'}), 400

    # Validate category belongs to current tenant
    category_id, err = _resolve_category(data.get('category_id'))
    if err:
        return err

    transaction = Transaction(
        user_id=user.id,
        tenant_id=tenant_id,
        type=data['type'],
        amount=amount,
        category_id=category_id,
        description=data.get('description', ''),
        note=data.get('note', ''),
        date=transaction_date
    )

    db.session.add(transaction)
    db.session.commit()

    biz_logger.info(f"Transaction created: user_id={user.id} type={data['type']} amount={amount}")

    return jsonify({
        'message': '记录创建成功',
        'transaction': transaction.to_dict()
    }), 201


@transactions_bp.route('/<int:transaction_id>', methods=['GET'])
@token_required
def get_transaction(transaction_id):
    """Get a single transaction."""
    user = request.current_user
    transaction = Transaction.query.filter_by(
        id=transaction_id, user_id=user.id
    ).first()

    if not transaction:
        return jsonify({'error': '记录不存在'}), 404

    return jsonify({'transaction': transaction.to_dict()})


@transactions_bp.route('/<int:transaction_id>', methods=['PUT'])
@token_required
def update_transaction(transaction_id):
    """Update a transaction."""
    user = request.current_user
    transaction = Transaction.query.filter_by(
        id=transaction_id, user_id=user.id
    ).first()

    if not transaction:
        return jsonify({'error': '记录不存在'}), 404

    data = request.get_json()

    if data.get('type'):
        if data['type'] not in ['income', 'expense']:
            return jsonify({'error': '交易类型无效'}), 400
        transaction.type = data['type']

    if data.get('amount'):
        try:
            amount = float(data['amount'])
            if amount <= 0:
                return jsonify({'error': '金额必须大于0'}), 400
            transaction.amount = amount
        except (ValueError, TypeError):
            return jsonify({'error': '金额格式无效'}), 400

    if data.get('category_id') is not None:
        category_id, err = _resolve_category(data['category_id'])
        if err:
            return err
        transaction.category_id = category_id
    if data.get('description') is not None:
        transaction.description = data['description']
    if data.get('note') is not None:
        transaction.note = data['note']
    if data.get('date'):
        try:
            transaction.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': '日期格式无效'}), 400

    db.session.commit()

    biz_logger.info(f"Transaction updated: id={transaction_id} user_id={user.id}")

    return jsonify({
        'message': '更新成功',
        'transaction': transaction.to_dict()
    })


@transactions_bp.route('/<int:transaction_id>', methods=['DELETE'])
@token_required
def delete_transaction(transaction_id):
    """Delete a transaction."""
    user = request.current_user
    transaction = Transaction.query.filter_by(
        id=transaction_id, user_id=user.id
    ).first()

    if not transaction:
        return jsonify({'error': '记录不存在'}), 404

    db.session.delete(transaction)
    db.session.commit()

    biz_logger.info(f"Transaction deleted: id={transaction_id} user_id={user.id}")

    return jsonify({'message': '删除成功'})


@transactions_bp.route('/categories', methods=['GET'])
@token_required
def get_categories():
    """List categories."""
    transaction_type = request.args.get('type')
    query = Category.query
    if transaction_type:
        query = query.filter_by(type=transaction_type)

    categories = query.all()
    return jsonify({'categories': [c.to_dict() for c in categories]})
