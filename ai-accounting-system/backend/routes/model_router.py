"""Model Router API endpoints."""

from flask import Blueprint, request, jsonify
from utils.jwt_helper import token_required, admin_required
from services.model_router import (
    get_router, get_routing_config, update_routing_config,
    get_cache, get_budget_tracker, classify_task, TaskType,
    list_models, get_model_config,
)

router_bp = Blueprint("model_router", __name__)


@router_bp.route("/stats", methods=["GET"])
@token_required
@admin_required
def router_stats():
    """Get model router statistics."""
    router = get_router()
    return jsonify(router.get_stats())


@router_bp.route("/classify", methods=["POST"])
@token_required
def classify():
    """Classify a task from messages."""
    data = request.get_json()
    messages = data.get("messages", [])
    agent_name = data.get("agent_name", "")

    task_type = classify_task(messages, agent_name)

    # Get recommended model
    router = get_router()
    decision = router.route(messages, agent_name)

    return jsonify({
        "task_type": task_type.value,
        "recommended_model": decision.model,
        "reason": decision.reason,
        "fallback_chain": decision.fallback_chain,
        "estimated_cost_cents": decision.estimated_cost_cents,
        "estimated_latency_ms": decision.estimated_latency_ms,
    })


@router_bp.route("/config", methods=["GET"])
@token_required
@admin_required
def get_config():
    """Get current routing configuration."""
    config = get_routing_config()
    return jsonify({
        "max_cost_per_request_cents": config.max_cost_per_request_cents,
        "max_cost_per_user_daily_cents": config.max_cost_per_user_daily_cents,
        "budget_check_enabled": config.budget_check_enabled,
        "prefer_fast_models": config.prefer_fast_models,
        "max_acceptable_latency_ms": config.max_acceptable_latency_ms,
        "cache_enabled": config.cache_enabled,
        "cache_ttl_seconds": config.cache_ttl_seconds,
        "fallback_enabled": config.fallback_enabled,
        "max_fallback_attempts": config.max_fallback_attempts,
        "force_model": config.force_model,
    })


@router_bp.route("/config", methods=["PUT"])
@token_required
@admin_required
def update_config():
    """Update routing configuration."""
    data = request.get_json()
    update_routing_config(**data)
    return jsonify({"status": "updated", "config": data})


@router_bp.route("/models", methods=["GET"])
@token_required
@admin_required
def models_list():
    """List all registered models."""
    models = list_models()
    return jsonify({
        "models": [
            {
                "name": m.name,
                "provider": m.provider,
                "tier": m.tier,
                "input_price": m.input_price,
                "output_price": m.output_price,
                "max_context": m.max_context,
                "supports_tools": m.supports_tools,
                "supports_vision": m.supports_vision,
                "avg_latency_ms": m.avg_latency_ms,
                "reliability": m.reliability,
                "enabled": m.enabled,
            }
            for m in models
        ]
    })


@router_bp.route("/models/<name>", methods=["PUT"])
@token_required
@admin_required
def update_model(name):
    """Update model configuration."""
    cfg = get_model_config(name)
    if not cfg:
        return jsonify({"error": f"Model '{name}' not found"}), 404

    data = request.get_json()
    for k, v in data.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)

    return jsonify({"status": "updated", "model": name})


@router_bp.route("/cache", methods=["GET"])
@token_required
@admin_required
def cache_stats():
    """Get cache statistics."""
    cache = get_cache()
    return jsonify(cache.stats())


@router_bp.route("/cache", methods=["DELETE"])
@token_required
@admin_required
def clear_cache():
    """Clear the response cache."""
    cache = get_cache()
    cache.clear()
    return jsonify({"status": "cache cleared"})


@router_bp.route("/budget/<int:user_id>", methods=["GET"])
@token_required
@admin_required
def user_budget(user_id):
    """Get budget usage for a user."""
    tracker = get_budget_tracker()
    return jsonify(tracker.get_usage(str(user_id)))
