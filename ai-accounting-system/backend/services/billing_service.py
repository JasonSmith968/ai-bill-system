"""Billing service - core subscription and usage logic."""

import logging
from datetime import datetime, date
from flask import current_app
from extensions import db
from models.plan import Plan
from models.subscription import Subscription
from models.usage import UsageLog
from models.user import User

logger = logging.getLogger(__name__)


def get_user_plan(user_id):
    """Get user's current plan. Returns Plan object (defaults to free)."""
    user = User.query.get(user_id)
    if not user:
        return Plan.query.filter_by(name='free').first()

    # Prefer tenant-based subscription
    if user.tenant_id:
        plan = get_tenant_plan(user.tenant_id)
        if plan:
            return plan

    if user.subscription and user.subscription.status == 'active':
        plan = user.subscription.plan
        if plan and plan.is_active:
            return plan

    return Plan.query.filter_by(name='free').first()


def get_user_subscription(user_id):
    """Get user's active subscription record (tenant-aware)."""
    user = User.query.get(user_id)
    if user and user.tenant_id:
        sub = get_tenant_subscription(user.tenant_id)
        if sub:
            return sub
    return Subscription.query.filter_by(
        user_id=user_id,
        status='active'
    ).first()


def get_tenant_plan(tenant_id):
    """Get tenant's current plan. Returns Plan object (defaults to free)."""
    sub = get_tenant_subscription(tenant_id)
    if sub and sub.plan and sub.plan.is_active:
        return sub.plan
    return Plan.query.filter_by(name='free').first()


def get_tenant_subscription(tenant_id):
    """Get tenant's active subscription record."""
    return Subscription.query.filter_by(
        tenant_id=tenant_id,
        status='active'
    ).first()


def check_ai_quota(user_id):
    """Check if user has remaining AI quota (calls + tokens).

    Returns:
        (allowed: bool, details: dict)
        If allowed is False, details contains info about which limit was hit.
    """
    plan = get_user_plan(user_id)
    if not plan:
        return False, {'error': 'no_plan', 'message': '无法获取套餐信息'}

    usage = UsageLog.get_or_create_current(
        user_id,
        calls_limit=plan.ai_calls_limit,
        token_limit=plan.token_limit
    )

    calls_remaining = max(0, usage.calls_limit - usage.calls_used)
    tokens_remaining = max(0, usage.token_limit - usage.tokens_used)

    if usage.calls_used >= usage.calls_limit:
        return False, {
            'error': 'calls_exceeded',
            'message': f'本月 AI 调用次数已用尽 ({usage.calls_used}/{usage.calls_limit})',
            'calls_used': usage.calls_used,
            'calls_limit': usage.calls_limit,
            'tokens_used': usage.tokens_used,
            'tokens_limit': usage.token_limit,
            'calls_remaining': 0,
            'tokens_remaining': tokens_remaining,
            'plan_name': plan.name,
            'reset_date': _get_next_reset_date(),
        }

    if usage.tokens_used >= usage.token_limit:
        return False, {
            'error': 'tokens_exceeded',
            'message': f'本月 Token 额度已用尽 ({usage.tokens_used}/{usage.token_limit})',
            'calls_used': usage.calls_used,
            'calls_limit': usage.calls_limit,
            'tokens_used': usage.tokens_used,
            'tokens_limit': usage.token_limit,
            'calls_remaining': calls_remaining,
            'tokens_remaining': 0,
            'plan_name': plan.name,
            'reset_date': _get_next_reset_date(),
        }

    return True, {
        'calls_remaining': calls_remaining,
        'tokens_remaining': tokens_remaining,
        'calls_limit': usage.calls_limit,
        'tokens_limit': usage.token_limit,
    }


def consume_ai_usage(user_id, tokens_used=0):
    """Record AI usage: increment call count and add tokens used."""
    plan = get_user_plan(user_id)
    if not plan:
        return

    usage = UsageLog.get_or_create_current(
        user_id,
        calls_limit=plan.ai_calls_limit,
        token_limit=plan.token_limit
    )

    usage.calls_used += 1
    usage.tokens_used += max(0, tokens_used)
    usage.updated_at = datetime.utcnow()
    db.session.commit()


def get_usage_stats(user_id):
    """Get current month's usage statistics."""
    plan = get_user_plan(user_id)
    usage = UsageLog.get_or_create_current(
        user_id,
        calls_limit=plan.ai_calls_limit if plan else 50,
        token_limit=plan.token_limit if plan else 100000
    )

    subscription = get_user_subscription(user_id)

    return {
        'usage': usage.to_dict(),
        'plan': plan.to_dict() if plan else None,
        'subscription': subscription.to_dict() if subscription else None,
        'reset_date': _get_next_reset_date(),
    }


def get_usage_history(user_id, limit=12):
    """Get usage history for the last N months."""
    logs = UsageLog.query.filter_by(user_id=user_id) \
        .order_by(UsageLog.period.desc()) \
        .limit(limit) \
        .all()
    return [log.to_dict() for log in logs]


def create_stripe_checkout(user_id, plan_id, billing_cycle, tenant_id=None):
    """Create a Stripe Checkout Session for subscription."""
    import services.stripe_service as stripe_svc

    user = User.query.get(user_id)
    plan = Plan.query.get(plan_id)

    if not user or not plan:
        return None, '用户或套餐不存在'

    if plan.name == 'free':
        return None, '免费套餐无需支付'

    # Get or create Stripe customer
    if not user.stripe_customer_id:
        customer = stripe_svc.create_customer(user)
        user.stripe_customer_id = customer.id
        db.session.commit()

    # Select price ID based on billing cycle
    if billing_cycle == 'yearly':
        price_id = plan.stripe_price_id_yearly
    else:
        price_id = plan.stripe_price_id_monthly

    if not price_id:
        return None, '该套餐的支付价格未配置'

    # Create checkout session
    frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:5173')
    success_url = f'{frontend_url}/billing-success?session_id={{CHECKOUT_SESSION_ID}}'
    cancel_url = f'{frontend_url}/pricing'

    session = stripe_svc.create_checkout_session(
        customer_id=user.stripe_customer_id,
        price_id=price_id,
        success_url=success_url,
        cancel_url=cancel_url
    )

    return {
        'checkout_url': session.url,
        'session_id': session.id,
    }, None


def create_alipay_order(user_id, plan_id, billing_cycle):
    """Create an Alipay payment order."""
    import services.alipay_service as alipay_svc

    user = User.query.get(user_id)
    plan = Plan.query.get(plan_id)

    if not user or not plan:
        return None, '用户或套餐不存在'

    if plan.name == 'free':
        return None, '免费套餐无需支付'

    # Calculate price
    if billing_cycle == 'yearly':
        amount = plan.price_yearly
        cycle_text = '年付'
    else:
        amount = plan.price_monthly
        cycle_text = '月付'

    if amount <= 0:
        return None, '支付金额无效'

    # Generate trade number
    out_trade_no = alipay_svc.generate_out_trade_no()

    # Create trade
    subject = f'AI智能记账 {plan.display_name} ({cycle_text})'
    result = alipay_svc.create_trade(
        out_trade_no=out_trade_no,
        total_amount=amount,
        subject=subject,
        body=f'{plan.display_name} {cycle_text} 订阅'
    )

    # Store pending subscription
    _create_pending_subscription(user_id, plan_id, billing_cycle, alipay_trade_no=out_trade_no)

    return result, None


def handle_stripe_checkout_completed(session):
    """Handle Stripe checkout.session.completed webhook event."""
    customer_id = session.get('customer')
    subscription_id = session.get('subscription')

    if not customer_id:
        current_app.logger.error('Stripe webhook: no customer in session')
        return

    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        current_app.logger.error(f'Stripe webhook: no user found for customer {customer_id}')
        return

    # Get subscription details from Stripe
    import services.stripe_service as stripe_svc
    stripe_sub = stripe_svc.get_subscription(subscription_id)

    # Determine plan from price ID
    price_id = stripe_sub['items']['data'][0]['price']['id']
    plan = _find_plan_by_stripe_price_id(price_id)

    if not plan:
        current_app.logger.error(f'Stripe webhook: no plan found for price {price_id}')
        return

    # Determine billing cycle
    interval = stripe_sub['items']['data'][0]['price']['recurring']['interval']
    billing_cycle = 'yearly' if interval == 'year' else 'monthly'

    # Create or update subscription (prefer tenant binding)
    tenant_id = user.tenant_id
    if tenant_id:
        sub = Subscription.query.filter_by(tenant_id=tenant_id, status='active').first()
    else:
        sub = Subscription.query.filter_by(user_id=user.id, status='active').first()

    if sub:
        sub.plan_id = plan.id
        sub.billing_cycle = billing_cycle
        sub.stripe_subscription_id = subscription_id
        sub.current_period_start = datetime.fromtimestamp(stripe_sub['current_period_start'])
        sub.current_period_end = datetime.fromtimestamp(stripe_sub['current_period_end'])
    else:
        sub = Subscription(
            tenant_id=tenant_id,
            user_id=user.id,
            plan_id=plan.id,
            status='active',
            billing_cycle=billing_cycle,
            stripe_subscription_id=subscription_id,
            stripe_customer_id=customer_id,
            current_period_start=datetime.fromtimestamp(stripe_sub['current_period_start']),
            current_period_end=datetime.fromtimestamp(stripe_sub['current_period_end']),
        )
        db.session.add(sub)

    # Update tenant and user subscription references
    if tenant_id:
        from models.tenant import Tenant
        tenant = Tenant.query.get(tenant_id)
        if tenant:
            tenant.plan_id = plan.id
            tenant.stripe_subscription_id = subscription_id
            tenant.stripe_customer_id = customer_id

    user.subscription_id = sub.id
    db.session.commit()

    current_app.logger.info(f'Stripe subscription activated: user={user.id}, plan={plan.name}')


def handle_stripe_invoice_paid(invoice):
    """Handle Stripe invoice.paid webhook event."""
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return

    sub = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first()
    if sub:
        sub.status = 'active'
        sub.current_period_start = datetime.fromtimestamp(invoice['period_start'])
        sub.current_period_end = datetime.fromtimestamp(invoice['period_end'])
        db.session.commit()


def handle_stripe_invoice_payment_failed(invoice):
    """Handle Stripe invoice.payment_failed webhook event."""
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        return

    sub = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first()
    if sub:
        sub.status = 'past_due'
        db.session.commit()


def handle_stripe_subscription_updated(data):
    """Handle Stripe customer.subscription.updated webhook events.

    Covers: plan changes, pause/resume, quantity changes, trial end,
    cancellation schedule updates from the Stripe Customer Portal.
    """
    subscription_id = data.get('id')
    if not subscription_id:
        logger.warning('subscription.updated event missing subscription id')
        return

    sub = Subscription.query.filter_by(stripe_subscription_id=subscription_id).first()
    if not sub:
        logger.warning(f'Subscription not found for stripe ID: {subscription_id}')
        return

    # Map Stripe status to our status
    stripe_status = data.get('status', '')
    status_map = {
        'active': 'active',
        'past_due': 'past_due',
        'unpaid': 'past_due',
        'canceled': 'canceled',
        'incomplete': 'inactive',
        'incomplete_expired': 'canceled',
        'trialing': 'trialing',
        'paused': 'paused',
    }
    new_status = status_map.get(stripe_status, sub.status)
    sub.status = new_status

    # Update period dates if present
    current_period_end = data.get('current_period_end')
    if current_period_end:
        sub.current_period_end = datetime.fromtimestamp(current_period_end)

    # Handle cancellation schedule (cancel_at_period_end from Customer Portal)
    cancel_at_period_end = data.get('cancel_at_period_end', False)
    if cancel_at_period_end:
        logger.info(f'Subscription {sub.id} scheduled to cancel at period end')

    db.session.commit()
    logger.info(f'Subscription {sub.id} updated: status={new_status}, cancel_at_end={cancel_at_period_end}')


def handle_stripe_subscription_deleted(subscription):
    """Handle Stripe customer.subscription.deleted webhook event."""
    stripe_sub_id = subscription.get('id')
    if not stripe_sub_id:
        return

    sub = Subscription.query.filter_by(stripe_subscription_id=stripe_sub_id).first()
    if sub:
        sub.status = 'cancelled'
        sub.cancelled_at = datetime.utcnow()
        db.session.commit()

        # Clear tenant subscription references
        if sub.tenant_id:
            from models.tenant import Tenant
            tenant = Tenant.query.get(sub.tenant_id)
            if tenant:
                tenant.plan_id = None
                tenant.stripe_subscription_id = None

        # Clear user's subscription reference
        user = User.query.get(sub.user_id)
        if user:
            user.subscription_id = None
            db.session.commit()


def handle_alipay_callback(params):
    """Handle Alipay async notification."""
    trade_status = params.get('trade_status')
    out_trade_no = params.get('out_trade_no')

    if not out_trade_no:
        return False

    sub = Subscription.query.filter_by(alipay_trade_no=out_trade_no).first()
    if not sub:
        current_app.logger.error(f'Alipay callback: no subscription found for {out_trade_no}')
        return False

    if trade_status == 'TRADE_SUCCESS':
        sub.status = 'active'
        # Set period to 1 month or 1 year from now
        now = datetime.utcnow()
        sub.current_period_start = now
        if sub.billing_cycle == 'yearly':
            from dateutil.relativedelta import relativedelta
            sub.current_period_end = now + relativedelta(years=1)
        else:
            from dateutil.relativedelta import relativedelta
            sub.current_period_end = now + relativedelta(months=1)

        # Update user
        user = User.query.get(sub.user_id)
        if user:
            user.subscription_id = sub.id

        db.session.commit()
        current_app.logger.info(f'Alipay subscription activated: user={sub.user_id}')
        return True

    elif trade_status == 'TRADE_CLOSED':
        sub.status = 'cancelled'
        db.session.commit()
        return True

    return False


def cancel_subscription(user_id):
    """Cancel subscription (tenant-aware).

    Strategy: cancel with Stripe FIRST, then update local DB.
    If Stripe fails after retries, do NOT mark local subscription as cancelled
    — the subscription remains active and the user should retry.
    """
    import time
    user = User.query.get(user_id)
    # Prefer tenant subscription
    if user and user.tenant_id:
        sub = get_tenant_subscription(user.tenant_id)
    else:
        sub = get_user_subscription(user_id)

    if not sub:
        return None, '没有找到活跃的订阅'

    # Step 1: Cancel with Stripe FIRST (with retry)
    stripe_success = False
    if sub.stripe_subscription_id:
        import services.stripe_service as stripe_svc
        max_retries = 3
        for attempt in range(max_retries):
            try:
                stripe_svc.cancel_subscription(sub.stripe_subscription_id)
                stripe_success = True
                break
            except Exception as e:
                current_app.logger.warning(
                    f'Stripe cancel attempt {attempt + 1}/{max_retries} failed: {e}'
                )
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # exponential backoff

        if not stripe_success:
            current_app.logger.error(
                f'Failed to cancel Stripe subscription after {max_retries} attempts: '
                f'sub={sub.id}, stripe_id={sub.stripe_subscription_id}'
            )
            return None, '支付平台取消失败，请稍后重试或联系客服'

    # Step 2: Stripe confirmed (or no Stripe ID) — update local DB
    try:
        sub.status = 'cancelled'
        sub.cancelled_at = datetime.utcnow()

        # Clear tenant subscription references
        if sub.tenant_id:
            from models.tenant import Tenant
            tenant = Tenant.query.get(sub.tenant_id)
            if tenant:
                tenant.plan_id = None
                tenant.stripe_subscription_id = None

        # Clear user's subscription reference
        if user:
            user.subscription_id = None

        db.session.commit()
        return {'message': '订阅已取消'}, None

    except Exception as e:
        # DB update failed after Stripe succeeded — log and alert
        db.session.rollback()
        current_app.logger.critical(
            f'CRITICAL: Stripe cancelled but local DB update failed: '
            f'sub={sub.id}, stripe_id={sub.stripe_subscription_id}, error={e}'
        )
        return None, '取消处理异常，请联系客服'


def _create_pending_subscription(user_id, plan_id, billing_cycle, alipay_trade_no=None, stripe_sub_id=None, tenant_id=None):
    """Create a pending subscription record."""
    # If tenant_id not provided, try to get from user
    if tenant_id is None:
        user = User.query.get(user_id)
        tenant_id = user.tenant_id if user else None

    sub = Subscription(
        tenant_id=tenant_id,
        user_id=user_id,
        plan_id=plan_id,
        status='pending',
        billing_cycle=billing_cycle,
        alipay_trade_no=alipay_trade_no,
        stripe_subscription_id=stripe_sub_id,
    )
    db.session.add(sub)
    db.session.commit()
    return sub


def _find_plan_by_stripe_price_id(price_id):
    """Find a plan by its Stripe price ID."""
    plan = Plan.query.filter_by(stripe_price_id_monthly=price_id).first()
    if not plan:
        plan = Plan.query.filter_by(stripe_price_id_yearly=price_id).first()
    return plan


def _get_next_reset_date():
    """Get the date when usage will reset (1st of next month)."""
    today = date.today()
    if today.month == 12:
        return date(today.year + 1, 1, 1).isoformat()
    return date(today.year, today.month + 1, 1).isoformat()
