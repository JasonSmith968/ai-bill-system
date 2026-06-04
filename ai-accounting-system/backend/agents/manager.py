"""Agent Manager - Central orchestrator for all agents.

Integrates Router, WorkflowEngine, ToolRegistry, and PromptManager.
Maintains backward compatibility with existing pipeline methods.
"""

import time
import logging
from agents.base import AgentContext, AgentResult
from agents.logger import AgentLogger
from services import billing_service

logger = logging.getLogger(__name__)


class AgentManager:
    """Central orchestrator that coordinates all agents."""

    def __init__(self):
        self._agents = {}
        self._logger = AgentLogger()
        self._router = None
        self._workflow_engine = None
        self._tool_registry = None
        self._prompt_manager = None
        self._register_built_in_agents()

    def _register_built_in_agents(self):
        from agents.ocr_agent import OCRAgent
        from agents.finance_agent import FinanceAgent
        from agents.risk_agent import RiskAgent
        from agents.recommendation_agent import RecommendationAgent
        from agents.tax_agent import TaxAgent
        from agents.budget_agent import BudgetAgent
        from agents.investment_agent import InvestmentAgent
        from agents.report_agent import ReportAgent

        self.register(OCRAgent())
        self.register(FinanceAgent())
        self.register(RiskAgent())
        self.register(RecommendationAgent())
        self.register(TaxAgent())
        self.register(BudgetAgent())
        self.register(InvestmentAgent())
        self.register(ReportAgent())

    @property
    def router(self):
        if self._router is None:
            from agents.router import AgentRouter
            self._router = AgentRouter()
        return self._router

    @property
    def workflow_engine(self):
        if self._workflow_engine is None:
            from agents.workflow import get_workflow_engine
            self._workflow_engine = get_workflow_engine()
        return self._workflow_engine

    @property
    def tool_registry(self):
        if self._tool_registry is None:
            from agents.tools import get_tool_registry
            self._tool_registry = get_tool_registry()
        return self._tool_registry

    @property
    def prompt_manager(self):
        if self._prompt_manager is None:
            from agents.prompt_manager import get_prompt_manager
            self._prompt_manager = get_prompt_manager()
        return self._prompt_manager

    def register(self, agent):
        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")

    def get_agent(self, name):
        return self._agents.get(name)

    def list_agents(self):
        return [{
            'name': a.name,
            'description': a.description,
            'capabilities': a.capabilities
        } for a in self._agents.values()]

    def route(self, user_message, context=None):
        """Route a user message to the appropriate agent via AgentRouter."""
        return self.router.route(user_message, context)

    def execute_workflow(self, workflow_name, context, **kwargs):
        """Execute a named workflow via WorkflowEngine."""
        return self.workflow_engine.execute(workflow_name, context, **kwargs)

    def run(self, agent_name, context, **kwargs):
        """Run a single agent with timing, logging, circuit breaker, and token tracking."""
        agent = self._agents.get(agent_name)
        if not agent:
            return AgentResult(success=False, error=f'Agent "{agent_name}" not found')

        # Circuit breaker check
        from agents.circuit_breaker import get_breaker
        breaker = get_breaker(agent_name)
        if not breaker.allow_request():
            state = breaker.get_state()
            return AgentResult(
                success=False,
                error=f"Agent '{agent_name}' 暂时不可用 (熔断中)，请稍后重试",
                data={'circuit_breaker': state}
            )

        # Check AI quota for agents that call LLM
        llm_agents = ('finance', 'recommendation', 'tax', 'investment', 'report', 'budget')
        if agent_name in llm_agents:
            allowed, quota_details = billing_service.check_ai_quota(context.user_id)
            if not allowed:
                return AgentResult(
                    success=False,
                    error=quota_details.get('message', 'AI额度已用尽'),
                    data={'quota': quota_details}
                )

        start = time.time()
        try:
            result = agent.execute(context, **kwargs)
            result.agent_name = agent_name
            result.duration_ms = (time.time() - start) * 1000

            # Record success on circuit breaker
            breaker.record_success()

            # Consume AI usage with actual token count from LLM tracer
            if result.success and agent_name in llm_agents:
                tokens_used = self._extract_tokens_from_context(context)
                billing_service.consume_ai_usage(context.user_id, tokens_used=tokens_used)

            self._logger.log_execution(context, result)
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            # Record failure on circuit breaker
            breaker.record_failure()

            result = AgentResult(success=False, error=str(e),
                                 agent_name=agent_name, duration_ms=duration)
            context.add_call(agent_name, 'error', duration, [], [])
            self._logger.log_execution(context, result)
            return result

    def _extract_tokens_from_context(self, context) -> int:
        """Extract total tokens used from the agent context's call chain.

        Tries multiple sources in order:
        1. Token usage stored directly on the context
        2. LLM tracer's recent stats for this agent
        3. Token budget's usage record
        """
        # Check if token info was stored on context by the agent
        tokens = context.get('_tokens_used')
        if tokens and isinstance(tokens, (int, float)) and tokens > 0:
            return int(tokens)

        # Try tracer's recent stats
        try:
            from agents.llm_tracer import get_tracer
            tracer = get_tracer()
            last_agent = context.call_chain[-1]['agent'] if context.call_chain else ''
            if last_agent:
                stats = tracer.get_agent_stats(last_agent, period_seconds=120)
                total = stats.get('total_input_tokens', 0) + stats.get('total_output_tokens', 0)
                if total > 0:
                    return total
        except Exception:
            pass

        # Try token budget usage
        try:
            from agents.token_budget import TokenBudget
            budget = TokenBudget()
            usage = budget.get_usage()
            total = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            if total > 0:
                return total
        except Exception:
            pass

        return 0

    def get_monitor(self):
        """Return the AgentMonitor instance for dashboard access."""
        from agents.monitoring import get_monitor
        return get_monitor()

    def run_chain(self, agent_names, context, **kwargs):
        """Run agents sequentially, passing context between them. Stops on failure."""
        last_result = None
        for name in agent_names:
            last_result = self.run(name, context, **kwargs)
            if not last_result.success:
                return last_result
        return last_result

    def run_receipt_pipeline(self, context, image_path, storage_key=None):
        """Convenience: OCR -> Finance parse. Delegates to WorkflowEngine."""
        for event in self.workflow_engine.execute('receipt_pipeline', context,
                                                   image_path=image_path, storage_key=storage_key):
            pass  # Consume all events
        return {
            'context': context.to_dict(),
            'call_chain': context.call_chain,
            'ocr_text': context.get('ocr_text'),
            'receipt_info': context.get('receipt_info'),
            'parsed_transaction': context.get('parsed_transaction'),
            'category_id': context.get('category_id')
        }

    def run_full_analysis(self, context, period=3):
        """Convenience: Risk -> Recommendation. Delegates to WorkflowEngine."""
        def _run():
            for event in self.workflow_engine.execute('full_analysis', context, period=period):
                yield event

        # For backward compatibility, return dict after consuming events
        events = []
        for event in _run():
            yield_event = context.get('_yield_event')
            if yield_event:
                if event['type'] == 'step_start':
                    yield_event({'type': 'agent_start', 'agent': event.get('agent', '')})
                elif event['type'] == 'step_end':
                    yield_event({'type': 'agent_done', 'agent': event.get('agent', ''),
                                 'duration_ms': event.get('duration_ms', 0)})
            events.append(event)

        return {
            'context': context.to_dict(),
            'call_chain': context.call_chain,
            'data': {k: context.get(k) for k in context.keys()
                     if not k.startswith('_')}
        }
