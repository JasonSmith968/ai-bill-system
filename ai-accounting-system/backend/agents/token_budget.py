"""Token budget control — per-request token and cost enforcement.

Tracks input/output tokens, estimates costs, and enforces limits
before LLM calls are made.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# DeepSeek pricing (per 1M tokens, in USD cents)
MODEL_COST = {
    'deepseek-chat': {'input': 14, 'output': 28},        # $0.14/$0.28 per 1M
    'deepseek-reasoner': {'input': 55, 'output': 219},   # $0.55/$2.19 per 1M
}


def estimate_tokens(text: str) -> int:
    """Estimate token count from text.

    Heuristic: ~2 chars per token for Chinese, ~4 for English.
    For mixed content, use chars / 2.5 as a middle ground.
    """
    if not text:
        return 0
    return max(1, int(len(text) / 2.5))


def estimate_messages_tokens(messages: list) -> int:
    """Estimate total tokens across a list of messages."""
    total = 0
    for msg in messages:
        content = msg.get('content', '')
        if isinstance(content, str):
            total += estimate_tokens(content)
        total += 4  # message overhead (role, separators)
    return total


def compute_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Compute cost in cents for a given model and token counts."""
    pricing = MODEL_COST.get(model, MODEL_COST['deepseek-chat'])
    input_cost = (input_tokens / 1_000_000) * pricing['input']
    output_cost = (output_tokens / 1_000_000) * pricing['output']
    return round(input_cost + output_cost, 4)


@dataclass
class TokenBudget:
    """Per-request token budget enforcement."""

    max_input_tokens: int = 8000
    max_output_tokens: int = 4000
    max_cost_cents: float = 100.0

    _input_tokens: int = field(default=0, init=False)
    _output_tokens: int = field(default=0, init=False)
    _cost_cents: float = field(default=0.0, init=False)
    _model: str = field(default='', init=False)

    def check_budget(self, messages: list, max_tokens: int = 0,
                     model: str = '') -> tuple[bool, str]:
        """Check if a request is within budget before sending.

        Returns:
            (allowed: bool, reason: str)
        """
        estimated_input = estimate_messages_tokens(messages)

        if estimated_input > self.max_input_tokens:
            return False, (
                f"输入 token 超限: 预估 {estimated_input} > 上限 {self.max_input_tokens}"
            )

        output_limit = max_tokens or self.max_output_tokens
        if output_limit > self.max_output_tokens:
            return False, (
                f"输出 token 超限: 请求 {output_limit} > 上限 {self.max_output_tokens}"
            )

        # Estimate total cost
        model_name = model or 'deepseek-chat'
        estimated_cost = compute_cost(estimated_input, output_limit, model_name)
        if estimated_cost > self.max_cost_cents:
            return False, (
                f"预估成本超限: {estimated_cost:.2f}¢ > 上限 {self.max_cost_cents:.2f}¢"
            )

        return True, ''

    def record_usage(self, input_tokens: int, output_tokens: int, model: str = ''):
        """Record actual token usage after an LLM call."""
        self._input_tokens += input_tokens
        self._output_tokens += output_tokens
        self._model = model or 'deepseek-chat'
        cost = compute_cost(input_tokens, output_tokens, self._model)
        self._cost_cents += cost

    def get_usage(self) -> dict:
        """Return current usage stats."""
        return {
            'input_tokens': self._input_tokens,
            'output_tokens': self._output_tokens,
            'total_tokens': self._input_tokens + self._output_tokens,
            'cost_cents': round(self._cost_cents, 4),
            'model': self._model,
        }

    def reset(self):
        """Reset usage counters (for a new request)."""
        self._input_tokens = 0
        self._output_tokens = 0
        self._cost_cents = 0.0
        self._model = ''
