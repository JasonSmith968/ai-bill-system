"""Risk Agent - Anomaly detection, subscription detection, risk scoring."""

import time
import logging
from agents.base import BaseAgent, AgentResult
from services.agent_service import (
    detect_subscriptions, detect_fixed_expenses,
    detect_anomalies, detect_high_frequency
)

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    """Agent for risk detection and anomaly analysis."""

    @property
    def name(self):
        return 'risk'

    @property
    def description(self):
        return 'Anomaly detection, subscription detection, fixed expense detection'

    @property
    def capabilities(self):
        return ['detect_subscriptions', 'detect_fixed_expenses',
                'detect_anomalies', 'detect_high_frequency']

    def execute(self, context, **kwargs):
        start = time.time()
        task = kwargs.get('task', 'full_scan')
        months = kwargs.get('months', 3)
        output_keys = []

        try:
            if task == 'full_scan':
                return self._full_scan(context, start, months)
            elif task == 'subscriptions':
                return self._detect_one(context, start, 'subscriptions',
                                        detect_subscriptions, context.user_id, months)
            elif task == 'fixed_expenses':
                return self._detect_one(context, start, 'fixed_expenses',
                                        detect_fixed_expenses, context.user_id, months)
            elif task == 'anomalies':
                return self._detect_one(context, start, 'anomalies',
                                        detect_anomalies, context.user_id, months)
            elif task == 'high_frequency':
                return self._detect_one(context, start, 'high_frequency',
                                        detect_high_frequency, context.user_id, 30)
            else:
                return AgentResult(success=False, error=f'Unknown task: {task}',
                                   agent_name=self.name)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_call(context, 'error', duration, [], [])
            logger.error(f"RiskAgent failed: {e}")
            return AgentResult(success=False, error=str(e),
                               agent_name=self.name, duration_ms=duration)

    def _full_scan(self, context, start, months):
        output_keys = []

        subscriptions = detect_subscriptions(context.user_id, months)
        context.set('subscriptions', subscriptions, self.name)
        output_keys.append('subscriptions')

        fixed_expenses = detect_fixed_expenses(context.user_id, months)
        context.set('fixed_expenses', fixed_expenses, self.name)
        output_keys.append('fixed_expenses')

        anomalies = detect_anomalies(context.user_id, months)
        context.set('anomalies', anomalies, self.name)
        output_keys.append('anomalies')

        high_frequency = detect_high_frequency(context.user_id, 30)
        context.set('high_frequency', high_frequency, self.name)
        output_keys.append('high_frequency')

        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], output_keys)

        return AgentResult(
            success=True,
            data={
                'subscriptions': subscriptions,
                'fixed_expenses': fixed_expenses,
                'anomalies': anomalies,
                'high_frequency': high_frequency
            },
            agent_name=self.name,
            duration_ms=duration
        )

    def _detect_one(self, context, start, key, func, *args):
        result = func(*args)
        context.set(key, result, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], [key])
        return AgentResult(success=True, data={key: result},
                           agent_name=self.name, duration_ms=duration)
