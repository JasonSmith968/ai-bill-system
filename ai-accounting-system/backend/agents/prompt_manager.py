"""Prompt Manager — template-based prompt system with context compression.

Manages system prompts for each agent, with DB-backed templates and built-in defaults.
Delegates to PromptRegistry for versioned storage and ContextCompressor for compression.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_manager = None


def get_prompt_manager():
    """Get or create the singleton PromptManager."""
    global _manager
    if _manager is None:
        _manager = PromptManager()
    return _manager


# Built-in default system prompts per agent
DEFAULT_SYSTEM_PROMPTS = {
    'finance': (
        '你是AI财务助手，擅长分析消费模式、识别支出趋势、提供建议。'
        '用中文回答，使用Markdown格式。专业、简洁、有洞察力。'
    ),
    'risk': (
        '你是风险检测Agent，专注于发现异常消费、订阅浪费、高频消费模式。'
        '用中文回答，重点关注风险点和可操作的建议。'
    ),
    'recommendation': (
        '你是财务建议Agent，根据用户的消费数据提供预算优化和理财建议。'
        '用中文回答，建议要具体、可执行、有针对性。'
    ),
    'tax': (
        '你是税务顾问Agent，了解中国个人所得税政策，帮助用户合理节税。'
        '用中文回答，引用相关税法条文，建议要合规合法。'
    ),
    'budget': (
        '你是预算管理Agent，帮助用户制定合理的预算计划并跟踪执行。'
        '用中文回答，预算建议基于历史数据，务实可行。'
    ),
    'investment': (
        '你是投资分析Agent，基于用户的财务状况提供投资建议和风险评估。'
        '用中文回答，注意风险提示，不做具体投资推荐。'
    ),
    'report': (
        '你是报告生成Agent，将财务数据整理成结构化的分析报告。'
        '用中文回答，报告格式清晰、数据准确、重点突出。'
    ),
    'ocr': (
        '你是OCR识别Agent，负责从收据、发票图片中提取结构化信息。'
        '输出JSON格式的结构化数据。'
    ),
}

# Default user-facing prompt templates
DEFAULT_TEMPLATES = {
    'spending_analysis': (
        '请分析以下财务数据并给出建议：\n\n'
        '{{analysis_data}}\n\n'
        '请包含：\n'
        '1. 消费模式总结\n'
        '2. 风险提醒\n'
        '3. 预算优化建议\n'
        '4. 具体行动计划'
    ),
    'tax_consult': (
        '基于以下消费数据，提供税务优化建议：\n\n'
        '{{analysis_data}}\n\n'
        '请分析可能的税前扣除项和节税方案。'
    ),
    'investment_analysis': (
        '基于以下财务状况，提供投资建议：\n\n'
        '{{analysis_data}}\n\n'
        '请评估风险承受能力并给出资产配置建议。'
    ),
    'intent_classification': (
        '你是一个意图分类器。根据用户消息，输出JSON格式的分类结果。\n'
        '可选意图: record(记账), analyze(分析), risk(风险), budget(预算), '
        'tax(税务), investment(投资), report(报告), ocr(OCR识别), chat(闲聊)\n'
        '输出格式: {"intent": "xxx", "confidence": 0.0-1.0, "reason": "简短说明"}\n'
        '只输出JSON，不要其他内容。'
    ),
}


class PromptManager:
    """Manages prompt templates with DB-backed storage and built-in defaults.

    Delegates to:
    - PromptRegistry for versioned prompt storage, A/B testing, rollback
    - ContextCompressor for intelligent context compression
    """

    def load(self, template_name: str, **variables) -> str:
        """Load and render a template by name.

        Tries PromptRegistry (DB), falls back to built-in defaults.
        """
        from agents.prompt_registry import get_prompt_registry
        registry = get_prompt_registry()

        template = registry.get_prompt(template_name)
        if template and variables:
            for key, value in variables.items():
                template = template.replace('{{' + key + '}}', str(value))
        return template or ''

    def get_system_prompt(self, agent_name: str) -> str:
        """Get the system prompt for an agent.

        Delegates to PromptRegistry with built-in fallback.
        """
        from agents.prompt_registry import get_prompt_registry
        return get_prompt_registry().get_system_prompt(agent_name)

    def build_messages(self, system_key: str, user_content: str,
                       context_data: Optional[dict] = None) -> list:
        """Build a messages list for LLM chat.

        Args:
            system_key: Agent name or system prompt key
            user_content: User message content
            context_data: Optional context to inject into system prompt

        Returns:
            List of message dicts [{role, content}, ...]
        """
        system = self.get_system_prompt(system_key)

        if context_data:
            context_str = '\n'.join(f'- {k}: {v}' for k, v in context_data.items() if v)
            if context_str:
                system += f'\n\n## 上下文信息\n{context_str}'

        messages = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user_content},
        ]
        return messages

    def compress_context(self, messages: list, max_tokens: int = 3000) -> list:
        """Compress message history to fit within token limits.

        Delegates to ContextCompressor with hybrid strategy.
        """
        from agents.context_compressor import get_compressor
        return get_compressor().compress(messages, max_tokens=max_tokens, strategy='hybrid')
