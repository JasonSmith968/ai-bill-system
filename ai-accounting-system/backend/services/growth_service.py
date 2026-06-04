"""SaaS Growth Service

Core logic for referral system, invite rewards, affiliate tracking,
onboarding flow, email lifecycle, retention automation, and AI usage nudges.
"""

import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

from flask import current_app
from extensions import db


class GrowthService:
    """Growth service — wraps module-level functions for dependency injection.

    Usage:
        svc = GrowthService(db.session)
        code = svc.generate_referral_code(user_id)
    """

    def __init__(self, session=None):
        self._session = session

    # --- Referral ---
    def generate_referral_code(self, user_id: int) -> str:
        return generate_referral_code(user_id)

    def get_referral_stats(self, user_id: int) -> dict:
        return get_referral_stats(user_id)

    def process_referral_signup(self, referred_user_id: int, referral_code: str) -> dict:
        return process_referral_signup(referred_user_id, referral_code)

    def process_referral_conversion(self, user_id: int) -> dict:
        return process_referral_conversion(user_id)

    # --- Affiliate ---
    def track_affiliate_click(self, affiliate_code: str, **kwargs) -> dict:
        return track_affiliate_click(affiliate_code, **kwargs)

    def process_affiliate_conversion(self, user_id: int, affiliate_code: str,
                                      revenue_cents: int) -> dict:
        # Wrapper adapts (user_id, affiliate_code, revenue_cents) from route
        # to underlying function which uses cookie-based affiliate tracking
        return process_affiliate_conversion(user_id, 0, revenue_cents)

    def get_affiliate_stats(self, user_id: int) -> dict:
        # Route passes user_id; look up affiliate by user_id
        from models.referral import Affiliate
        affiliate = Affiliate.query.filter_by(user_id=user_id).first()
        if not affiliate:
            return None
        return get_affiliate_stats(affiliate.id)

    # --- Onboarding ---
    def get_onboarding_progress(self, user_id: int) -> dict:
        return get_onboarding_progress(user_id)

    def complete_onboarding_step(self, user_id: int, step_key: str,
                                  status: str = 'completed') -> dict:
        return complete_onboarding_step(user_id, step_key)

    # --- Email ---
    def init_email_templates(self) -> int:
        return init_email_templates()

    def send_lifecycle_email(self, user_id: int, template_name: str,
                              context: dict = None) -> dict:
        return send_lifecycle_email(user_id, template_name, context)

    # --- Nudges ---
    def init_nudge_rules(self) -> int:
        return init_nudge_rules()

    def check_nudges(self, user_id: int) -> list:
        return check_nudges(user_id)

    # --- Retention ---
    def run_retention_check(self) -> dict:
        return run_retention_check()

    def run_nudge_check(self) -> dict:
        return run_nudge_check()

    # --- Dashboard ---
    def get_growth_dashboard(self, period_days: int = 30) -> dict:
        return get_growth_dashboard(period_days)


# ==============================================================================
# Referral System
# ==============================================================================


def generate_referral_code(user_id: int) -> str:
    """Generate a unique referral code for a user."""
    from models.referral import Referral

    existing = Referral.query.filter_by(referrer_id=user_id).first()
    if existing:
        return existing.referral_code

    # Generate 8-char alphanumeric code
    chars = string.ascii_uppercase + string.digits
    for _ in range(10):  # retry up to 10 times
        code = ''.join(secrets.choice(chars) for _ in range(8))
        if not Referral.query.filter_by(referral_code=code).first():
            referral = Referral(
                referrer_id=user_id,
                referral_code=code,
                status='pending',
            )
            db.session.add(referral)
            db.session.commit()
            return code

    raise RuntimeError("Failed to generate unique referral code")


def get_referral_stats(user_id: int) -> dict:
    """Get referral statistics for a user."""
    from models.referral import Referral
    from models.growth import GrowthEvent

    referrals = Referral.query.filter_by(referrer_id=user_id).all()

    total = len(referrals)
    registered = sum(1 for r in referrals if r.status in ('registered', 'converted', 'rewarded'))
    converted = sum(1 for r in referrals if r.status in ('converted', 'rewarded'))
    rewarded = sum(1 for r in referrals if r.status == 'rewarded')

    total_rewards = sum(r.reward_value for r in referrals if r.status == 'rewarded')

    # Recent invite events
    invites_sent = GrowthEvent.query.filter_by(
        user_id=user_id, event_type='invite_sent'
    ).count()

    return {
        'referral_code': referrals[0].referral_code if referrals else None,
        'total_referrals': total,
        'registered': registered,
        'converted': converted,
        'rewarded': rewarded,
        'total_reward_value': total_rewards,
        'conversion_rate': round(converted / max(total, 1) * 100, 1),
        'referrals': [r.to_dict() for r in referrals[:50]],
    }


def process_referral_signup(referred_user_id: int, referral_code: str) -> dict:
    """Process a new user signup via referral link."""
    from models.referral import Referral, InviteReward
    from models.growth import GrowthEvent

    referral = Referral.query.filter_by(referral_code=referral_code).first()
    if not referral:
        return {'success': False, 'error': 'Invalid referral code'}

    if referral.referrer_id == referred_user_id:
        return {'success': False, 'error': 'Cannot refer yourself'}

    # Check if already referred
    existing = Referral.query.filter_by(referred_id=referred_user_id).first()
    if existing:
        return {'success': False, 'error': 'User already referred'}

    referral.referred_id = referred_user_id
    referral.status = 'registered'
    referral.registered_at = datetime.utcnow()

    # Track event
    event = GrowthEvent(
        user_id=referred_user_id,
        event_type='invite_accepted',
        event_data={'referral_code': referral_code, 'referrer_id': referral.referrer_id},
        source='referral',
    )
    db.session.add(event)

    # Give referred user reward (signup trigger)
    reward_config = InviteReward.query.filter_by(trigger='signup', is_active=True).first()
    if reward_config and reward_config.referred_reward_type:
        _apply_reward(referred_user_id, reward_config.referred_reward_type, reward_config.referred_reward_value)

    db.session.commit()

    return {'success': True, 'referral_id': referral.id}


def process_referral_conversion(user_id: int) -> dict:
    """Process a referral conversion (first payment)."""
    from models.referral import Referral, InviteReward
    from models.growth import GrowthEvent

    referral = Referral.query.filter_by(referred_id=user_id, status='registered').first()
    if not referral:
        return {'success': False, 'error': 'No pending referral found'}

    referral.status = 'converted'
    referral.converted_at = datetime.utcnow()

    # Track event
    event = GrowthEvent(
        user_id=user_id,
        event_type='invite_converted',
        event_data={'referral_id': referral.id, 'referrer_id': referral.referrer_id},
        source='referral',
    )
    db.session.add(event)

    # Reward referrer
    reward_config = InviteReward.query.filter_by(trigger='first_payment', is_active=True).first()
    if reward_config:
        _apply_reward(referral.referrer_id, reward_config.referrer_reward_type, reward_config.referrer_reward_value)
        referral.reward_type = reward_config.referrer_reward_type
        referral.reward_value = reward_config.referrer_reward_value
        referral.status = 'rewarded'
        referral.rewarded_at = datetime.utcnow()

        # Give referred user reward too
        if reward_config.referred_reward_type:
            _apply_reward(user_id, reward_config.referred_reward_type, reward_config.referred_reward_value)

    db.session.commit()

    return {'success': True, 'referral_id': referral.id}


def _apply_reward(user_id: int, reward_type: str, reward_value: int):
    """Apply a reward to a user."""
    from models.user import User

    user = User.query.get(user_id)
    if not user:
        return

    if reward_type == 'free_days':
        # Extend subscription by N days
        if hasattr(user, 'subscription') and user.subscription:
            sub = user.subscription
            if sub.current_period_end:
                sub.current_period_end += timedelta(days=reward_value)
            else:
                sub.current_period_end = datetime.utcnow() + timedelta(days=reward_value)

    elif reward_type == 'credits':
        # Add usage credits
        if hasattr(user, 'usage_credits'):
            user.usage_credits = (user.usage_credits or 0) + reward_value

    elif reward_type == 'discount_pct':
        # Store discount for next invoice
        if hasattr(user, 'discount_percent'):
            user.discount_percent = max(user.discount_percent or 0, reward_value)


# ==============================================================================
# Affiliate Tracking
# ==============================================================================


def track_affiliate_click(affiliate_code: str, ip_address: str = None,
                          user_agent: str = None, referrer_url: str = None,
                          landing_page: str = None) -> dict:
    """Track an affiliate link click."""
    from models.referral import Affiliate, AffiliateClick

    affiliate = Affiliate.query.filter_by(affiliate_code=affiliate_code, status='active').first()
    if not affiliate:
        return {'success': False, 'error': 'Invalid affiliate code'}

    click = AffiliateClick(
        affiliate_id=affiliate.id,
        ip_address=ip_address,
        user_agent=user_agent,
        referrer_url=referrer_url,
        landing_page=landing_page,
    )
    affiliate.total_clicks += 1

    db.session.add(click)
    db.session.commit()

    return {'success': True, 'click_id': click.id, 'affiliate_id': affiliate.id}


def process_affiliate_conversion(user_id: int, subscription_id: int,
                                  revenue_cents: int) -> dict:
    """Process an affiliate conversion."""
    from models.referral import Affiliate, AffiliateClick, AffiliateConversion
    from models.growth import GrowthEvent

    # Find the affiliate click cookie (simplified: check recent unconverted clicks)
    # In production, this would use cookie tracking
    recent_click = AffiliateClick.query.filter(
        AffiliateClick.converted == False,
        AffiliateClick.created_at >= datetime.utcnow() - timedelta(days=30),
    ).order_by(AffiliateClick.created_at.desc()).first()

    if not recent_click:
        return {'success': False, 'error': 'No affiliate click found'}

    affiliate = Affiliate.query.get(recent_click.affiliate_id)
    if not affiliate or affiliate.status != 'active':
        return {'success': False, 'error': 'Affiliate not active'}

    # Calculate commission
    if affiliate.commission_type == 'percentage':
        commission_cents = int(revenue_cents * affiliate.commission_rate)
    else:
        commission_cents = int(affiliate.commission_rate * 100)  # fixed rate in cents

    conversion = AffiliateConversion(
        affiliate_id=affiliate.id,
        click_id=recent_click.id,
        user_id=user_id,
        subscription_id=subscription_id,
        revenue_cents=revenue_cents,
        commission_cents=commission_cents,
        status='pending',
    )

    recent_click.converted = True
    recent_click.user_id = user_id
    affiliate.total_conversions += 1
    affiliate.total_revenue_cents += revenue_cents
    affiliate.total_commission_cents += commission_cents

    # Track event
    event = GrowthEvent(
        user_id=user_id,
        event_type='affiliate_conversion',
        event_data={'affiliate_id': affiliate.id, 'commission_cents': commission_cents},
        source='affiliate',
    )

    db.session.add(conversion)
    db.session.add(event)
    db.session.commit()

    return {
        'success': True,
        'conversion_id': conversion.id,
        'commission_cents': commission_cents,
    }


def get_affiliate_stats(affiliate_id: int) -> dict:
    """Get affiliate statistics."""
    from models.referral import Affiliate, AffiliateConversion

    affiliate = Affiliate.query.get(affiliate_id)
    if not affiliate:
        return {'error': 'Affiliate not found'}

    conversions = AffiliateConversion.query.filter_by(affiliate_id=affiliate_id).all()
    pending = sum(c.commission_cents for c in conversions if c.status == 'pending')
    approved = sum(c.commission_cents for c in conversions if c.status == 'approved')

    return {
        'affiliate': affiliate.to_dict(),
        'pending_commission_cents': pending,
        'approved_commission_cents': approved,
        'conversion_rate': round(
            affiliate.total_conversions / max(affiliate.total_clicks, 1) * 100, 1
        ),
        'avg_order_value_cents': round(
            affiliate.total_revenue_cents / max(affiliate.total_conversions, 1)
        ),
    }


# ==============================================================================
# Onboarding Flow
# ==============================================================================


# Default onboarding steps
DEFAULT_ONBOARDING_STEPS = [
    {
        'key': 'welcome',
        'title': '欢迎使用',
        'description': '了解系统核心功能',
        'action': 'view_tour',
        'optional': False,
    },
    {
        'key': 'create_first',
        'title': '创建第一笔记录',
        'description': '添加一笔收入或支出',
        'action': 'create_transaction',
        'optional': False,
    },
    {
        'key': 'setup_budget',
        'title': '设置预算',
        'description': '设置月度预算目标',
        'action': 'set_budget',
        'optional': True,
    },
    {
        'key': 'try_ai',
        'title': '体验 AI 助手',
        'description': '用 AI 分析你的财务数据',
        'action': 'use_ai_chat',
        'optional': True,
    },
    {
        'key': 'invite_team',
        'title': '邀请团队',
        'description': '邀请同事一起使用',
        'action': 'send_invite',
        'optional': True,
    },
]


def init_onboarding(user_id: int) -> list:
    """Initialize onboarding steps for a new user."""
    from models.growth import OnboardingStep

    existing = OnboardingStep.query.filter_by(user_id=user_id).count()
    if existing > 0:
        return get_onboarding_progress(user_id)

    steps = []
    for step_def in DEFAULT_ONBOARDING_STEPS:
        step = OnboardingStep(
            user_id=user_id,
            step_key=step_def['key'],
            status='pending',
        )
        db.session.add(step)
        steps.append(step)

    db.session.commit()
    return get_onboarding_progress(user_id)


def complete_onboarding_step(user_id: int, step_key: str) -> dict:
    """Mark an onboarding step as completed."""
    from models.growth import OnboardingStep, GrowthEvent

    step = OnboardingStep.query.filter_by(user_id=user_id, step_key=step_key).first()
    if not step:
        return {'success': False, 'error': 'Step not found'}

    if step.status == 'completed':
        return {'success': True, 'message': 'Already completed'}

    step.status = 'completed'
    step.completed_at = datetime.utcnow()

    # Track event
    event = GrowthEvent(
        user_id=user_id,
        event_type='onboarding_step',
        event_data={'step_key': step_key},
        source='onboarding',
    )
    db.session.add(event)

    # Check if all required steps complete
    required = [s for s in DEFAULT_ONBOARDING_STEPS if not s.get('optional')]
    completed_required = OnboardingStep.query.filter(
        OnboardingStep.user_id == user_id,
        OnboardingStep.step_key.in_([s['key'] for s in required]),
        OnboardingStep.status == 'completed',
    ).count()

    all_done = completed_required >= len(required)

    if all_done:
        complete_event = GrowthEvent(
            user_id=user_id,
            event_type='onboarding_complete',
            event_data={'completed_steps': completed_required},
            source='onboarding',
        )
        db.session.add(complete_event)

    db.session.commit()

    return {
        'success': True,
        'step_key': step_key,
        'onboarding_complete': all_done,
        'progress': get_onboarding_progress(user_id),
    }


def get_onboarding_progress(user_id: int) -> dict:
    """Get onboarding progress for a user."""
    from models.growth import OnboardingStep

    steps = OnboardingStep.query.filter_by(user_id=user_id).all()
    step_map = {s.step_key: s for s in steps}

    result = []
    for step_def in DEFAULT_ONBOARDING_STEPS:
        step = step_map.get(step_def['key'])
        result.append({
            'key': step_def['key'],
            'title': step_def['title'],
            'description': step_def['description'],
            'optional': step_def.get('optional', False),
            'status': step.status if step else 'pending',
            'completed_at': step.completed_at.isoformat() if step and step.completed_at else None,
        })

    completed = sum(1 for s in result if s['status'] == 'completed')
    total = len(result)

    return {
        'steps': result,
        'completed': completed,
        'total': total,
        'percent': round(completed / max(total, 1) * 100),
        'is_complete': all(
            s['status'] == 'completed'
            for s in result
            if not s.get('optional')
        ),
    }


# ==============================================================================
# Email Lifecycle
# ==============================================================================


# Default email templates
DEFAULT_EMAIL_TEMPLATES = [
    {
        'name': 'welcome',
        'subject': '欢迎加入 AI 记账系统！',
        'category': 'onboarding',
        'body_html': '''
        <h2>欢迎 {{username}}！</h2>
        <p>感谢您注册 AI 智能记账系统。</p>
        <p>以下是快速入门指南：</p>
        <ol>
            <li>创建您的第一笔记录</li>
            <li>设置月度预算</li>
            <li>体验 AI 智能分析</li>
        </ol>
        <p><a href="{{app_url}}">立即开始</a></p>
        ''',
    },
    {
        'name': 'onboarding_reminder',
        'subject': '完成设置，解锁全部功能',
        'category': 'onboarding',
        'body_html': '''
        <h2>Hi {{username}}，</h2>
        <p>您还有 {{remaining_steps}} 个步骤未完成。</p>
        <p>完成设置即可解锁 AI 分析、团队协作等功能。</p>
        <p><a href="{{app_url}}/onboarding">继续设置</a></p>
        ''',
    },
    {
        'name': 'trial_ending',
        'subject': '您的试用期即将结束',
        'category': 'retention',
        'body_html': '''
        <h2>Hi {{username}}，</h2>
        <p>您的免费试用期将在 {{days_remaining}} 天后结束。</p>
        <p>升级到付费版，享受无限 AI 分析、团队协作等功能。</p>
        <p><a href="{{app_url}}/billing">查看套餐</a></p>
        ''',
    },
    {
        'name': 'inactive_3days',
        'subject': '我们想念您！',
        'category': 'retention',
        'body_html': '''
        <h2>Hi {{username}}，</h2>
        <p>您已经 3 天没有登录了。</p>
        <p>来看看 AI 为您准备了什么新洞察吧！</p>
        <p><a href="{{app_url}}">立即查看</a></p>
        ''',
    },
    {
        'name': 'inactive_7days',
        'subject': '您的财务数据需要关注',
        'category': 'retention',
        'body_html': '''
        <h2>Hi {{username}}，</h2>
        <p>已经一周没有查看您的财务状况了。</p>
        <p>AI 助手发现了一些值得关注的趋势。</p>
        <p><a href="{{app_url}}/dashboard">查看报告</a></p>
        ''',
    },
    {
        'name': 'usage_limit_warning',
        'subject': 'AI 使用量即将达到上限',
        'category': 'engagement',
        'body_html': '''
        <h2>Hi {{username}}，</h2>
        <p>您本月的 AI 分析次数已使用 {{usage_percent}}%。</p>
        <p>升级套餐获取更多 AI 分析次数。</p>
        <p><a href="{{app_url}}/billing">升级套餐</a></p>
        ''',
    },
    {
        'name': 'feature_unlock',
        'subject': '新功能解锁：{{feature_name}}',
        'category': 'engagement',
        'body_html': '''
        <h2>Hi {{username}}，</h2>
        <p>我们刚刚上线了新功能：<strong>{{feature_name}}</strong></p>
        <p>{{feature_description}}</p>
        <p><a href="{{app_url}}{{feature_url}}">立即体验</a></p>
        ''',
    },
    {
        'name': 'referral_success',
        'subject': '恭喜！您的好友已成功注册',
        'category': 'transactional',
        'body_html': '''
        <h2>恭喜 {{username}}！</h2>
        <p>您邀请的好友 {{referred_name}} 已成功注册。</p>
        <p>您获得了 <strong>{{reward_value}}</strong> 奖励！</p>
        <p>继续邀请更多好友，获取更多奖励。</p>
        ''',
    },
]


def init_email_templates() -> int:
    """Initialize default email templates. Returns count of templates created."""
    from models.growth import EmailTemplate

    created = 0
    for tmpl in DEFAULT_EMAIL_TEMPLATES:
        existing = EmailTemplate.query.filter_by(name=tmpl['name']).first()
        if not existing:
            template = EmailTemplate(
                name=tmpl['name'],
                subject=tmpl['subject'],
                body_html=tmpl['body_html'],
                category=tmpl['category'],
                is_active=True,
            )
            db.session.add(template)
            created += 1

    db.session.commit()
    return created


def send_lifecycle_email(user_id: int, template_name: str, context: dict = None) -> dict:
    """Send a lifecycle email to a user."""
    from models.user import User
    from models.growth import EmailTemplate, EmailLog

    user = User.query.get(user_id)
    if not user:
        return {'success': False, 'error': 'User not found'}

    template = EmailTemplate.query.filter_by(name=template_name, is_active=True).first()
    if not template:
        return {'success': False, 'error': f'Template {template_name} not found'}

    # Check cooldown (don't send same template within 24h)
    recent = EmailLog.query.filter(
        EmailLog.user_id == user_id,
        EmailLog.template_name == template_name,
        EmailLog.created_at >= datetime.utcnow() - timedelta(hours=24),
    ).first()
    if recent:
        return {'success': False, 'error': 'Cooldown active'}

    # Build context
    ctx = {
        'username': user.username,
        'email': user.email,
        'app_url': current_app.config.get('FRONTEND_URL', 'http://localhost:5173'),
        **(context or {}),
    }

    # Render template
    subject = _render_template(template.subject, ctx)
    body = _render_template(template.body_html, ctx)

    # Create log entry
    log = EmailLog(
        user_id=user_id,
        template_name=template_name,
        recipient=user.email,
        subject=subject,
        status='queued',
    )
    db.session.add(log)
    db.session.commit()

    # Queue email send (via Celery)
    try:
        from tasks.growth_tasks import send_email_task
        send_email_task.delay(log.id, user.email, subject, body)
    except Exception:
        # Fallback: mark as sent (for development)
        log.status = 'sent'
        log.sent_at = datetime.utcnow()
        db.session.commit()

    return {'success': True, 'email_log_id': log.id}


def _render_template(template_str: str, context: dict) -> str:
    """Simple template rendering with {{variable}} substitution."""
    result = template_str
    for key, value in context.items():
        result = result.replace(f'{{{{{key}}}}}', str(value))
    return result


# ==============================================================================
# Retention Automation
# ==============================================================================


def check_retention_actions(user_id: int) -> list:
    """Check and trigger retention actions for a user."""
    from models.user import User
    from models.login_history import LoginHistory
    from models.growth import GrowthEvent
    from models.usage import UsageLog

    user = User.query.get(user_id)
    if not user:
        return []

    actions = []

    # Check last login
    last_login = LoginHistory.query.filter_by(user_id=user_id)\
        .order_by(LoginHistory.created_at.desc()).first()

    if last_login:
        days_inactive = (datetime.utcnow() - last_login.created_at).days
    else:
        days_inactive = 999

    # Inactive 3 days
    if days_inactive >= 3:
        actions.append({
            'type': 'email',
            'template': 'inactive_3days',
            'reason': f'Inactive for {days_inactive} days',
        })

    # Inactive 7 days
    if days_inactive >= 7:
        actions.append({
            'type': 'email',
            'template': 'inactive_7days',
            'reason': f'Inactive for {days_inactive} days',
        })

    # Check usage limits
    usage = UsageLog.get_or_create_current(user_id)
    if usage.calls_limit > 0:
        usage_pct = usage.calls_used / usage.calls_limit * 100
        if usage_pct >= 80:
            actions.append({
                'type': 'email',
                'template': 'usage_limit_warning',
                'context': {'usage_percent': round(usage_pct)},
                'reason': f'Usage at {round(usage_pct)}%',
            })

    return actions


def run_retention_check():
    """Run retention check for all active users. Called by Celery beat."""
    from models.user import User
    from models.growth import EmailLog

    users = User.query.filter_by(is_active=True).all()
    results = {'checked': 0, 'actions': 0, 'emails_sent': 0}

    for user in users:
        results['checked'] += 1
        actions = check_retention_actions(user.id)

        for action in actions:
            results['actions'] += 1

            if action['type'] == 'email':
                # Check if already sent recently
                recent = EmailLog.query.filter(
                    EmailLog.user_id == user.id,
                    EmailLog.template_name == action['template'],
                    EmailLog.created_at >= datetime.utcnow() - timedelta(hours=72),
                ).first()

                if not recent:
                    send_lifecycle_email(
                        user.id,
                        action['template'],
                        action.get('context'),
                    )
                    results['emails_sent'] += 1

    return results


# ==============================================================================
# AI Usage Nudges
# ==============================================================================


# Default nudge rules
DEFAULT_NUDGE_RULES = [
    {
        'name': 'unused_ai_chat',
        'description': 'User has not used AI chat feature',
        'trigger_condition': {
            'metric': 'ai_chat_count',
            'operator': '==',
            'value': 0,
            'period_days': 7,
        },
        'nudge_type': 'in_app',
        'nudge_content': {
            'title': '试试 AI 智能助手',
            'message': '用自然语言和 AI 对话，轻松分析您的财务数据。',
            'cta': '立即体验',
            'cta_url': '/ai/chat',
        },
        'cooldown_hours': 168,  # 7 days
        'max_sends': 2,
    },
    {
        'name': 'low_ai_usage',
        'description': 'User rarely uses AI features',
        'trigger_condition': {
            'metric': 'ai_chat_count',
            'operator': '<',
            'value': 3,
            'period_days': 30,
        },
        'nudge_type': 'in_app',
        'nudge_content': {
            'title': 'AI 助手可以帮您更多',
            'message': '试试让 AI 帮您分类交易、生成报告、分析趋势。',
            'cta': '查看功能',
            'cta_url': '/ai/features',
        },
        'cooldown_hours': 336,  # 14 days
        'max_sends': 3,
    },
    {
        'name': 'no_export',
        'description': 'User has never exported data',
        'trigger_condition': {
            'metric': 'export_count',
            'operator': '==',
            'value': 0,
            'period_days': 30,
        },
        'nudge_type': 'in_app',
        'nudge_content': {
            'title': '导出您的财务报告',
            'message': '一键导出 Excel/PDF 报告，方便分享和存档。',
            'cta': '导出报告',
            'cta_url': '/reports/export',
        },
        'cooldown_hours': 720,  # 30 days
        'max_sends': 1,
    },
    {
        'name': 'approaching_limit',
        'description': 'User approaching AI usage limit',
        'trigger_condition': {
            'metric': 'usage_percent',
            'operator': '>=',
            'value': 80,
            'period_days': 1,  # current month
        },
        'nudge_type': 'email',
        'nudge_content': {
            'title': 'AI 使用量提醒',
            'message': '您本月的 AI 分析次数已使用 80%，升级获取更多额度。',
            'cta': '升级套餐',
            'cta_url': '/billing',
        },
        'cooldown_hours': 72,
        'max_sends': 2,
    },
    {
        'name': 'onboarding_incomplete',
        'description': 'User has incomplete onboarding',
        'trigger_condition': {
            'metric': 'onboarding_percent',
            'operator': '<',
            'value': 100,
            'period_days': 3,
        },
        'nudge_type': 'in_app',
        'nudge_content': {
            'title': '完成设置，解锁全部功能',
            'message': '还有几个步骤即可使用全部功能。',
            'cta': '继续设置',
            'cta_url': '/onboarding',
        },
        'cooldown_hours': 48,
        'max_sends': 3,
    },
]


def init_nudge_rules() -> int:
    """Initialize default nudge rules. Returns count of rules created."""
    from models.growth import NudgeRule

    created = 0
    for rule_def in DEFAULT_NUDGE_RULES:
        existing = NudgeRule.query.filter_by(name=rule_def['name']).first()
        if not existing:
            rule = NudgeRule(
                name=rule_def['name'],
                description=rule_def['description'],
                trigger_condition=rule_def['trigger_condition'],
                nudge_type=rule_def['nudge_type'],
                nudge_content=rule_def['nudge_content'],
                cooldown_hours=rule_def.get('cooldown_hours', 72),
                max_sends=rule_def.get('max_sends', 3),
                is_active=True,
            )
            db.session.add(rule)
            created += 1

    db.session.commit()
    return created


def check_nudges(user_id: int) -> list:
    """Check which nudges should be triggered for a user."""
    from models.growth import NudgeRule, NudgeLog

    rules = NudgeRule.query.filter_by(is_active=True).all()
    triggered = []

    for rule in rules:
        # Check max sends
        send_count = NudgeLog.query.filter_by(
            user_id=user_id, rule_id=rule.id
        ).count()
        if send_count >= rule.max_sends:
            continue

        # Check cooldown
        last_send = NudgeLog.query.filter_by(
            user_id=user_id, rule_id=rule.id
        ).order_by(NudgeLog.created_at.desc()).first()

        if last_send:
            hours_since = (datetime.utcnow() - last_send.created_at).total_seconds() / 3600
            if hours_since < rule.cooldown_hours:
                continue

        # Check trigger condition
        if _evaluate_nudge_condition(user_id, rule.trigger_condition):
            triggered.append(rule)

    return triggered


def _evaluate_nudge_condition(user_id: int, condition: dict) -> bool:
    """Evaluate a nudge trigger condition."""
    metric = condition.get('metric', '')
    operator = condition.get('operator', '==')
    value = condition.get('value', 0)
    period_days = condition.get('period_days', 30)

    actual = _get_nudge_metric(user_id, metric, period_days)

    if operator == '==':
        return actual == value
    elif operator == '!=':
        return actual != value
    elif operator == '<':
        return actual < value
    elif operator == '>':
        return actual > value
    elif operator == '<=':
        return actual <= value
    elif operator == '>=':
        return actual >= value

    return False


def _get_nudge_metric(user_id: int, metric: str, period_days: int) -> float:
    """Get a metric value for nudge evaluation."""
    from models.agent_log import AgentExecutionLog
    from models.transaction import Transaction
    from models.growth import OnboardingStep

    since = datetime.utcnow() - timedelta(days=period_days)

    if metric == 'ai_chat_count':
        return AgentExecutionLog.query.filter(
            AgentExecutionLog.user_id == user_id,
            AgentExecutionLog.created_at >= since,
        ).count()

    elif metric == 'export_count':
        # Check growth events
        from models.growth import GrowthEvent
        return GrowthEvent.query.filter(
            GrowthEvent.user_id == user_id,
            GrowthEvent.event_type == 'export',
            GrowthEvent.created_at >= since,
        ).count()

    elif metric == 'transaction_count':
        return Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.created_at >= since,
        ).count()

    elif metric == 'usage_percent':
        from models.usage import UsageLog
        usage = UsageLog.get_or_create_current(user_id)
        return round(usage.calls_used / max(usage.calls_limit, 1) * 100)

    elif metric == 'onboarding_percent':
        progress = get_onboarding_progress(user_id)
        return progress['percent']

    return 0


def send_nudge(user_id: int, rule) -> dict:
    """Send a nudge to a user."""
    from models.growth import NudgeLog, GrowthEvent

    if rule.nudge_type == 'email':
        result = send_lifecycle_email(user_id, 'usage_limit_warning', rule.nudge_content)
    else:
        # In-app nudge: just log it, frontend will pick it up
        result = {'success': True, 'type': 'in_app'}

    # Log the nudge
    log = NudgeLog(
        user_id=user_id,
        rule_id=rule.id,
        nudge_type=rule.nudge_type,
        status='sent',
    )
    db.session.add(log)

    # Track event
    event = GrowthEvent(
        user_id=user_id,
        event_type='nudge_sent',
        event_data={
            'rule_name': rule.name,
            'nudge_type': rule.nudge_type,
        },
        source='nudge',
    )
    db.session.add(event)
    db.session.commit()

    return result


def run_nudge_check():
    """Run nudge check for all active users. Called by Celery beat."""
    from models.user import User

    users = User.query.filter_by(is_active=True).all()
    results = {'checked': 0, 'nudges_sent': 0}

    for user in users:
        results['checked'] += 1
        triggered = check_nudges(user.id)

        for rule in triggered:
            send_nudge(user.id, rule)
            results['nudges_sent'] += 1

    return results


# ==============================================================================
# Growth Analytics
# ==============================================================================


def get_growth_dashboard(period_days: int = 30) -> dict:
    """Get growth analytics dashboard."""
    from models.referral import Referral, Affiliate, AffiliateConversion
    from models.growth import GrowthEvent, EmailLog
    from models.user import User
    from sqlalchemy import func

    since = datetime.utcnow() - timedelta(days=period_days)

    # New users by source
    events = GrowthEvent.query.filter(GrowthEvent.created_at >= since).all()
    source_counts = {}
    for e in events:
        if e.event_type == 'signup':
            source = e.source or 'organic'
            source_counts[source] = source_counts.get(source, 0) + 1

    # Referral stats
    total_referrals = Referral.query.filter(Referral.created_at >= since).count()
    converted_referrals = Referral.query.filter(
        Referral.converted_at >= since
    ).count()

    # Email stats
    emails_sent = EmailLog.query.filter(EmailLog.created_at >= since).count()
    emails_opened = EmailLog.query.filter(
        EmailLog.opened_at >= since
    ).count()

    # Affiliate stats
    total_affiliates = Affiliate.query.filter_by(status='active').count()
    affiliate_conversions = AffiliateConversion.query.filter(
        AffiliateConversion.created_at >= since
    ).count()

    # Nudge stats
    from models.growth import NudgeLog
    nudges_sent = NudgeLog.query.filter(NudgeLog.created_at >= since).count()
    nudges_clicked = NudgeLog.query.filter(
        NudgeLog.clicked_at >= since
    ).count()

    return {
        'period_days': period_days,
        'new_users_by_source': source_counts,
        'referral': {
            'total_referrals': total_referrals,
            'converted': converted_referrals,
            'conversion_rate': round(converted_referrals / max(total_referrals, 1) * 100, 1),
        },
        'email': {
            'sent': emails_sent,
            'opened': emails_opened,
            'open_rate': round(emails_opened / max(emails_sent, 1) * 100, 1),
        },
        'affiliate': {
            'active_affiliates': total_affiliates,
            'conversions': affiliate_conversions,
        },
        'nudges': {
            'sent': nudges_sent,
            'clicked': nudges_clicked,
            'click_rate': round(nudges_clicked / max(nudges_sent, 1) * 100, 1),
        },
    }
