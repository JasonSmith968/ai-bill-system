"""Tests for the Intelligent Model Router."""

import pytest
from services.model_router import (
    classify_task, TaskType, ModelRouter, RoutingDecision,
    get_router, get_cache, get_budget_tracker, get_routing_config,
    ModelConfig, register_model, ResponseCache, BudgetTracker,
    _MODEL_REGISTRY, _TASK_MODEL_MAP,
)


# ==============================================================================
# Task Classification Tests
# ==============================================================================


class TestTaskClassification:
    """Test task type classification from messages."""

    def test_classify_simple(self):
        """Short messages should be classified as SIMPLE."""
        messages = [{"role": "user", "content": "What is 2+2?"}]
        assert classify_task(messages) == TaskType.SIMPLE

    def test_classify_chat(self):
        """Medium-length general messages should be CHAT."""
        messages = [{"role": "user", "content": "Tell me about accounting best practices and how to manage finances effectively."}]
        result = classify_task(messages)
        assert result in (TaskType.CHAT, TaskType.ANALYSIS)

    def test_classify_ocr_from_content(self):
        """Messages mentioning OCR should be classified as OCR."""
        messages = [{"role": "user", "content": "Please OCR this receipt image and extract the data."}]
        assert classify_task(messages) == TaskType.OCR

    def test_classify_ocr_chinese(self):
        """Chinese OCR keywords should work."""
        messages = [{"role": "user", "content": "请识别这张发票上的文字"}]
        assert classify_task(messages) == TaskType.OCR

    def test_classify_reasoning(self):
        """Complex reasoning tasks should be REASONING."""
        messages = [{"role": "user", "content": "Analyze why our expenses increased and calculate the trend."}]
        result = classify_task(messages)
        assert result in (TaskType.REASONING, TaskType.ANALYSIS)

    def test_classify_code(self):
        """Code-related messages should be CODE."""
        messages = [{"role": "user", "content": "Write a function to calculate tax deductions."}]
        assert classify_task(messages) == TaskType.CODE

    def test_classify_categorize(self):
        """Categorization requests should be CATEGORIZE."""
        messages = [{"role": "user", "content": "Categorize this transaction into the right category."}]
        assert classify_task(messages) == TaskType.CATEGORIZE

    def test_classify_report(self):
        """Report generation should be REPORT."""
        messages = [{"role": "user", "content": "Generate a monthly expense report."}]
        assert classify_task(messages) == TaskType.REPORT

    def test_classify_by_agent_name(self):
        """Agent name should influence classification."""
        messages = [{"role": "user", "content": "Process this."}]

        assert classify_task(messages, agent_name="ocr_agent") == TaskType.OCR
        assert classify_task(messages, agent_name="tax_advisor") == TaskType.REASONING
        assert classify_task(messages, agent_name="report_gen") == TaskType.REPORT
        assert classify_task(messages, agent_name="categorizer") == TaskType.CATEGORIZE

    def test_classify_empty_messages(self):
        """Empty messages should default to CHAT."""
        assert classify_task([]) == TaskType.CHAT
        assert classify_task([{"role": "user", "content": ""}]) == TaskType.CHAT


# ==============================================================================
# Response Cache Tests
# ==============================================================================


class TestResponseCache:
    """Test the response cache."""

    def test_cache_hit(self):
        """Cached response should be returned on hit."""
        cache = ResponseCache(max_size=10, ttl=60)
        messages = [{"role": "user", "content": "test"}]
        response = {"content": "cached result"}

        cache.set(messages, "model-a", response)
        result = cache.get(messages, "model-a")

        assert result is not None
        assert result["content"] == "cached result"

    def test_cache_miss_different_model(self):
        """Same messages with different model should miss."""
        cache = ResponseCache()
        messages = [{"role": "user", "content": "test"}]

        cache.set(messages, "model-a", {"content": "a"})
        assert cache.get(messages, "model-b") is None

    def test_cache_miss_different_messages(self):
        """Different messages should miss."""
        cache = ResponseCache()
        cache.set([{"role": "user", "content": "a"}], "m", {"content": "1"})
        assert cache.get([{"role": "user", "content": "b"}], "m") is None

    def test_cache_expiry(self):
        """Expired entries should miss."""
        import time
        cache = ResponseCache(ttl=1)
        messages = [{"role": "user", "content": "test"}]

        cache.set(messages, "m", {"content": "1"})
        assert cache.get(messages, "m") is not None

        time.sleep(1.1)
        assert cache.get(messages, "m") is None

    def test_cache_eviction(self):
        """Oldest entry should be evicted when full."""
        cache = ResponseCache(max_size=2)

        cache.set([{"role": "user", "content": "1"}], "m", {"content": "1"})
        cache.set([{"role": "user", "content": "2"}], "m", {"content": "2"})
        cache.set([{"role": "user", "content": "3"}], "m", {"content": "3"})

        # First entry should be evicted
        assert cache.get([{"role": "user", "content": "1"}], "m") is None
        assert cache.get([{"role": "user", "content": "3"}], "m") is not None

    def test_cache_stats(self):
        """Stats should report correct counts."""
        cache = ResponseCache(max_size=10, ttl=60)
        cache.set([{"role": "user", "content": "1"}], "m", {"content": "1"})

        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["valid"] == 1
        assert stats["max_size"] == 10

    def test_cache_clear(self):
        """Clear should remove all entries."""
        cache = ResponseCache()
        cache.set([{"role": "user", "content": "1"}], "m", {"content": "1"})
        cache.clear()
        assert cache.stats()["size"] == 0


# ==============================================================================
# Budget Tracker Tests
# ==============================================================================


class TestBudgetTracker:
    """Test per-user budget tracking."""

    def test_within_budget(self):
        """Request within budget should be allowed."""
        tracker = BudgetTracker()
        allowed, reason = tracker.check_budget("user1", 10.0)
        assert allowed is True

    def test_exceed_budget(self):
        """Request exceeding budget should be denied."""
        tracker = BudgetTracker()
        # Record usage close to limit
        tracker.record_usage("user1", 490.0)

        allowed, reason = tracker.check_budget("user1", 20.0)
        assert allowed is False
        assert "exceeded" in reason.lower()

    def test_budget_accumulation(self):
        """Multiple requests should accumulate."""
        tracker = BudgetTracker()
        tracker.record_usage("user1", 200.0)
        tracker.record_usage("user1", 200.0)

        # Total is 400, limit is 500
        allowed, _ = tracker.check_budget("user1", 50.0)
        assert allowed is True

        allowed, _ = tracker.check_budget("user1", 150.0)
        assert allowed is False

    def test_budget_per_user_isolation(self):
        """Different users should have separate budgets."""
        tracker = BudgetTracker()
        tracker.record_usage("user1", 490.0)

        # user2 should be fine
        allowed, _ = tracker.check_budget("user2", 100.0)
        assert allowed is True

    def test_get_usage(self):
        """get_usage should return correct summary."""
        tracker = BudgetTracker()
        tracker.record_usage("user1", 123.45)

        usage = tracker.get_usage("user1")
        assert usage["user_id"] == "user1"
        assert usage["today_cost_cents"] == 123.45
        assert usage["budget_limit_cents"] > 0


# ==============================================================================
# Model Router Tests
# ==============================================================================


class TestModelRouter:
    """Test the model router."""

    def test_route_simple_task(self):
        """Simple tasks should route to cheap model."""
        router = ModelRouter()
        messages = [{"role": "user", "content": "Hi"}]

        decision = router.route(messages, agent_name="chat")

        assert decision.model == "deepseek-chat"
        assert decision.task_type in (TaskType.SIMPLE, TaskType.CHAT)

    def test_route_reasoning_task(self):
        """Reasoning tasks should route to premium model."""
        router = ModelRouter()
        messages = [
            {"role": "user", "content": "Analyze why our expenses increased and calculate the projected trend for next quarter."}
        ]

        decision = router.route(messages, agent_name="advisor")

        # Should prefer reasoning model
        assert decision.model in ("deepseek-reasoner", "gpt-4o", "deepseek-chat")
        assert decision.task_type in (TaskType.REASONING, TaskType.ANALYSIS)

    def test_route_ocr_task(self):
        """OCR tasks should route to vision-capable model."""
        router = ModelRouter()
        messages = [{"role": "user", "content": "OCR this receipt image."}]

        decision = router.route(messages, agent_name="ocr")

        assert decision.task_type == TaskType.OCR
        # Should prefer vision model or fallback
        assert decision.model in ("gpt-4o-mini", "deepseek-chat")

    def test_route_with_override(self):
        """Model override should be respected."""
        router = ModelRouter()
        messages = [{"role": "user", "content": "test"}]

        decision = router.route(messages, model_override="deepseek-reasoner")

        assert decision.model == "deepseek-reasoner"
        assert "override" in decision.reason

    def test_route_fallback_chain(self):
        """Fallback chain should be populated."""
        router = ModelRouter()
        messages = [{"role": "user", "content": "Analyze this complex data."}]

        decision = router.route(messages)

        assert isinstance(decision.fallback_chain, list)

    def test_route_cost_estimation(self):
        """Cost should be estimated."""
        router = ModelRouter()
        messages = [{"role": "user", "content": "Hello world"}]

        decision = router.route(messages)

        assert decision.estimated_cost_cents >= 0

    def test_route_latency_estimation(self):
        """Latency should be estimated."""
        router = ModelRouter()
        messages = [{"role": "user", "content": "Hello"}]

        decision = router.route(messages)

        assert decision.estimated_latency_ms > 0

    def test_route_vision_requirement(self):
        """Vision requirement should filter models."""
        router = ModelRouter()
        messages = [{"role": "user", "content": "Describe this image."}]

        decision = router.route(messages, require_vision=True)

        cfg = _MODEL_REGISTRY.get(decision.model)
        assert cfg is not None
        assert cfg.supports_vision or decision.model == "deepseek-chat"  # fallback

    def test_route_tools_requirement(self):
        """Tool requirement should filter models."""
        router = ModelRouter()
        messages = [{"role": "user", "content": "Use the calculator tool."}]

        decision = router.route(messages, require_tools=True)

        cfg = _MODEL_REGISTRY.get(decision.model)
        assert cfg is not None
        assert cfg.supports_tools


# ==============================================================================
# Model Registry Tests
# ==============================================================================


class TestModelRegistry:
    """Test model registration and configuration."""

    def test_default_models_registered(self):
        """Default models should be registered."""
        assert "deepseek-chat" in _MODEL_REGISTRY
        assert "deepseek-reasoner" in _MODEL_REGISTRY
        assert "gpt-4o-mini" in _MODEL_REGISTRY

    def test_register_custom_model(self):
        """Custom models can be registered."""
        custom = ModelConfig(
            name="test-model",
            provider="test",
            api_url="http://test.com",
            api_key_env="TEST_KEY",
            input_price=1.0,
            output_price=2.0,
            max_context=4096,
        )
        register_model(custom)

        assert "test-model" in _MODEL_REGISTRY
        assert _MODEL_REGISTRY["test-model"].provider == "test"

        # Cleanup
        del _MODEL_REGISTRY["test-model"]

    def test_model_tiers(self):
        """Models should have correct tiers."""
        assert _MODEL_REGISTRY["deepseek-chat"].tier == 1
        assert _MODEL_REGISTRY["deepseek-reasoner"].tier == 3

    def test_list_models(self):
        """list_models should return all models."""
        models = list_models()
        assert len(models) >= 3
        assert all(isinstance(m, ModelConfig) for m in models)


# ==============================================================================
# Routing Config Tests
# ==============================================================================


class TestRoutingConfig:
    """Test routing configuration."""

    def test_default_config(self):
        """Default config should have sensible values."""
        config = get_routing_config()

        assert config.max_cost_per_request_cents > 0
        assert config.max_cost_per_user_daily_cents > 0
        assert config.cache_enabled is True
        assert config.fallback_enabled is True

    def test_force_model(self):
        """Force model should override routing."""
        from services.model_router import update_routing_config

        update_routing_config(force_model="deepseek-reasoner")

        router = ModelRouter()
        decision = router.route([{"role": "user", "content": "Hi"}])
        assert decision.model == "deepseek-reasoner"
        assert "forced" in decision.reason

        # Reset
        update_routing_config(force_model=None)

    def test_disable_cache(self):
        """Disabling cache should prevent cache hits."""
        from services.model_router import update_routing_config

        update_routing_config(cache_enabled=False)

        router = ModelRouter()
        messages = [{"role": "user", "content": "unique test message"}]

        # First call
        result1 = router.route(messages)
        # Should not have cache hit
        assert result1.cached is False

        # Reset
        update_routing_config(cache_enabled=True)


# ==============================================================================
# Integration Tests
# ==============================================================================


class TestRouterIntegration:
    """Test router integration scenarios."""

    def test_cache_roundtrip(self):
        """Cache should work through the router."""
        cache = ResponseCache(max_size=100, ttl=300)
        messages = [{"role": "user", "content": "cache test"}]
        model = "deepseek-chat"

        # Simulate LLM response
        response = {"content": "Hello!", "usage": {"prompt_tokens": 10, "completion_tokens": 5}}

        # Cache it
        cache.set(messages, model, response)

        # Retrieve it
        cached = cache.get(messages, model)
        assert cached is not None
        assert cached["content"] == "Hello!"

    def test_budget_integration(self):
        """Budget should accumulate across requests."""
        tracker = BudgetTracker()

        # Simulate multiple requests
        for _ in range(10):
            tracker.record_usage("user1", 40.0)

        # Total: 400 cents
        usage = tracker.get_usage("user1")
        assert usage["today_cost_cents"] == 400.0

        # Should still be within budget
        allowed, _ = tracker.check_budget("user1", 50.0)
        assert allowed is True

        # But not for a large request
        allowed, _ = tracker.check_budget("user1", 200.0)
        assert allowed is False

    def test_task_model_mapping(self):
        """Every task type should have at least one model."""
        for task_type in TaskType:
            models = _TASK_MODEL_MAP.get(task_type, [])
            assert len(models) > 0, f"No models for task type {task_type}"
            for model_name in models:
                assert model_name in _MODEL_REGISTRY, (
                    f"Model {model_name} not in registry (task: {task_type})"
                )
