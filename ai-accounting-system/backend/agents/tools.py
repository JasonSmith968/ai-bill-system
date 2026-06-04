"""Tool Registry — standardized tool definitions and execution for agents.

Provides OpenAI function calling format compatibility.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_registry = None


def get_tool_registry():
    """Get or create the singleton ToolRegistry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_built_in_tools(_registry)
    return _registry


@dataclass
class ToolDefinition:
    """Defines a callable tool for agents."""
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable
    required_permission: Optional[str] = None
    agent_whitelist: Optional[list] = None  # If set, only these agents can use this tool

    def to_openai_format(self):
        """Convert to OpenAI function calling format."""
        return {
            'type': 'function',
            'function': {
                'name': self.name,
                'description': self.description,
                'parameters': self.parameters,
            }
        }


class ToolRegistry:
    """Central registry for agent tools."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition):
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self, agent_name=None) -> list[dict]:
        """List available tools, optionally filtered by agent."""
        tools = []
        for t in self._tools.values():
            if agent_name and t.agent_whitelist and agent_name not in t.agent_whitelist:
                continue
            tools.append({
                'name': t.name,
                'description': t.description,
                'parameters': t.parameters,
                'required_permission': t.required_permission,
            })
        return tools

    def execute(self, name: str, **kwargs) -> dict:
        """Execute a tool by name with given parameters."""
        tool = self._tools.get(name)
        if not tool:
            return {'success': False, 'error': f'Tool not found: {name}'}

        start = time.time()
        try:
            result = tool.handler(**kwargs)
            duration = (time.time() - start) * 1000
            logger.info(f"Tool '{name}' executed in {duration:.0f}ms")
            return {'success': True, 'data': result, 'duration_ms': round(duration, 2)}
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"Tool '{name}' failed: {e}")
            return {'success': False, 'error': str(e), 'duration_ms': round(duration, 2)}

    def to_openai_tools(self, agent_name=None) -> list[dict]:
        """Export tools as OpenAI function calling format."""
        tools = []
        for t in self._tools.values():
            if agent_name and t.agent_whitelist and agent_name not in t.agent_whitelist:
                continue
            tools.append(t.to_openai_format())
        return tools


# ============================================================
# Built-in Tool Handlers
# ============================================================

def _ocr_extract(**kwargs):
    """Extract text from an image using OCR."""
    image_path = kwargs.get('image_path', '')
    if not image_path:
        return {'error': 'image_path required'}
    from services.ocr_service import OCRService
    text = OCRService.extract_text(image_path)
    return {'text': text}


def _data_query(**kwargs):
    """Query transaction data with filters."""
    from datetime import date, timedelta
    from sqlalchemy import func
    from extensions import db
    from models.transaction import Transaction, Category

    user_id = kwargs.get('user_id')
    period_months = kwargs.get('period_months', 3)
    today = date.today()
    start = today - timedelta(days=30 * period_months)

    total = float(db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id, Transaction.type == 'expense',
        Transaction.date >= start
    ).scalar() or 0)

    count = Transaction.query.filter(
        Transaction.user_id == user_id, Transaction.type == 'expense',
        Transaction.date >= start
    ).count()

    return {
        'total_expense': round(total, 2),
        'transaction_count': count,
        'period_months': period_months,
        'monthly_avg': round(total / max(period_months, 1), 2),
    }


def _spending_analysis(**kwargs):
    """Run spending analysis for a user."""
    user_id = kwargs.get('user_id')
    period_months = kwargs.get('period_months', 3)
    from services.agent_service import run_full_analysis
    return run_full_analysis(user_id, period_months)


def _budget_compute(**kwargs):
    """Compute budget allocation for a user."""
    user_id = kwargs.get('user_id')
    months = kwargs.get('months', 3)
    from services.agent_service import compute_budget_allocation
    return compute_budget_allocation(user_id, months)


def _chart_generate(**kwargs):
    """Generate a chart (placeholder — returns chart config for frontend rendering)."""
    chart_type = kwargs.get('chart_type', 'bar')
    data = kwargs.get('data', {})
    title = kwargs.get('title', '')
    return {
        'chart_type': chart_type,
        'data': data,
        'title': title,
        'render_at': 'frontend',
    }


def _report_export(**kwargs):
    """Export a report (placeholder — returns export config)."""
    report_type = kwargs.get('report_type', 'pdf')
    data = kwargs.get('data', {})
    return {
        'report_type': report_type,
        'data_keys': list(data.keys()) if isinstance(data, dict) else [],
        'status': 'ready',
    }


def _register_built_in_tools(registry):
    """Register all built-in tools."""
    registry.register(ToolDefinition(
        name='ocr_extract',
        description='从图片中提取文字，支持收据、发票等',
        parameters={
            'type': 'object',
            'properties': {
                'image_path': {'type': 'string', 'description': '图片文件路径'}
            },
            'required': ['image_path']
        },
        handler=_ocr_extract,
        required_permission='ai:call',
    ))

    registry.register(ToolDefinition(
        name='data_query',
        description='查询用户交易数据的统计摘要',
        parameters={
            'type': 'object',
            'properties': {
                'user_id': {'type': 'integer', 'description': '用户ID'},
                'period_months': {'type': 'integer', 'description': '分析周期（月）', 'default': 3}
            },
            'required': ['user_id']
        },
        handler=_data_query,
    ))

    registry.register(ToolDefinition(
        name='spending_analysis',
        description='执行完整的消费分析（规则引擎+LLM）',
        parameters={
            'type': 'object',
            'properties': {
                'user_id': {'type': 'integer', 'description': '用户ID'},
                'period_months': {'type': 'integer', 'description': '分析周期（月）', 'default': 3}
            },
            'required': ['user_id']
        },
        handler=_spending_analysis,
        required_permission='ai:call',
    ))

    registry.register(ToolDefinition(
        name='budget_compute',
        description='计算预算分配建议',
        parameters={
            'type': 'object',
            'properties': {
                'user_id': {'type': 'integer', 'description': '用户ID'},
                'months': {'type': 'integer', 'description': '参考周期（月）', 'default': 3}
            },
            'required': ['user_id']
        },
        handler=_budget_compute,
    ))

    registry.register(ToolDefinition(
        name='chart_generate',
        description='生成图表配置（前端渲染）',
        parameters={
            'type': 'object',
            'properties': {
                'chart_type': {'type': 'string', 'enum': ['bar', 'line', 'pie', 'area'], 'description': '图表类型'},
                'data': {'type': 'object', 'description': '图表数据'},
                'title': {'type': 'string', 'description': '图表标题'}
            },
            'required': ['chart_type', 'data']
        },
        handler=_chart_generate,
    ))

    registry.register(ToolDefinition(
        name='report_export',
        description='导出财务报告',
        parameters={
            'type': 'object',
            'properties': {
                'report_type': {'type': 'string', 'enum': ['pdf', 'xlsx', 'csv'], 'description': '导出格式'},
                'data': {'type': 'object', 'description': '报告数据'}
            },
            'required': ['report_type']
        },
        handler=_report_export,
        required_permission='report:export',
    ))
