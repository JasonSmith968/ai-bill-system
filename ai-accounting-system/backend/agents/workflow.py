"""Workflow Engine — declarative multi-step agent pipelines.

Supports sequential execution, conditional steps, retry, and SSE streaming.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from agents.base import AgentContext, AgentResult

logger = logging.getLogger(__name__)

_engine = None


def get_workflow_engine():
    """Get or create the singleton WorkflowEngine."""
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
        _register_built_in_workflows(_engine)
    return _engine


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    name: str
    agent_name: str
    task: str
    input_keys: list = field(default_factory=list)
    output_keys: list = field(default_factory=list)
    condition: Optional[Callable] = None  # fn(context) -> bool
    retry: int = 0
    on_error: str = 'stop'  # 'stop' | 'skip' | 'fallback'
    fallback_agent: Optional[str] = None


@dataclass
class Workflow:
    """A named workflow composed of steps."""
    name: str
    description: str
    steps: list


class WorkflowEngine:
    """Executes declarative workflows by dispatching to AgentManager."""

    def __init__(self):
        self._workflows: dict[str, Workflow] = {}

    def register(self, workflow: Workflow):
        """Register a workflow."""
        self._workflows[workflow.name] = workflow
        logger.debug(f"Registered workflow: {workflow.name}")

    def get(self, name: str) -> Optional[Workflow]:
        return self._workflows.get(name)

    def list_workflows(self) -> list[dict]:
        return [
            {'name': w.name, 'description': w.description, 'steps': len(w.steps)}
            for w in self._workflows.values()
        ]

    def execute(self, workflow_name: str, context: AgentContext, **kwargs):
        """Execute a workflow, yielding step events for SSE streaming.

        Yields:
            dict: {'type': 'step_start'|'step_end'|'workflow_end'|'error', ...}
        """
        workflow = self._workflows.get(workflow_name)
        if not workflow:
            yield {'type': 'error', 'message': f'Workflow not found: {workflow_name}'}
            return

        from agents.manager import get_manager
        manager = get_manager()

        yield {'type': 'workflow_start', 'workflow': workflow_name, 'steps': len(workflow.steps)}

        for i, step in enumerate(workflow.steps):
            # Check condition
            if step.condition and not step.condition(context):
                yield {
                    'type': 'step_skipped',
                    'step': step.name,
                    'agent': step.agent_name,
                    'reason': 'condition not met'
                }
                continue

            yield {
                'type': 'step_start',
                'step': step.name,
                'agent': step.agent_name,
                'task': step.task,
                'index': i,
            }

            # Execute with retry
            result = None
            last_error = ''
            for attempt in range(step.retry + 1):
                start = time.time()
                try:
                    result = manager.run(step.agent_name, context, task=step.task, **kwargs)
                    duration = (time.time() - start) * 1000
                    context.add_workflow_step(step.name, step.agent_name, 'success' if result.success else 'failed', duration)

                    if result.success:
                        # Store output keys in context
                        for key in step.output_keys:
                            if key in result.data:
                                context.set(key, result.data[key], step.agent_name)
                        break
                    else:
                        last_error = result.error
                except Exception as e:
                    duration = (time.time() - start) * 1000
                    context.add_workflow_step(step.name, step.agent_name, 'error', duration)
                    last_error = str(e)
                    logger.error(f"Workflow step '{step.name}' error (attempt {attempt+1}): {e}")

                if attempt < step.retry:
                    time.sleep(0.5 * (attempt + 1))

            # Handle failure
            if result is None or not result.success:
                if step.on_error == 'skip':
                    yield {
                        'type': 'step_end',
                        'step': step.name,
                        'status': 'skipped',
                        'error': last_error,
                    }
                    continue
                elif step.on_error == 'fallback' and step.fallback_agent:
                    yield {
                        'type': 'step_fallback',
                        'step': step.name,
                        'fallback_agent': step.fallback_agent,
                    }
                    try:
                        start = time.time()
                        result = manager.run(step.fallback_agent, context, task=step.task, **kwargs)
                        duration = (time.time() - start) * 1000
                        context.add_workflow_step(step.name, step.fallback_agent, 'fallback', duration)
                    except Exception as e:
                        yield {'type': 'error', 'step': step.name, 'message': str(e)}
                        return
                else:
                    yield {'type': 'error', 'step': step.name, 'message': last_error}
                    return

            yield {
                'type': 'step_end',
                'step': step.name,
                'agent': step.agent_name,
                'status': 'success' if result and result.success else 'failed',
                'duration_ms': result.duration_ms if result else 0,
                'data_keys': list(result.data.keys()) if result and result.data else [],
            }

        yield {'type': 'workflow_end', 'workflow': workflow_name}

    def execute_sync(self, workflow_name: str, context: AgentContext, **kwargs) -> AgentResult:
        """Execute workflow synchronously, returning the final result."""
        last_result = None
        for event in self.execute(workflow_name, context, **kwargs):
            if event['type'] == 'error':
                return AgentResult(success=False, error=event.get('message', ''))
            if event['type'] == 'step_end' and event.get('status') == 'success':
                last_result = event
        if last_result:
            return AgentResult(
                success=True,
                data={'last_step': last_result.get('step'), 'workflow': workflow_name},
                agent_name='workflow_engine'
            )
        return AgentResult(success=False, error='Workflow produced no results', agent_name='workflow_engine')


# ============================================================
# Built-in Workflows
# ============================================================

def _register_built_in_workflows(engine):
    """Register default workflows."""

    engine.register(Workflow(
        name='receipt_pipeline',
        description='收据识别 → 交易解析',
        steps=[
            WorkflowStep(
                name='ocr_extract', agent_name='ocr', task='process_receipt',
                output_keys=['ocr_text', 'receipt_info'],
            ),
            WorkflowStep(
                name='parse_transaction', agent_name='finance', task='parse',
                input_keys=['ocr_text', 'receipt_info'],
                output_keys=['parsed_transaction'],
            ),
        ]
    ))

    engine.register(Workflow(
        name='full_analysis',
        description='风险检测 → 预算建议',
        steps=[
            WorkflowStep(
                name='risk_scan', agent_name='risk', task='full_scan',
                output_keys=['risk_data'],
            ),
            WorkflowStep(
                name='budget_recommend', agent_name='recommendation', task='recommend',
                input_keys=['risk_data'],
                output_keys=['recommendations'],
            ),
        ]
    ))

    engine.register(Workflow(
        name='tax_planning',
        description='消费分析 → 税务建议 → 综合建议',
        steps=[
            WorkflowStep(
                name='spending_analysis', agent_name='finance', task='analyze',
                output_keys=['analysis_data'],
            ),
            WorkflowStep(
                name='tax_consult', agent_name='tax', task='consult',
                input_keys=['analysis_data'],
                output_keys=['tax_advice'],
            ),
            WorkflowStep(
                name='final_recommend', agent_name='recommendation', task='recommend',
                input_keys=['analysis_data', 'tax_advice'],
                output_keys=['recommendations'],
                on_error='skip',
            ),
        ]
    ))

    engine.register(Workflow(
        name='investment_review',
        description='消费分析 → 投资建议 → 报告生成',
        steps=[
            WorkflowStep(
                name='spending_analysis', agent_name='finance', task='analyze',
                output_keys=['analysis_data'],
            ),
            WorkflowStep(
                name='investment_analysis', agent_name='investment', task='analysis',
                input_keys=['analysis_data'],
                output_keys=['investment_advice'],
            ),
            WorkflowStep(
                name='report_generate', agent_name='report', task='generate',
                input_keys=['analysis_data', 'investment_advice'],
                output_keys=['report'],
                on_error='skip',
            ),
        ]
    ))
