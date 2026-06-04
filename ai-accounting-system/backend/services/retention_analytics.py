"""Retention Analytics — 6 dimensions of user retention intelligence.

1. Cohort Analysis    — signup-month retention curves
2. Churn Prediction   — at-risk user scoring
3. Feature Adoption   — per-feature usage penetration
4. Onboarding         — completion funnel and time-to-complete
5. Referral Conversion — referral funnel and viral coefficient
6. AI Engagement      — AI usage depth and quality score
"""

import logging
from datetime import datetime, timedelta
from collections import defaultdict

from extensions import db
from sqlalchemy import text, func

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Cohort Analysis
# ---------------------------------------------------------------------------

def get_cohort_analysis(months: int = 12) -> dict:
    """Monthly cohort retention matrix.

    Returns a grid where rows = signup month, columns = months since signup,
    values = percentage of cohort still active (logged in).
    """
    cutoff = datetime.utcnow() - timedelta(days=months * 31)

    # Get all users with signup month
    users = db.session.execute(text("""
        SELECT id, DATE_FORMAT(created_at, '%Y-%m') AS cohort_month
        FROM users
        WHERE created_at >= :cutoff
    """), {'cutoff': cutoff}).fetchall()

    if not users:
        return {'cohorts': [], 'matrix': [], 'summary': {}}

    user_map = {}
    cohort_sizes = defaultdict(int)
    for uid, cohort_month in users:
        user_map[uid] = cohort_month
        cohort_sizes[cohort_month] += 1

    # Get all logins
    user_ids = list(user_map.keys())
    if not user_ids:
        return {'cohorts': [], 'matrix': [], 'summary': {}}

    placeholders = ','.join([':p' + str(i) for i in range(len(user_ids))])
    params = {f'p{i}': uid for i, uid in enumerate(user_ids)}

    logins = db.session.execute(text(f"""
        SELECT user_id, DATE_FORMAT(login_at, '%Y-%m') AS login_month
        FROM login_history
        WHERE user_id IN ({placeholders})
          AND success = 1
    """), params).fetchall()

    # Build activity map: user_id -> set of login months
    user_login_months = defaultdict(set)
    for uid, login_month in logins:
        user_login_months[uid].add(login_month)

    # Build cohort matrix
    all_cohorts = sorted(cohort_sizes.keys())
    max_offset = months

    matrix = []
    for cohort in all_cohorts:
        row = {'cohort': cohort, 'size': cohort_sizes[cohort], 'retention': []}
        cohort_year, cohort_mon = map(int, cohort.split('-'))

        for offset in range(max_offset):
            # Calculate the target month
            target_year = cohort_year + (cohort_mon - 1 + offset) // 12
            target_month = (cohort_mon - 1 + offset) % 12 + 1
            target = f"{target_year:04d}-{target_month:02d}"

            # Count users in this cohort who were active in target month
            active_count = sum(
                1 for uid, cm in user_map.items()
                if cm == cohort and target in user_login_months.get(uid, set())
            )
            pct = round(active_count / cohort_sizes[cohort] * 100, 1) if cohort_sizes[cohort] > 0 else 0
            row['retention'].append({
                'month': offset,
                'active': active_count,
                'pct': pct,
            })

        matrix.append(row)

    # Summary stats
    if matrix:
        latest = matrix[-1]
        month1_retention = latest['retention'][1]['pct'] if len(latest['retention']) > 1 else 0
        month3_retention = latest['retention'][3]['pct'] if len(latest['retention']) > 3 else 0
    else:
        month1_retention = month3_retention = 0

    return {
        'cohorts': all_cohorts,
        'matrix': matrix,
        'summary': {
            'total_users': len(user_map),
            'total_cohorts': len(all_cohorts),
            'latest_month1_retention_pct': month1_retention,
            'latest_month3_retention_pct': month3_retention,
        },
    }


# ---------------------------------------------------------------------------
# 2. Churn Prediction
# ---------------------------------------------------------------------------

def get_churn_prediction(limit: int = 50) -> dict:
    """Score users by churn risk based on activity decline signals.

    Signals:
    - Days since last login (higher = more risk)
    - Login frequency decline (recent vs prior period)
    - Transaction activity decline
    - AI usage decline
    - Subscription status
    """
    now = datetime.utcnow()

    # Get users with recent activity signals
    users = db.session.execute(text("""
        SELECT
            u.id,
            u.email,
            u.created_at,
            u.is_active,
            COALESCE(s.status, 'none') AS sub_status,
            MAX(lh.login_at) AS last_login,
            COUNT(DISTINCT CASE WHEN lh.login_at >= :thirty_days_ago THEN lh.id END) AS logins_30d,
            COUNT(DISTINCT CASE WHEN lh.login_at >= :sixty_days_ago AND lh.login_at < :thirty_days_ago THEN lh.id END) AS logins_30_60d
        FROM users u
        LEFT JOIN subscriptions s ON s.user_id = u.id
        LEFT JOIN login_history lh ON lh.user_id = u.id AND lh.success = 1
        WHERE u.is_active = 1
        GROUP BY u.id, u.email, u.created_at, u.is_active, s.status
        ORDER BY last_login DESC
        LIMIT :limit
    """), {
        'thirty_days_ago': now - timedelta(days=30),
        'sixty_days_ago': now - timedelta(days=60),
        'limit': limit * 5,  # get more, then score and re-limit
    }).fetchall()

    # Get transaction counts
    user_ids = [u[0] for u in users]
    if not user_ids:
        return {'users': [], 'summary': {}}

    placeholders = ','.join([':tx' + str(i) for i in range(len(user_ids))])
    tx_params = {f'tx{i}': uid for i, uid in enumerate(user_ids)}

    tx_counts = db.session.execute(text(f"""
        SELECT user_id,
            COUNT(CASE WHEN created_at >= :thirty_days_ago THEN 1 END) AS tx_30d,
            COUNT(CASE WHEN created_at >= :sixty_days_ago AND created_at < :thirty_days_ago THEN 1 END) AS tx_30_60d
        FROM transactions
        WHERE user_id IN ({placeholders})
        GROUP BY user_id
    """), {**tx_params, 'thirty_days_ago': now - timedelta(days=30), 'sixty_days_ago': now - timedelta(days=60)}).fetchall()

    tx_map = {r[0]: (r[1], r[2]) for r in tx_counts}

    # Get AI usage counts
    ai_counts = db.session.execute(text(f"""
        SELECT user_id,
            COUNT(CASE WHEN created_at >= :thirty_days_ago THEN 1 END) AS ai_30d,
            COUNT(CASE WHEN created_at >= :sixty_days_ago AND created_at < :thirty_days_ago THEN 1 END) AS ai_30_60d
        FROM agent_execution_logs
        WHERE user_id IN ({placeholders})
        GROUP BY user_id
    """), {**tx_params, 'thirty_days_ago': now - timedelta(days=30), 'sixty_days_ago': now - timedelta(days=60)}).fetchall()

    ai_map = {r[0]: (r[1], r[2]) for r in ai_counts}

    # Score each user
    scored = []
    for row in users:
        uid, email, created_at, is_active, sub_status, last_login, logins_30d, logins_30_60d = row

        # Days since last login
        if last_login:
            days_since_login = (now - last_login).days
        else:
            days_since_login = (now - created_at).days if created_at else 999

        # Login frequency change
        login_change = 0
        if logins_30_60d > 0:
            login_change = (logins_30d - logins_30_60d) / logins_30_60d
        elif logins_30d > 0:
            login_change = 1.0  # new activity

        # Transaction change
        tx_30d, tx_30_60d = tx_map.get(uid, (0, 0))
        tx_change = 0
        if tx_30_60d > 0:
            tx_change = (tx_30d - tx_30_60d) / tx_30_60d

        # AI usage change
        ai_30d, ai_30_60d = ai_map.get(uid, (0, 0))
        ai_change = 0
        if ai_30_60d > 0:
            ai_change = (ai_30d - ai_30_60d) / ai_30_60d

        # Churn risk score (0-100, higher = more risk)
        risk_score = 0

        # Days since login (0-40 points)
        if days_since_login > 30:
            risk_score += 40
        elif days_since_login > 14:
            risk_score += 25
        elif days_since_login > 7:
            risk_score += 10

        # Login decline (0-25 points)
        if logins_30d == 0 and logins_30_60d > 0:
            risk_score += 25
        elif login_change < -0.5:
            risk_score += 20
        elif login_change < -0.2:
            risk_score += 10

        # Transaction decline (0-20 points)
        if tx_30d == 0 and tx_30_60d > 0:
            risk_score += 20
        elif tx_change < -0.5:
            risk_score += 15
        elif tx_change < -0.2:
            risk_score += 5

        # AI decline (0-15 points)
        if ai_30d == 0 and ai_30_60d > 0:
            risk_score += 15
        elif ai_change < -0.5:
            risk_score += 10

        # Subscription status bonus
        if sub_status in ('cancelled', 'expired', 'past_due'):
            risk_score += 20
        elif sub_status == 'none':
            risk_score += 5

        risk_score = min(100, risk_score)

        # Risk level
        if risk_score >= 70:
            risk_level = 'critical'
        elif risk_score >= 50:
            risk_level = 'high'
        elif risk_score >= 30:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        scored.append({
            'user_id': uid,
            'email': email,
            'days_since_login': days_since_login,
            'logins_30d': logins_30d,
            'logins_prev_30d': logins_30_60d,
            'login_change_pct': round(login_change * 100, 1),
            'transactions_30d': tx_30d,
            'transactions_prev_30d': tx_30_60d,
            'ai_calls_30d': ai_30d,
            'ai_calls_prev_30d': ai_30_60d,
            'subscription_status': sub_status,
            'risk_score': risk_score,
            'risk_level': risk_level,
        })

    # Sort by risk and limit
    scored.sort(key=lambda x: x['risk_score'], reverse=True)
    scored = scored[:limit]

    # Summary
    risk_counts = defaultdict(int)
    for u in scored:
        risk_counts[u['risk_level']] += 1

    return {
        'users': scored,
        'summary': {
            'total_scored': len(scored),
            'critical': risk_counts.get('critical', 0),
            'high': risk_counts.get('high', 0),
            'medium': risk_counts.get('medium', 0),
            'low': risk_counts.get('low', 0),
            'avg_risk_score': round(sum(u['risk_score'] for u in scored) / len(scored), 1) if scored else 0,
        },
    }


# ---------------------------------------------------------------------------
# 3. Feature Adoption
# ---------------------------------------------------------------------------

def get_feature_adoption(days: int = 30) -> dict:
    """Measure adoption rate of key features across active users."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Total active users
    active_users = db.session.execute(text("""
        SELECT COUNT(DISTINCT user_id) FROM login_history
        WHERE login_at >= :cutoff AND success = 1
    """), {'cutoff': cutoff}).scalar() or 0

    if active_users == 0:
        return {'features': [], 'summary': {'active_users': 0}}

    features = []

    # 1. Transaction creation
    tx_users = db.session.execute(text("""
        SELECT COUNT(DISTINCT user_id) FROM transactions WHERE created_at >= :cutoff
    """), {'cutoff': cutoff}).scalar() or 0
    features.append({
        'feature': 'transaction_create',
        'name': '记账',
        'users': tx_users,
        'adoption_pct': round(tx_users / active_users * 100, 1),
    })

    # 2. AI-assisted transactions
    ai_tx_users = db.session.execute(text("""
        SELECT COUNT(DISTINCT user_id) FROM transactions
        WHERE created_at >= :cutoff AND ai_generated = 1
    """), {'cutoff': cutoff}).scalar() or 0
    features.append({
        'feature': 'ai_bookkeeping',
        'name': 'AI 记账',
        'users': ai_tx_users,
        'adoption_pct': round(ai_tx_users / active_users * 100, 1),
    })

    # 3. OCR/Receipt scanning
    ocr_users = db.session.execute(text("""
        SELECT COUNT(DISTINCT user_id) FROM transactions
        WHERE created_at >= :cutoff AND (receipt_image IS NOT NULL OR ocr_text IS NOT NULL)
    """), {'cutoff': cutoff}).scalar() or 0
    features.append({
        'feature': 'receipt_ocr',
        'name': '票据识别',
        'users': ocr_users,
        'adoption_pct': round(ocr_users / active_users * 100, 1),
    })

    # 4. AI chat/agent usage
    ai_agent_users = db.session.execute(text("""
        SELECT COUNT(DISTINCT user_id) FROM agent_execution_logs
        WHERE created_at >= :cutoff AND success = 1
    """), {'cutoff': cutoff}).scalar() or 0
    features.append({
        'feature': 'ai_agent',
        'name': 'AI 助手',
        'users': ai_agent_users,
        'adoption_pct': round(ai_agent_users / active_users * 100, 1),
    })

    # 5. Report generation
    report_users = db.session.execute(text("""
        SELECT COUNT(DISTINCT user_id) FROM task_records
        WHERE created_at >= :cutoff AND task_type = 'report' AND status = 'success'
    """), {'cutoff': cutoff}).scalar() or 0
    features.append({
        'feature': 'reports',
        'name': '报表生成',
        'users': report_users,
        'adoption_pct': round(report_users / active_users * 100, 1),
    })

    # 6. Export usage (check via task_records)
    export_users = db.session.execute(text("""
        SELECT COUNT(DISTINCT user_id) FROM task_records
        WHERE created_at >= :cutoff AND task_type = 'export' AND status = 'success'
    """), {'cutoff': cutoff}).scalar() or 0
    features.append({
        'feature': 'export',
        'name': '数据导出',
        'users': export_users,
        'adoption_pct': round(export_users / active_users * 100, 1),
    })

    # 7. Onboarding completion
    onboarded_users = db.session.execute(text("""
        SELECT COUNT(DISTINCT user_id) FROM onboarding_steps
        WHERE status = 'completed'
    """)).scalar() or 0
    features.append({
        'feature': 'onboarding',
        'name': '引导完成',
        'users': onboarded_users,
        'adoption_pct': round(onboarded_users / active_users * 100, 1) if active_users > 0 else 0,
    })

    # Sort by adoption
    features.sort(key=lambda x: x['adoption_pct'], reverse=True)

    return {
        'features': features,
        'summary': {
            'active_users': active_users,
            'period_days': days,
            'avg_adoption_pct': round(sum(f['adoption_pct'] for f in features) / len(features), 1) if features else 0,
            'most_adopted': features[0]['name'] if features else None,
            'least_adopted': features[-1]['name'] if features else None,
        },
    }


# ---------------------------------------------------------------------------
# 4. Onboarding Completion
# ---------------------------------------------------------------------------

def get_onboarding_analytics() -> dict:
    """Onboarding funnel analysis: step-by-step completion rates and timing."""
    # Step completion rates
    steps = db.session.execute(text("""
        SELECT
            step_key,
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) AS skipped,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
            AVG(CASE WHEN status = 'completed' AND completed_at IS NOT NULL
                THEN TIMESTAMPDIFF(HOUR, created_at, completed_at) END) AS avg_hours_to_complete
        FROM onboarding_steps
        GROUP BY step_key
        ORDER BY MIN(id)
    """)).fetchall()

    funnel = []
    for row in steps:
        step_key, total, completed, skipped, pending, avg_hours = row
        funnel.append({
            'step': step_key,
            'total': total,
            'completed': completed,
            'skipped': skipped,
            'pending': pending,
            'completion_rate_pct': round(completed / total * 100, 1) if total > 0 else 0,
            'skip_rate_pct': round(skipped / total * 100, 1) if total > 0 else 0,
            'avg_hours_to_complete': round(float(avg_hours), 1) if avg_hours else None,
        })

    # Overall completion stats
    total_users_with_onboarding = db.session.execute(text("""
        SELECT COUNT(DISTINCT user_id) FROM onboarding_steps
    """)).scalar() or 0

    fully_completed = db.session.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT user_id
            FROM onboarding_steps
            WHERE step_key NOT IN (SELECT step_key FROM onboarding_steps WHERE step_key = 'invite_team')
            GROUP BY user_id
            HAVING SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) = COUNT(*)
        ) AS t
    """)).scalar() or 0

    # Users who completed at least the required steps (welcome + create_first)
    required_completed = db.session.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT user_id
            FROM onboarding_steps
            WHERE step_key IN ('welcome', 'create_first')
            GROUP BY user_id
            HAVING SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) = 2
        ) AS t
    """)).scalar() or 0

    return {
        'funnel': funnel,
        'summary': {
            'total_users_with_onboarding': total_users_with_onboarding,
            'fully_completed': fully_completed,
            'full_completion_rate_pct': round(fully_completed / total_users_with_onboarding * 100, 1) if total_users_with_onboarding > 0 else 0,
            'required_completed': required_completed,
            'required_completion_rate_pct': round(required_completed / total_users_with_onboarding * 100, 1) if total_users_with_onboarding > 0 else 0,
        },
    }


# ---------------------------------------------------------------------------
# 5. Referral Conversion
# ---------------------------------------------------------------------------

def get_referral_analytics(days: int = 90) -> dict:
    """Referral funnel: code generation → signup → conversion → reward."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Referral funnel
    funnel = db.session.execute(text("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status = 'registered' THEN 1 ELSE 0 END) AS registered,
            SUM(CASE WHEN status = 'converted' THEN 1 ELSE 0 END) AS converted,
            SUM(CASE WHEN status = 'rewarded' THEN 1 ELSE 0 END) AS rewarded
        FROM referrals
        WHERE created_at >= :cutoff
    """), {'cutoff': cutoff}).fetchone()

    total, pending, registered, converted, rewarded = funnel

    # Unique referrers
    referrers = db.session.execute(text("""
        SELECT COUNT(DISTINCT referrer_id) FROM referrals WHERE created_at >= :cutoff
    """), {'cutoff': cutoff}).scalar() or 0

    # Referrals per referrer
    referrals_per_referrer = round(total / referrers, 1) if referrers > 0 else 0

    # Conversion rate
    signup_rate = round((registered + converted + rewarded) / total * 100, 1) if total > 0 else 0
    conversion_rate = round((converted + rewarded) / total * 100, 1) if total > 0 else 0

    # Viral coefficient (new users from referrals / total new users)
    new_users = db.session.execute(text("""
        SELECT COUNT(*) FROM users WHERE created_at >= :cutoff
    """), {'cutoff': cutoff}).scalar() or 0

    referred_users = registered + converted + rewarded
    viral_coefficient = round(referred_users / new_users, 3) if new_users > 0 else 0

    # Top referrers
    top_referrers = db.session.execute(text("""
        SELECT
            r.referrer_id,
            u.email,
            COUNT(*) AS total_referrals,
            SUM(CASE WHEN r.status IN ('converted', 'rewarded') THEN 1 ELSE 0 END) AS conversions
        FROM referrals r
        JOIN users u ON u.id = r.referrer_id
        WHERE r.created_at >= :cutoff
        GROUP BY r.referrer_id, u.email
        ORDER BY total_referrals DESC
        LIMIT 10
    """), {'cutoff': cutoff}).fetchall()

    # Affiliate stats
    affiliate_stats = db.session.execute(text("""
        SELECT
            COUNT(*) AS total_affiliates,
            SUM(total_clicks) AS total_clicks,
            SUM(total_conversions) AS total_conversions,
            SUM(total_revenue_cents) AS total_revenue_cents,
            SUM(total_commission_cents) AS total_commission_cents
        FROM affiliates
        WHERE status = 'active'
    """)).fetchone()

    return {
        'referral_funnel': {
            'total': total,
            'pending': pending,
            'registered': registered,
            'converted': converted,
            'rewarded': rewarded,
            'signup_rate_pct': signup_rate,
            'conversion_rate_pct': conversion_rate,
        },
        'viral': {
            'unique_referrers': referrers,
            'referrals_per_referrer': referrals_per_referrer,
            'referred_users': referred_users,
            'new_users': new_users,
            'viral_coefficient': viral_coefficient,
        },
        'top_referrers': [
            {
                'user_id': r[0],
                'email': r[1],
                'total_referrals': r[2],
                'conversions': r[3],
                'conversion_rate_pct': round(r[3] / r[2] * 100, 1) if r[2] > 0 else 0,
            }
            for r in top_referrers
        ],
        'affiliate': {
            'total_affiliates': affiliate_stats[0] or 0,
            'total_clicks': affiliate_stats[1] or 0,
            'total_conversions': affiliate_stats[2] or 0,
            'total_revenue_cents': affiliate_stats[3] or 0,
            'total_commission_cents': affiliate_stats[4] or 0,
            'conversion_rate_pct': round(
                (affiliate_stats[2] or 0) / (affiliate_stats[1] or 1) * 100, 1
            ),
        },
    }


# ---------------------------------------------------------------------------
# 6. AI Engagement Score
# ---------------------------------------------------------------------------

def get_ai_engagement(days: int = 30) -> dict:
    """AI engagement scoring: depth, breadth, quality, cost efficiency."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Per-user AI metrics
    user_metrics = db.session.execute(text("""
        SELECT
            user_id,
            COUNT(*) AS total_calls,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS success_calls,
            AVG(duration_ms) AS avg_duration_ms,
            SUM(input_tokens) AS total_input_tokens,
            SUM(output_tokens) AS total_output_tokens,
            SUM(cost_cents) AS total_cost_cents,
            COUNT(DISTINCT agent_name) AS agents_used,
            COUNT(DISTINCT DATE(created_at)) AS active_days,
            COUNT(DISTINCT model) AS models_used
        FROM agent_execution_logs
        WHERE created_at >= :cutoff AND user_id IS NOT NULL
        GROUP BY user_id
    """), {'cutoff': cutoff}).fetchall()

    if not user_metrics:
        return {'users': [], 'summary': {}}

    # Get transaction AI adoption per user
    ai_tx = db.session.execute(text("""
        SELECT user_id, COUNT(*) AS ai_tx_count
        FROM transactions
        WHERE created_at >= :cutoff AND ai_generated = 1
        GROUP BY user_id
    """), {'cutoff': cutoff}).fetchall()
    ai_tx_map = {r[0]: r[1] for r in ai_tx}

    users = []
    for row in user_metrics:
        uid, total, success, avg_dur, in_tok, out_tok, cost, agents, active_days, models = row

        success_rate = round(success / total * 100, 1) if total > 0 else 0
        avg_daily_calls = round(total / days, 1)
        ai_tx_count = ai_tx_map.get(uid, 0)

        # Engagement score (0-100)
        score = 0

        # Call volume (0-30 points)
        if total >= 100:
            score += 30
        elif total >= 50:
            score += 25
        elif total >= 20:
            score += 20
        elif total >= 5:
            score += 10
        elif total >= 1:
            score += 5

        # Frequency — active days (0-25 points)
        if active_days >= 20:
            score += 25
        elif active_days >= 10:
            score += 20
        elif active_days >= 5:
            score += 15
        elif active_days >= 2:
            score += 8

        # Agent breadth (0-20 points)
        if agents >= 5:
            score += 20
        elif agents >= 3:
            score += 15
        elif agents >= 2:
            score += 10
        elif agents >= 1:
            score += 5

        # Success rate (0-15 points)
        if success_rate >= 95:
            score += 15
        elif success_rate >= 85:
            score += 10
        elif success_rate >= 70:
            score += 5

        # AI transaction output (0-10 points)
        if ai_tx_count >= 20:
            score += 10
        elif ai_tx_count >= 5:
            score += 7
        elif ai_tx_count >= 1:
            score += 3

        # Engagement level
        if score >= 80:
            level = 'power_user'
        elif score >= 60:
            level = 'engaged'
        elif score >= 40:
            level = 'active'
        elif score >= 20:
            level = 'casual'
        else:
            level = 'dormant'

        users.append({
            'user_id': uid,
            'total_calls': total,
            'success_rate_pct': success_rate,
            'avg_duration_ms': round(float(avg_dur or 0), 0),
            'total_input_tokens': in_tok or 0,
            'total_output_tokens': out_tok or 0,
            'total_cost_cents': round(float(cost or 0), 4),
            'agents_used': agents,
            'active_days': active_days,
            'avg_daily_calls': avg_daily_calls,
            'ai_transactions': ai_tx_count,
            'engagement_score': score,
            'engagement_level': level,
        })

    users.sort(key=lambda x: x['engagement_score'], reverse=True)

    # Summary
    level_counts = defaultdict(int)
    for u in users:
        level_counts[u['engagement_level']] += 1

    total_calls = sum(u['total_calls'] for u in users)
    total_cost = sum(u['total_cost_cents'] for u in users)

    return {
        'users': users[:50],  # Top 50
        'summary': {
            'total_ai_users': len(users),
            'total_calls': total_calls,
            'total_cost_cents': round(total_cost, 4),
            'avg_calls_per_user': round(total_calls / len(users), 1) if users else 0,
            'avg_engagement_score': round(sum(u['engagement_score'] for u in users) / len(users), 1) if users else 0,
            'power_users': level_counts.get('power_user', 0),
            'engaged': level_counts.get('engaged', 0),
            'active': level_counts.get('active', 0),
            'casual': level_counts.get('casual', 0),
            'dormant': level_counts.get('dormant', 0),
        },
        'period_days': days,
    }


# ---------------------------------------------------------------------------
# Unified Dashboard
# ---------------------------------------------------------------------------

def get_retention_dashboard(days: int = 30) -> dict:
    """Unified retention analytics dashboard."""
    return {
        'cohort': get_cohort_analysis(months=6),
        'churn': get_churn_prediction(limit=20),
        'feature_adoption': get_feature_adoption(days=days),
        'onboarding': get_onboarding_analytics(),
        'referral': get_referral_analytics(days=days),
        'ai_engagement': get_ai_engagement(days=days),
        'generated_at': datetime.utcnow().isoformat(),
        'period_days': days,
    }
