"""Budget Agent — Budget planning, progress tracking, overspend alerts."""

import time
import logging
from datetime import date, timedelta
from sqlalchemy import func
from agents.base import BaseAgent, AgentResult
from extensions import db
from models.transaction import Transaction, Category

logger = logging.getLogger(__name__)


class BudgetAgent(BaseAgent):
    """Agent for budget management and tracking."""

    @property
    def name(self):
        return 'budget'

    @property
    def description(self):
        return 'Budget planning, execution tracking, and overspend alerts'

    @property
    def capabilities(self):
        return ['create_plan', 'track_progress', 'alert']

    def execute(self, context, **kwargs):
        start = time.time()
        task = kwargs.get('task', 'create_plan')

        try:
            if task == 'create_plan':
                return self._create_plan(context, start, **kwargs)
            elif task == 'track_progress':
                return self._track_progress(context, start, **kwargs)
            elif task == 'alert':
                return self._check_alerts(context, start, **kwargs)
            else:
                return AgentResult(success=False, error=f'Unknown task: {task}',
                                   agent_name=self.name)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_call(context, 'error', duration, [], [])
            logger.error(f"BudgetAgent failed: {e}")
            return AgentResult(success=False, error=str(e),
                               agent_name=self.name, duration_ms=duration)

    def _create_plan(self, context, start, **kwargs):
        """Create a budget plan based on historical spending."""
        from services.agent_service import compute_budget_allocation
        months = kwargs.get('months', 3)
        budget = compute_budget_allocation(context.user_id, months)

        # Learn user's budget preferences from memory
        profile = context.recall('budget_preferences', {})
        if profile:
            for b in budget:
                cat = b['category']
                if cat in profile:
                    b['suggested_budget'] = profile[cat]

        context.set('budget_plan', budget, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['budget_plan'])

        return AgentResult(
            success=True,
            data={'budget_plan': budget},
            agent_name=self.name,
            duration_ms=duration
        )

    def _track_progress(self, context, start, **kwargs):
        """Track budget execution for the current month."""
        user_id = context.user_id
        today = date.today()
        month_start = today.replace(day=1)

        # Get current month spending by category
        cat_stats = db.session.query(
            Category.name, Category.color,
            func.sum(Transaction.amount).label('spent'),
            func.count(Transaction.id).label('count')
        ).join(Transaction, Transaction.category_id == Category.id).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense',
            Transaction.date >= month_start
        ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

        budget_plan = context.get('budget_plan', [])
        budget_map = {b['category']: b for b in budget_plan}

        progress = []
        days_in_month = 30  # approximation
        day_of_month = today.day
        month_pct = day_of_month / days_in_month

        for s in cat_stats:
            cat = s.name
            spent = float(s.spent)
            budget_info = budget_map.get(cat, {})
            budget_amt = budget_info.get('suggested_budget', 0)

            entry = {
                'category': cat,
                'color': s.color,
                'spent': round(spent, 2),
                'budget': budget_amt,
                'count': s.count,
            }
            if budget_amt > 0:
                entry['percentage'] = round(spent / budget_amt * 100, 1)
                entry['on_track'] = spent <= budget_amt * month_pct * 1.2  # 20% tolerance
                entry['projected'] = round(spent / max(day_of_month, 1) * days_in_month, 2)
            progress.append(entry)

        context.set('budget_progress', progress, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['budget_progress'])

        return AgentResult(
            success=True,
            data={'budget_progress': progress, 'day_of_month': day_of_month},
            agent_name=self.name,
            duration_ms=duration
        )

    def _check_alerts(self, context, start, **kwargs):
        """Check for overspend alerts."""
        progress = context.get('budget_progress', [])
        if not progress:
            # Run progress check first
            self._track_progress(context, start, **kwargs)
            progress = context.get('budget_progress', [])

        alerts = []
        for p in progress:
            if p.get('percentage', 0) > 100:
                over = p['spent'] - p['budget']
                alerts.append({
                    'category': p['category'],
                    'severity': 'high' if p['percentage'] > 150 else 'medium',
                    'message': f"{p['category']}已超支 ¥{over:,.0f}（{p['percentage']}%）",
                    'spent': p['spent'],
                    'budget': p['budget'],
                })
            elif p.get('projected', 0) > p.get('budget', 0) * 1.1:
                alerts.append({
                    'category': p['category'],
                    'severity': 'low',
                    'message': f"{p['category']}预计月底超支（当前{p['percentage']}%）",
                    'spent': p['spent'],
                    'budget': p['budget'],
                    'projected': p['projected'],
                })

        context.set('budget_alerts', alerts, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['budget_alerts'])

        return AgentResult(
            success=True,
            data={'budget_alerts': alerts},
            agent_name=self.name,
            duration_ms=duration
        )
