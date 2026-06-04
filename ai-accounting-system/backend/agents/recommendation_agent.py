"""Recommendation Agent - Budget allocation, auto-tagging, LLM recommendations."""

import time
import logging
from agents.base import BaseAgent, AgentResult
from services.agent_service import (
    compute_budget_allocation, _categorize_tags,
    build_agent_prompt, call_llm_analysis, generate_local_explanation
)

logger = logging.getLogger(__name__)


class RecommendationAgent(BaseAgent):
    """Agent for budget recommendations and financial advice."""

    @property
    def name(self):
        return 'recommendation'

    @property
    def description(self):
        return 'Budget allocation, auto-tagging, and AI-powered recommendations'

    @property
    def capabilities(self):
        return ['compute_budget', 'auto_tag', 'generate_recommendations']

    def execute(self, context, **kwargs):
        start = time.time()
        task = kwargs.get('task', 'recommend')
        months = kwargs.get('months', 3)

        try:
            if task == 'budget':
                return self._compute_budget(context, start, months)
            elif task == 'auto_tag':
                return self._auto_tag(context, start, **kwargs)
            elif task == 'recommend':
                return self._generate_recommendations(context, start)
            else:
                return AgentResult(success=False, error=f'Unknown task: {task}',
                                   agent_name=self.name)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_call(context, 'error', duration, [], [])
            logger.error(f"RecommendationAgent failed: {e}")
            return AgentResult(success=False, error=str(e),
                               agent_name=self.name, duration_ms=duration)

    def _compute_budget(self, context, start, months):
        budget = compute_budget_allocation(context.user_id, months)
        context.set('budget_allocation', budget, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['budget_allocation'])
        return AgentResult(success=True, data={'budget_allocation': budget},
                           agent_name=self.name, duration_ms=duration)

    def _auto_tag(self, context, start, **kwargs):
        description = kwargs.get('description', '')
        note = kwargs.get('note', '')
        category = kwargs.get('category', '')
        amount = float(kwargs.get('amount', 0))

        tags = _categorize_tags(description, note, category, amount)
        context.set('auto_tags', tags, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['auto_tags'])
        return AgentResult(success=True, data={'auto_tags': tags},
                           agent_name=self.name, duration_ms=duration)

    def _generate_recommendations(self, context, start):
        input_keys = []

        # Read data produced by RiskAgent from context
        analysis_data = {
            'period_months': 3,
            'total_expense': 0,
            'monthly_avg_expense': 0,
            'total_count': 0,
            'subscriptions': context.get('subscriptions', []),
            'fixed_expenses': context.get('fixed_expenses', []),
            'anomalies': context.get('anomalies', []),
            'high_frequency': context.get('high_frequency', []),
            'budget_allocation': context.get('budget_allocation', []),
            'tag_analysis': context.get('tag_analysis', [])
        }

        if context.get('subscriptions'):
            input_keys.append('subscriptions')
        if context.get('anomalies'):
            input_keys.append('anomalies')
        if context.get('budget_allocation'):
            input_keys.append('budget_allocation')

        # Compute totals from budget data
        if analysis_data['budget_allocation']:
            total = sum(b.get('monthly_avg', 0) for b in analysis_data['budget_allocation'])
            analysis_data['total_expense'] = round(total * 3, 2)
            analysis_data['monthly_avg_expense'] = round(total, 2)

        # Try LLM first, fallback to local
        prompt = build_agent_prompt(context.user_id, analysis_data)
        content = call_llm_analysis(prompt)
        source = 'llm'

        if not content:
            content = generate_local_explanation(analysis_data)
            source = 'local'

        context.set('recommendations', content, self.name)
        context.set('recommendation_source', source, self.name)

        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, input_keys, ['recommendations'])

        return AgentResult(
            success=True,
            data={'recommendations': content, 'source': source},
            agent_name=self.name,
            duration_ms=duration
        )
