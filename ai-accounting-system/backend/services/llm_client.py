"""LLM Client — Unified abstraction for LLM API calls.

Supports DeepSeek (OpenAI-compatible) as default provider.
Provides retry, timeout, streaming, and tool calling support.

Integrated hardening:
- Circuit breaker (per-model) to fast-fail on repeated errors
- Token budget enforcement before each request
- Error recovery with classification and backoff
- LLM call tracing (metadata only, no content)
"""

import time
import json
import logging
from typing import Generator

import requests
from flask import current_app

from agents.circuit_breaker import get_breaker
from agents.token_budget import TokenBudget, estimate_messages_tokens, compute_cost
from agents.error_recovery import ErrorRecovery, classify_error, should_retry, get_wait_seconds
from services.cost_control import get_cost_control

logger = logging.getLogger(__name__)

_client = None


def get_llm_client():
    """Get or create the singleton LLMClient instance."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


class LLMClientError(Exception):
    """LLM call failure."""
    pass


class LLMClient:
    """Unified LLM API client with retry, streaming, and tool calling.

    Integrates circuit breaker, token budget, error recovery, and tracing.
    """

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({'Content-Type': 'application/json'})

    @property
    def _config(self):
        return {
            'api_key': current_app.config.get('DEEPSEEK_API_KEY', ''),
            'api_url': current_app.config.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions'),
            'model': current_app.config.get('LLM_MODEL', 'deepseek-chat'),
            'temperature': float(current_app.config.get('LLM_TEMPERATURE', 0.7)),
            'max_tokens': int(current_app.config.get('LLM_MAX_TOKENS', 2000)),
            'timeout': int(current_app.config.get('LLM_TIMEOUT', 30)),
        }

    def chat(self, messages, model=None, temperature=None, max_tokens=None,
             tools=None, stream=False, agent_name='unknown', request_id=None):
        """Send a chat completion request.

        Args:
            messages: List of message dicts [{role, content}, ...]
            model: Model override (default from config)
            temperature: Temperature override
            max_tokens: Max tokens override
            tools: OpenAI function calling tool definitions
            stream: Whether to stream the response
            agent_name: Caller agent name (for circuit breaker + tracing)
            request_id: Request ID (for tracing)

        Returns:
            If stream=False: dict with 'content', 'usage', 'model'
            If stream=True: generator yielding str chunks
        """
        cfg = self._config
        if not cfg['api_key']:
            raise LLMClientError('DEEPSEEK_API_KEY not configured')

        resolved_model = model or cfg['model']
        resolved_max_tokens = max_tokens or cfg['max_tokens']

        # --- Circuit breaker check ---
        breaker = get_breaker(agent_name)
        if not breaker.allow_request():
            raise LLMClientError(
                f"Circuit breaker OPEN for agent '{agent_name}', "
                f"using fallback. State: {breaker.get_state()}"
            )

        # --- Token budget check ---
        budget = TokenBudget()
        allowed, reason = budget.check_budget(
            messages, max_tokens=resolved_max_tokens, model=resolved_model
        )
        if not allowed:
            raise LLMClientError(f"Token budget exceeded: {reason}")

        # --- Cost control guardrail ---
        estimated_input = estimate_messages_tokens(messages)
        from agents.token_budget import compute_cost as _est_cost
        est_cost = _est_cost(estimated_input, resolved_max_tokens, resolved_model)
        try:
            cc = get_cost_control()
            cc_allowed, cc_details = cc.check_request_allowed(
                user_id=agent_name,  # agent_name acts as caller ID
                estimated_input_tokens=estimated_input,
                estimated_output_tokens=resolved_max_tokens,
                estimated_cost_cents=est_cost,
            )
            if not cc_allowed:
                raise LLMClientError(
                    f"Cost control denied: {cc_details.get('message', 'budget exceeded')}"
                )
        except LLMClientError:
            raise
        except Exception:
            pass  # Cost control failure should not block LLM calls

        payload = {
            'model': resolved_model,
            'messages': messages,
            'temperature': temperature if temperature is not None else cfg['temperature'],
            'max_tokens': resolved_max_tokens,
            'stream': stream,
        }

        if tools:
            payload['tools'] = tools
            payload['tool_choice'] = 'auto'

        headers = {'Authorization': f'Bearer {cfg["api_key"]}'}

        if stream:
            return self._stream_request(
                cfg['api_url'], headers, payload, cfg['timeout'],
                agent_name=agent_name, request_id=request_id,
            )

        return self._request_with_retry(
            cfg['api_url'], headers, payload, cfg['timeout'],
            agent_name=agent_name, request_id=request_id,
        )

    def chat_stream(self, messages, **kwargs):
        """Convenience: always returns a string generator."""
        kwargs['stream'] = True
        return self.chat(messages, **kwargs)

    def _request_with_retry(self, url, headers, payload, timeout,
                            agent_name='unknown', request_id=None):
        """Send request with error recovery and circuit breaker integration."""
        model = payload.get('model', 'deepseek-chat')
        recovery = ErrorRecovery()
        start_time = time.time()

        while True:
            try:
                resp = self._session.post(
                    url, headers=headers, json=payload, timeout=timeout
                )

                if resp.status_code == 200:
                    data = resp.json()
                    choice = data['choices'][0]
                    usage = data.get('usage', {})
                    input_tokens = usage.get('prompt_tokens', 0)
                    output_tokens = usage.get('completion_tokens', 0)

                    # Record success
                    self._record_success(
                        agent_name, model, input_tokens, output_tokens,
                        time.time() - start_time, request_id,
                    )

                    return {
                        'content': choice['message'].get('content', ''),
                        'tool_calls': choice['message'].get('tool_calls'),
                        'finish_reason': choice.get('finish_reason', ''),
                        'usage': usage,
                        'model': data.get('model', ''),
                    }

                # HTTP error — raise to be caught below
                resp.raise_for_status()

            except (requests.Timeout, requests.ConnectionError,
                    requests.HTTPError) as exc:
                decision = recovery.handle_error(exc)

                if decision['should_retry']:
                    logger.warning(
                        f"LLM {decision['error_type']} (attempt {decision['attempt']}), "
                        f"retrying in {decision['wait_seconds']:.1f}s"
                    )
                    time.sleep(decision['wait_seconds'])
                    continue

                # No retry — record failure and raise
                self._record_failure(
                    agent_name, model, decision['error_type'],
                    time.time() - start_time, request_id,
                )
                raise LLMClientError(
                    f"LLM call failed ({decision['error_type']}): {exc}"
                ) from exc

            except Exception as exc:
                # Unexpected error
                decision = recovery.handle_error(exc)
                self._record_failure(
                    agent_name, model, decision['error_type'],
                    time.time() - start_time, request_id,
                )
                raise LLMClientError(f"LLM call failed: {exc}") from exc

    def _stream_request(self, url, headers, payload, timeout,
                        agent_name='unknown', request_id=None):
        """Streaming SSE request — yields content chunks."""
        model = payload.get('model', 'deepseek-chat')
        start_time = time.time()

        try:
            resp = self._session.post(
                url, headers=headers, json=payload, timeout=timeout, stream=True
            )
            if resp.status_code != 200:
                error_type = classify_error(
                    requests.HTTPError(response=resp)
                )
                self._record_failure(
                    agent_name, model, error_type,
                    time.time() - start_time, request_id,
                )
                raise LLMClientError(
                    f"LLM stream error {resp.status_code}: {resp.text[:200]}"
                )

            chunk_count = 0
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith('data: '):
                    continue
                data_str = line[6:]
                if data_str.strip() == '[DONE]':
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk['choices'][0].get('delta', {})
                    content = delta.get('content', '')
                    if content:
                        chunk_count += 1
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

            # Stream completed successfully
            # Estimate tokens from chunk count (rough: ~4 chars per chunk average)
            estimated_output = max(1, chunk_count * 2)
            self._record_success(
                agent_name, model, 0, estimated_output,
                time.time() - start_time, request_id,
            )

        except requests.Timeout:
            self._record_failure(
                agent_name, model, 'timeout',
                time.time() - start_time, request_id,
            )
            raise LLMClientError("LLM stream timeout")
        except requests.ConnectionError as e:
            self._record_failure(
                agent_name, model, 'connection_error',
                time.time() - start_time, request_id,
            )
            raise LLMClientError(f"LLM stream connection error: {e}")

    def _record_success(self, agent_name, model, input_tokens, output_tokens,
                        duration_s, request_id):
        """Record a successful LLM call — breaker, budget, tracer, cost control."""
        # Circuit breaker
        breaker = get_breaker(agent_name)
        breaker.record_success()

        # Token budget
        budget = TokenBudget()
        budget.record_usage(input_tokens, output_tokens, model)

        # Cost control — record actual usage
        cost_cents = compute_cost(input_tokens, output_tokens, model)
        try:
            cc = get_cost_control()
            cc.record_usage(
                user_id=agent_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_cents=cost_cents,
            )
        except Exception:
            pass

        # Tracer
        try:
            from agents.llm_tracer import get_tracer
            tracer = get_tracer()
            tracer.trace_call(
                agent_name=agent_name,
                request_id=request_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=int(duration_s * 1000),
                cost_cents=cost_cents,
                success=True,
            )
        except Exception:
            pass  # Tracer failure should never break the main flow

        logger.info(
            f"LLM success: agent={agent_name} model={model} "
            f"tokens={input_tokens}+{output_tokens} "
            f"cost={cost_cents:.4f}c duration={duration_s:.2f}s"
        )

    def _record_failure(self, agent_name, model, error_type,
                        duration_s, request_id):
        """Record a failed LLM call — breaker, tracer."""
        # Circuit breaker
        breaker = get_breaker(agent_name)
        breaker.record_failure()

        # Tracer
        try:
            from agents.llm_tracer import get_tracer
            tracer = get_tracer()
            tracer.trace_call(
                agent_name=agent_name,
                request_id=request_id,
                model=model,
                input_tokens=0,
                output_tokens=0,
                duration_ms=int(duration_s * 1000),
                cost_cents=0,
                success=False,
                error_type=error_type,
            )
        except Exception:
            pass

        logger.warning(
            f"LLM failure: agent={agent_name} model={model} "
            f"error_type={error_type} duration={duration_s:.2f}s"
        )

    def chat_with_tools(self, messages, tools, model=None, temperature=None,
                        max_tokens=None, agent_name='unknown', request_id=None):
        """Chat with tool calling support. Returns dict with content + tool_calls."""
        return self.chat(
            messages, model=model, temperature=temperature,
            max_tokens=max_tokens, tools=tools, stream=False,
            agent_name=agent_name, request_id=request_id,
        )
