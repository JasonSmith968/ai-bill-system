"""Billing and subscription API endpoints."""

import stripe
from flask import Blueprint, request, jsonify, current_app
from extensions import db
from utils.jwt_helper import token_required
from models.plan import Plan
from models.user import User
from services import billing_service

billing_bp = Blueprint('billing', __name__)


@billing_bp.route('/plans', methods=['GET'])
def get_plans():
    """Get all available subscription plans."""
    plans = Plan.query.filter_by(is_active=True).order_by(Plan.sort_order).all()
    return jsonify({'plans': [p.to_dict() for p in plans]})


@billing_bp.route('/subscription', methods=['GET'])
@token_required
def get_subscription():
    """Get current tenant's subscription status."""
    from flask import g
    tenant_id = getattr(g, 'current_tenant', None)
    tenant_id = tenant_id.id if tenant_id else None

    if tenant_id:
        sub = billing_service.get_tenant_subscription(tenant_id)
        plan = billing_service.get_tenant_plan(tenant_id)
    else:
        # Fallback to user-based for backward compatibility
        user_id = request.current_user.id
        sub = billing_service.get_user_subscription(user_id)
        plan = billing_service.get_user_plan(user_id)

    return jsonify({
        'subscription': sub.to_dict() if sub else None,
        'plan': plan.to_dict() if plan else None,
    })


@billing_bp.route('/checkout', methods=['POST'])
@token_required
def create_checkout():
    """Create a payment checkout session."""
    from flask import g
    user_id = request.current_user.id
    tenant = getattr(g, 'current_tenant', None)
    tenant_id = tenant.id if tenant else None
    data = request.get_json()

    plan_id = data.get('plan_id')
    billing_cycle = data.get('billing_cycle', 'monthly')
    payment_method = data.get('payment_method', 'stripe')

    if not plan_id:
        return jsonify({'error': '请选择套餐'}), 400

    if billing_cycle not in ('monthly', 'yearly'):
        return jsonify({'error': '无效的计费周期'}), 400

    if payment_method not in ('stripe', 'alipay'):
        return jsonify({'error': '无效的支付方式'}), 400

    if payment_method == 'stripe':
        result, error = billing_service.create_stripe_checkout(
            user_id, plan_id, billing_cycle, tenant_id=tenant_id
        )
    else:
        result, error = billing_service.create_alipay_order(
            user_id, plan_id, billing_cycle, tenant_id=tenant_id
        )

    if error:
        return jsonify({'error': error}), 400

    return jsonify(result)


@billing_bp.route('/checkout/success', methods=['POST'])
@token_required
def checkout_success():
    """Handle successful checkout (called by frontend after redirect)."""
    user_id = request.current_user.id
    data = request.get_json()
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({'error': '缺少 session_id'}), 400

    # Verify the session with Stripe
    import services.stripe_service as stripe_svc
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            # Trigger webhook-like processing
            billing_service.handle_stripe_checkout_completed(session)
            return jsonify({'status': 'success', 'message': '订阅激活成功'})
        else:
            return jsonify({'status': 'pending', 'message': '支付处理中'})
    except Exception as e:
        current_app.logger.error(f'Checkout success verification failed: {e}')
        return jsonify({'error': '支付验证失败'}), 400


@billing_bp.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events with idempotency protection."""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    if not sig_header:
        return jsonify({'error': 'Missing signature'}), 400

    try:
        import services.stripe_service as stripe_svc
        event = stripe_svc.construct_webhook_event(payload, sig_header)
    except ValueError as e:
        current_app.logger.error(f'Stripe webhook error: {e}')
        return jsonify({'error': str(e)}), 400
    except stripe.error.SignatureVerificationError as e:
        current_app.logger.error(f'Stripe signature verification failed: {e}')
        return jsonify({'error': 'Invalid signature'}), 400

    # Idempotency: skip if event already processed
    from models.processed_event import ProcessedEvent
    event_id = event.get('id', '')
    if event_id and ProcessedEvent.is_processed(event_id):
        current_app.logger.info(f'Stripe webhook: duplicate event {event_id}, skipping')
        return jsonify({'status': 'ok', 'duplicate': True})

    # Handle different event types
    event_type = event['type']
    data = event['data']['object']

    try:
        if event_type == 'checkout.session.completed':
            billing_service.handle_stripe_checkout_completed(data)
        elif event_type == 'customer.subscription.updated':
            billing_service.handle_stripe_subscription_updated(data)
        elif event_type == 'invoice.paid':
            billing_service.handle_stripe_invoice_paid(data)
        elif event_type == 'invoice.payment_failed':
            billing_service.handle_stripe_invoice_payment_failed(data)
        elif event_type == 'customer.subscription.deleted':
            billing_service.handle_stripe_subscription_deleted(data)
        else:
            current_app.logger.info(f'Unhandled Stripe event: {event_type}')

        # Mark event as processed (commit with the handler's transaction)
        ProcessedEvent.mark_processed(event_id, event_type)
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Stripe webhook handler failed: event={event_id}, type={event_type}, error={e}')
        return jsonify({'error': 'Webhook processing failed'}), 500

    return jsonify({'status': 'ok'})


@billing_bp.route('/webhook/alipay', methods=['POST'])
def alipay_webhook():
    """Handle Alipay async notification."""
    params = request.form.to_dict()

    if not params:
        return 'failure'

    # Verify signature
    import services.alipay_service as alipay_svc
    if not alipay_svc.verify_callback(params):
        current_app.logger.error('Alipay signature verification failed')
        return 'failure'

    # Process callback
    success = billing_service.handle_alipay_callback(params)
    return 'success' if success else 'failure'


@billing_bp.route('/cancel', methods=['POST'])
@token_required
def cancel_subscription():
    """Cancel current subscription."""
    user_id = request.current_user.id
    result, error = billing_service.cancel_subscription(user_id)

    if error:
        return jsonify({'error': error}), 400

    return jsonify(result)


@billing_bp.route('/usage', methods=['GET'])
@token_required
def get_usage():
    """Get current month's usage statistics."""
    user_id = request.current_user.id
    stats = billing_service.get_usage_stats(user_id)
    return jsonify(stats)


@billing_bp.route('/usage/history', methods=['GET'])
@token_required
def get_usage_history():
    """Get usage history for the last 12 months."""
    user_id = request.current_user.id
    limit = request.args.get('limit', 12, type=int)
    history = billing_service.get_usage_history(user_id, limit)
    return jsonify({'history': history})


@billing_bp.route('/portal', methods=['POST'])
@token_required
def create_portal():
    """Create Stripe customer portal for managing subscription."""
    user_id = request.current_user.id
    user = User.query.get(user_id)

    if not user or not user.stripe_customer_id:
        return jsonify({'error': '未找到 Stripe 客户信息'}), 400

    import services.stripe_service as stripe_svc
    frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:5173')

    try:
        session = stripe_svc.create_portal_session(
            customer_id=user.stripe_customer_id,
            return_url=f'{frontend_url}/profile'
        )
        return jsonify({'portal_url': session.url})
    except Exception as e:
        current_app.logger.error(f'Failed to create portal session: {e}')
        return jsonify({'error': '创建管理门户失败'}), 500
