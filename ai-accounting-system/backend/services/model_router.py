"""
Intelligent Model Router

Automatically selects the optimal model based on task type, with:
- Task classification (simple/OCR/reasoning/code/analysis)
- Cost-aware routing (budget enforcement)
- Latency optimization (prefer fast models when possible)
- Cache-first strategy (check cache before calling LLM)
- Auto-fallback chain (cheaper model on failure)
- Per-user budget tracking
"""

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from flask import current_app

logger = logging.getLogger(__name__)


# ==============================================================================
# Task Classification
# ==============================================================================


class TaskType(str, Enum):
    SIMPLE = "simple"          # Simple Q&A, formatting, translation
    CHAT = "chat"              # General conversation
    ANALYSIS = "analysis"      # Data analysis, summarization
    CODE = "code"              # Code generation, debugging
    OCR = "ocr"                # OCR processing
    REASONING = "reasoning"    # Complex reasoning, math, logic
    REPORT = "report"          # Report generation
    CATEGORIZE = "categorize"  # Transaction categorization
    EXTRACT = "extract"        # Data extraction from receipts


# Task classification patterns
_TASK_PATTERNS = {
    TaskType.OCR: [
        r"ocr", r"receipt", r"invoice", r"scan", r"image.*text",
        r"识别", r"发票", r"收据", r"扫描",
    ],
    TaskType.REASONING: [
        r"analyze.*why", r"explain.*reason", r"compare.*and.*contrast",
        r"calculate", r"prove", r"derive", r"逻辑", r"推理", r"分析原因",
        r"为什么", r"计算", r"证明",
    ],
    TaskType.CODE: [
        r"code", r"function", r"debug", r"error.*fix", r"implement",
        r"refactor", r"sql.*query", r"代码", r"函数", r"修复",
    ],
    TaskType.CATEGORIZE: [
        r"categorize", r"classify", r"which.*category", r"分类",
        r"归类", r"属于.*类别",
    ],
    TaskType.EXTRACT: [
        r"extract", r"parse", r"pull.*data", r"提取", r"解析",
    ],
    TaskType.REPORT: [
        r"report", r"summary", r"overview", r"报告", r"汇总",
        r"总结",
    ],
    TaskType.ANALYSIS: [
        r"trend", r"pattern", r"insight", r"统计", r"趋势",
        r"规律",
    ],
}

# Priority order for classification (first match wins)
_CLASSIFY_PRIORITY = [
    TaskType.OCR,
    TaskType.REASONING,
    TaskType.CODE,
    TaskType.CATEGORIZE,
    TaskType.EXTRACT,
    TaskType.REPORT,
    TaskType.ANALYSIS,
    TaskType.SIMPLE,
    TaskType.CHAT,
]


def classify_task(messages: list, agent_name: str = "") -> TaskType:
    """Classify task type from messages and agent name.

    Args:
        messages: List of message dicts [{role, content}, ...]
        agent_name: Name of the calling agent (e.g., 'tax', 'ocr')

    Returns:
        TaskType enum value
    """
    # Agent name hints (fast path)
    agent_lower = agent_name.lower()
    if "ocr" in agent_lower or "receipt" in agent_lower:
        return TaskType.OCR
    if "tax" in agent_lower or "invest" in agent_lower:
        return TaskType.REASONING
    if "report" in agent_lower:
        return TaskType.REPORT
    if "categor" in agent_lower:
        return TaskType.CATEGORIZE

    # Message content analysis
    text = " ".join(
        m.get("content", "") for m in messages if isinstance(m.get("content"), str)
    ).lower()

    if not text.strip():
        return TaskType.CHAT

    for task_type in _CLASSIFY_PRIORITY:
        patterns = _TASK_PATTERNS.get(task_type, [])
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return task_type

    # Heuristic: short messages are simple
    if len(text) < 100:
        return TaskType.SIMPLE

    return TaskType.CHAT


# ==============================================================================
# Model Registry
# ==============================================================================


@dataclass
class ModelConfig:
    """Model configuration with pricing and capabilities."""

    name: str
    provider: str  # deepseek, openai, anthropic
    api_url: str
    api_key_env: str  # env var name for API key

    # Pricing (cents per 1K tokens)
    input_price: float
    output_price: float

    # Capabilities
    max_context: int  # max context window
    supports_tools: bool = True
    supports_vision: bool = False
    supports_streaming: bool = True

    # Performance
    avg_latency_ms: float = 2000  # expected avg latency
    reliability: float = 0.99  # historical success rate

    # Routing
    tier: int = 1  # 1=cheap, 2=standard, 3=premium
    enabled: bool = True


# Default model registry
_MODEL_REGISTRY: dict[str, ModelConfig] = {
    "deepseek-chat": ModelConfig(
        name="deepseek-chat",
        provider="deepseek",
        api_url="https://api.deepseek.com/v1/chat/completions",
        api_key_env="DEEPSEEK_API_KEY",
        input_price=0.14,
        output_price=0.28,
        max_context=65536,
        supports_tools=True,
        supports_vision=False,
        avg_latency_ms=1500,
        reliability=0.98,
        tier=1,
    ),
    "deepseek-coder": ModelConfig(
        name="deepseek-coder",
        provider="deepseek",
        api_url="https://api.deepseek.com/v1/chat/completions",
        api_key_env="DEEPSEEK_API_KEY",
        input_price=0.14,
        output_price=0.28,
        max_context=65536,
        supports_tools=True,
        avg_latency_ms=1800,
        reliability=0.97,
        tier=1,
    ),
    "deepseek-reasoner": ModelConfig(
        name="deepseek-reasoner",
        provider="deepseek",
        api_url="https://api.deepseek.com/v1/chat/completions",
        api_key_env="DEEPSEEK_API_KEY",
        input_price=0.55,
        output_price=2.19,
        max_context=65536,
        supports_tools=True,
        avg_latency_ms=8000,
        reliability=0.95,
        tier=3,
    ),
    "gpt-4o-mini": ModelConfig(
        name="gpt-4o-mini",
        provider="openai",
        api_url="https://api.openai.com/v1/chat/completions",
        api_key_env="OPENAI_API_KEY",
        input_price=15.0,
        output_price=60.0,
        max_context=128000,
        supports_tools=True,
        supports_vision=True,
        avg_latency_ms=2000,
        reliability=0.99,
        tier=2,
    ),
    "gpt-4o": ModelConfig(
        name="gpt-4o",
        provider="openai",
        api_url="https://api.openai.com/v1/chat/completions",
        api_key_env="OPENAI_API_KEY",
        input_price=250.0,
        output_price=1000.0,
        max_context=128000,
        supports_tools=True,
        supports_vision=True,
        avg_latency_ms=3000,
        reliability=0.99,
        tier=3,
    ),
}


def get_model_config(model_name: str) -> Optional[ModelConfig]:
    """Get model configuration by name."""
    return _MODEL_REGISTRY.get(model_name)


def register_model(config: ModelConfig):
    """Register a new model configuration."""
    _MODEL_REGISTRY[config.name] = config


def list_models() -> list[ModelConfig]:
    """List all registered models."""
    return list(_MODEL_REGISTRY.values())


# ==============================================================================
# Routing Strategy
# ==============================================================================


# Task → model preference order
_TASK_MODEL_MAP: dict[TaskType, list[str]] = {
    TaskType.SIMPLE: ["deepseek-chat"],
    TaskType.CHAT: ["deepseek-chat"],
    TaskType.ANALYSIS: ["deepseek-chat", "deepseek-coder"],
    TaskType.CODE: ["deepseek-coder", "deepseek-chat"],
    TaskType.OCR: ["gpt-4o-mini", "deepseek-chat"],  # vision-capable first
    TaskType.REASONING: ["deepseek-reasoner", "gpt-4o", "deepseek-chat"],
    TaskType.REPORT: ["deepseek-chat", "deepseek-coder"],
    TaskType.CATEGORIZE: ["deepseek-chat"],
    TaskType.EXTRACT: ["deepseek-chat", "gpt-4o-mini"],
}


@dataclass
class RoutingDecision:
    """Result of model routing."""

    model: str
    task_type: TaskType
    reason: str
    fallback_chain: list[str] = field(default_factory=list)
    cached: bool = False
    estimated_cost_cents: float = 0.0
    estimated_latency_ms: float = 0.0


@dataclass
class RoutingConfig:
    """Router configuration."""

    # Cost control
    max_cost_per_request_cents: float = 50.0  # max $0.50 per request
    max_cost_per_user_daily_cents: float = 500.0  # max $5/user/day
    budget_check_enabled: bool = True

    # Latency optimization
    prefer_fast_models: bool = True
    max_acceptable_latency_ms: float = 15000  # 15s max

    # Cache
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour

    # Fallback
    fallback_enabled: bool = True
    max_fallback_attempts: int = 3

    # Override
    force_model: Optional[str] = None  # override all routing


# Global config
_routing_config = RoutingConfig()


def get_routing_config() -> RoutingConfig:
    """Get the global routing configuration."""
    return _routing_config


def update_routing_config(**kwargs):
    """Update routing configuration."""
    for k, v in kwargs.items():
        if hasattr(_routing_config, k):
            setattr(_routing_config, k, v)


# ==============================================================================
# Cache Layer
# ==============================================================================


class ResponseCache:
    """Simple in-memory response cache with TTL."""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self._cache: dict[str, tuple[float, dict]] = {}
        self._max_size = max_size
        self._ttl = ttl

    def _make_key(self, messages: list, model: str) -> str:
        """Generate cache key from messages and model."""
        content = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(f"{model}:{content}".encode()).hexdigest()[:32]

    def get(self, messages: list, model: str) -> Optional[dict]:
        """Get cached response if available and not expired."""
        key = self._make_key(messages, model)
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._ttl:
                logger.debug(f"Cache hit for key {key[:8]}...")
                return data
            else:
                del self._cache[key]
        return None

    def set(self, messages: list, model: str, response: dict):
        """Cache a response."""
        if len(self._cache) >= self._max_size:
            # Evict oldest
            oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]

        key = self._make_key(messages, model)
        self._cache[key] = (time.time(), response)

    def invalidate(self, messages: list, model: str):
        """Invalidate a cached response."""
        key = self._make_key(messages, model)
        self._cache.pop(key, None)

    def clear(self):
        """Clear all cache."""
        self._cache.clear()

    def stats(self) -> dict:
        """Get cache statistics."""
        now = time.time()
        valid = sum(1 for ts, _ in self._cache.values() if now - ts < self._ttl)
        return {
            "size": len(self._cache),
            "valid": valid,
            "expired": len(self._cache) - valid,
            "max_size": self._max_size,
            "ttl": self._ttl,
        }


# Global cache instance
_response_cache = ResponseCache()


def get_cache() -> ResponseCache:
    """Get the global response cache."""
    return _response_cache


# ==============================================================================
# Budget Tracker
# ==============================================================================


class BudgetTracker:
    """Per-user daily budget tracking."""

    def __init__(self):
        self._usage: dict[str, dict[str, float]] = {}  # user_id -> {date: cents}

    def check_budget(self, user_id: str, estimated_cost: float) -> tuple[bool, str]:
        """Check if a request is within budget.

        Returns:
            (allowed, reason)
        """
        config = get_routing_config()
        if not config.budget_check_enabled:
            return True, "budget check disabled"

        from datetime import date
        today = date.today().isoformat()

        user_usage = self._usage.get(user_id, {})
        daily_cost = user_usage.get(today, 0.0)

        if daily_cost + estimated_cost > config.max_cost_per_user_daily_cents:
            return False, (
                f"Daily budget exceeded: ${daily_cost/100:.2f} + "
                f"${estimated_cost/100:.2f} > "
                f"${config.max_cost_per_user_daily_cents/100:.2f}"
            )

        return True, "within budget"

    def record_usage(self, user_id: str, cost_cents: float):
        """Record actual cost for a user."""
        from datetime import date
        today = date.today().isoformat()

        if user_id not in self._usage:
            self._usage[user_id] = {}
        self._usage[user_id][today] = self._usage[user_id].get(today, 0.0) + cost_cents

    def get_usage(self, user_id: str) -> dict:
        """Get usage summary for a user."""
        from datetime import date
        today = date.today().isoformat()
        user_usage = self._usage.get(user_id, {})
        return {
            "user_id": user_id,
            "today_cost_cents": round(user_usage.get(today, 0.0), 2),
            "today_cost_usd": round(user_usage.get(today, 0.0) / 100, 4),
            "budget_limit_cents": get_routing_config().max_cost_per_user_daily_cents,
            "budget_remaining_cents": round(
                get_routing_config().max_cost_per_user_daily_cents
                - user_usage.get(today, 0.0),
                2,
            ),
        }


# Global budget tracker
_budget_tracker = BudgetTracker()


def get_budget_tracker() -> BudgetTracker:
    """Get the global budget tracker."""
    return _budget_tracker


# ==============================================================================
# Model Router
# ==============================================================================


class ModelRouter:
    """Intelligent model router with task classification, fallback, and caching."""

    def __init__(self):
        self._cache = get_cache()
        self._budget = get_budget_tracker()

    def route(
        self,
        messages: list,
        agent_name: str = "unknown",
        user_id: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        model_override: Optional[str] = None,
        require_tools: bool = False,
        require_vision: bool = False,
    ) -> RoutingDecision:
        """Select the optimal model for a request.

        Args:
            messages: Chat messages
            agent_name: Calling agent name
            user_id: User ID for budget tracking
            task_type: Explicit task type override
            model_override: Force a specific model
            require_tools: Model must support tool calling
            require_vision: Model must support vision

        Returns:
            RoutingDecision with selected model and metadata
        """
        config = get_routing_config()

        # Force model override
        if config.force_model:
            model_cfg = get_model_config(config.force_model)
            if model_cfg:
                return RoutingDecision(
                    model=config.force_model,
                    task_type=task_type or TaskType.CHAT,
                    reason="forced by config",
                    estimated_cost_cents=self._estimate_cost(messages, config.force_model),
                    estimated_latency_ms=model_cfg.avg_latency_ms,
                )

        # Explicit override
        if model_override:
            model_cfg = get_model_config(model_override)
            if model_cfg:
                return RoutingDecision(
                    model=model_override,
                    task_type=task_type or TaskType.CHAT,
                    reason="explicit override",
                    estimated_cost_cents=self._estimate_cost(messages, model_override),
                    estimated_latency_ms=model_cfg.avg_latency_ms,
                )

        # Classify task
        if task_type is None:
            task_type = classify_task(messages, agent_name)

        # Get candidate models for this task
        candidates = _TASK_MODEL_MAP.get(task_type, ["deepseek-chat"])

        # Filter by requirements
        candidates = self._filter_candidates(
            candidates, require_tools=require_tools, require_vision=require_vision
        )

        if not candidates:
            # Fallback to default
            candidates = ["deepseek-chat"]
            logger.warning(f"No candidates for task {task_type}, falling back to deepseek-chat")

        # Select best model
        selected = self._select_best(candidates, messages, user_id, task_type)

        # Build fallback chain (exclude selected)
        fallback_chain = [m for m in candidates if m != selected]

        # Add cross-tier fallbacks
        if task_type == TaskType.REASONING and "deepseek-chat" not in fallback_chain:
            fallback_chain.append("deepseek-chat")

        model_cfg = get_model_config(selected)

        return RoutingDecision(
            model=selected,
            task_type=task_type,
            reason=f"task={task_type.value}, tier={model_cfg.tier if model_cfg else '?'}",
            fallback_chain=fallback_chain[:config.max_fallback_attempts],
            estimated_cost_cents=self._estimate_cost(messages, selected),
            estimated_latency_ms=model_cfg.avg_latency_ms if model_cfg else 2000,
        )

    def route_and_call(
        self,
        messages: list,
        agent_name: str = "unknown",
        user_id: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        model_override: Optional[str] = None,
        require_tools: bool = False,
        require_vision: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> dict:
        """Route to a model and execute the call with fallback.

        This is the main entry point for callers. It handles:
        1. Cache check
        2. Model selection
        3. Budget check
        4. LLM call
        5. Fallback on failure
        6. Cache storage
        7. Budget recording

        Returns:
            LLM response dict with added routing metadata
        """
        config = get_routing_config()

        # 1. Cache check
        if config.cache_enabled:
            # Use first candidate model for cache key
            decision = self.route(
                messages, agent_name, user_id, task_type,
                model_override, require_tools, require_vision,
            )
            cached = self._cache.get(messages, decision.model)
            if cached:
                logger.info(f"Cache hit for agent={agent_name} model={decision.model}")
                cached["_cache_hit"] = True
                cached["_routing"] = {
                    "model": decision.model,
                    "task_type": decision.task_type.value,
                    "reason": "cache hit",
                }
                return cached

        # 2. Route
        decision = self.route(
            messages, agent_name, user_id, task_type,
            model_override, require_tools, require_vision,
        )

        # 3. Budget check
        if user_id and config.budget_check_enabled:
            allowed, reason = self._budget.check_budget(
                user_id, decision.estimated_cost_cents
            )
            if not allowed:
                # Try cheaper model
                cheaper = self._find_cheaper_model(
                    decision.model, decision.fallback_chain
                )
                if cheaper:
                    logger.warning(
                        f"Budget exceeded for user {user_id}, "
                        f"downgrading {decision.model} → {cheaper}"
                    )
                    decision.model = cheaper
                    decision.reason += f", budget downgrade to {cheaper}"
                else:
                    raise ModelRouterError(f"Budget exceeded: {reason}")

        # 4. Execute with fallback
        response = self._execute_with_fallback(
            messages=messages,
            model=decision.model,
            fallback_chain=decision.fallback_chain,
            agent_name=agent_name,
            request_id=request_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # 5. Cache response
        if config.cache_enabled and response:
            self._cache.set(messages, decision.model, response)

        # 6. Record budget
        if user_id and response:
            usage = response.get("usage", {})
            actual_cost = self._compute_actual_cost(
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                response.get("model", decision.model),
            )
            self._budget.record_usage(user_id, actual_cost)

        # Add routing metadata
        response["_routing"] = {
            "model": decision.model,
            "task_type": decision.task_type.value,
            "reason": decision.reason,
            "fallback_chain": decision.fallback_chain,
            "estimated_cost_cents": decision.estimated_cost_cents,
        }
        response["_cache_hit"] = False

        return response

    def _filter_candidates(
        self, candidates: list[str],
        require_tools: bool = False,
        require_vision: bool = False,
    ) -> list[str]:
        """Filter candidate models by requirements."""
        result = []
        for name in candidates:
            cfg = get_model_config(name)
            if not cfg or not cfg.enabled:
                continue
            if require_tools and not cfg.supports_tools:
                continue
            if require_vision and not cfg.supports_vision:
                continue
            result.append(name)
        return result

    def _select_best(
        self,
        candidates: list[str],
        messages: list,
        user_id: Optional[str],
        task_type: TaskType,
    ) -> str:
        """Select the best model from candidates."""
        config = get_routing_config()

        if len(candidates) == 1:
            return candidates[0]

        # Score each candidate
        scored = []
        for name in candidates:
            cfg = get_model_config(name)
            if not cfg:
                continue

            score = 0.0

            # Cost score (lower is better, max 40 points)
            est_cost = self._estimate_cost(messages, name)
            max_cost = config.max_cost_per_request_cents
            cost_score = max(0, 40 * (1 - est_cost / max(max_cost, 0.01)))
            score += cost_score

            # Latency score (lower is better, max 30 points)
            if config.prefer_fast_models:
                latency_score = max(
                    0, 30 * (1 - cfg.avg_latency_ms / config.max_acceptable_latency_ms)
                )
                score += latency_score

            # Reliability score (max 20 points)
            score += cfg.reliability * 20

            # Tier bonus (prefer lower tier for cost savings, max 10 points)
            tier_score = max(0, 10 - (cfg.tier - 1) * 5)
            score += tier_score

            scored.append((name, score))

        if not scored:
            return candidates[0]

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def _find_cheaper_model(
        self, current: str, fallback_chain: list[str]
    ) -> Optional[str]:
        """Find a cheaper model from fallback chain."""
        current_cfg = get_model_config(current)
        if not current_cfg:
            return None

        best = None
        best_price = current_cfg.input_price

        for name in fallback_chain:
            cfg = get_model_config(name)
            if cfg and cfg.input_price < best_price:
                best = name
                best_price = cfg.input_price

        return best

    def _execute_with_fallback(
        self,
        messages: list,
        model: str,
        fallback_chain: list[str],
        agent_name: str,
        request_id: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> dict:
        """Execute LLM call with automatic fallback on failure."""
        from services.llm_client import get_llm_client, LLMClientError

        client = get_llm_client()
        models_to_try = [model] + fallback_chain
        last_error = None

        for attempt_model in models_to_try:
            try:
                logger.info(
                    f"LLM call: agent={agent_name} model={attempt_model} "
                    f"(attempt {models_to_try.index(attempt_model) + 1}/{len(models_to_try)})"
                )
                response = client.chat(
                    messages=messages,
                    model=attempt_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    agent_name=agent_name,
                    request_id=request_id,
                )
                if attempt_model != model:
                    logger.info(
                        f"Fallback succeeded: {model} → {attempt_model}"
                    )
                return response

            except LLMClientError as e:
                last_error = e
                logger.warning(
                    f"Model {attempt_model} failed: {e}, "
                    f"trying next in chain..."
                )
                continue

        raise ModelRouterError(
            f"All models failed. Last error: {last_error}"
        )

    def _estimate_cost(self, messages: list, model: str) -> float:
        """Estimate cost for a request in cents."""
        cfg = get_model_config(model)
        if not cfg:
            return 0.0

        # Estimate tokens (rough: 1 token ≈ 4 chars)
        total_chars = sum(len(m.get("content", "")) for m in messages)
        est_input_tokens = max(1, total_chars // 4)
        est_output_tokens = 500  # assume average output

        input_cost = (est_input_tokens / 1000) * cfg.input_price
        output_cost = (est_output_tokens / 1000) * cfg.output_price

        return round(input_cost + output_cost, 4)

    def _compute_actual_cost(
        self, input_tokens: int, output_tokens: int, model: str
    ) -> float:
        """Compute actual cost from token counts."""
        cfg = get_model_config(model)
        if not cfg:
            return 0.0

        input_cost = (input_tokens / 1000) * cfg.input_price
        output_cost = (output_tokens / 1000) * cfg.output_price

        return round(input_cost + output_cost, 4)

    def get_stats(self) -> dict:
        """Get router statistics."""
        return {
            "models": {
                name: {
                    "tier": cfg.tier,
                    "input_price": cfg.input_price,
                    "output_price": cfg.output_price,
                    "avg_latency_ms": cfg.avg_latency_ms,
                    "reliability": cfg.reliability,
                    "enabled": cfg.enabled,
                }
                for name, cfg in _MODEL_REGISTRY.items()
            },
            "cache": self._cache.stats(),
            "task_model_map": {
                k.value: v for k, v in _TASK_MODEL_MAP.items()
            },
        }


class ModelRouterError(Exception):
    """Model routing failure."""
    pass


# ==============================================================================
# Singleton
# ==============================================================================


_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    """Get or create the singleton ModelRouter."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
