"""Context Compressor — intelligent context window management.

Provides multiple compression strategies:
1. LLM-based summarization (best quality, costs tokens)
2. Sliding window (zero cost, loses older context)
3. Hybrid: summarize older messages, keep recent ones intact
"""

import logging
from typing import Optional

from agents.token_budget import estimate_tokens, estimate_messages_tokens

logger = logging.getLogger(__name__)

_compressor = None


def get_compressor() -> 'ContextCompressor':
    """Get or create the singleton ContextCompressor."""
    global _compressor
    if _compressor is None:
        _compressor = ContextCompressor()
    return _compressor


class ContextCompressor:
    """Intelligent context compression for long conversations.

    Strategies:
    - summarize: Use LLM to create a summary of older messages
    - sliding_window: Keep system + last N messages, drop the rest
    - hybrid: Summarize if LLM available, else sliding window
    """

    def compress(self, messages: list, max_tokens: int = 3000,
                 strategy: str = 'hybrid') -> list:
        """Compress messages to fit within token budget.

        Args:
            messages: List of message dicts
            max_tokens: Target maximum tokens
            strategy: 'summarize', 'sliding_window', or 'hybrid'

        Returns:
            Compressed messages list
        """
        if not messages:
            return messages

        estimated = estimate_messages_tokens(messages)
        if estimated <= max_tokens:
            return messages

        logger.info(
            f"Context compression needed: {estimated} tokens > {max_tokens} limit "
            f"(strategy={strategy})"
        )

        if strategy == 'summarize':
            return self._summarize_strategy(messages, max_tokens)
        elif strategy == 'sliding_window':
            return self._sliding_window(messages, max_tokens)
        else:  # hybrid
            return self._hybrid_strategy(messages, max_tokens)

    def summarize_messages(self, messages: list) -> Optional[str]:
        """Summarize a list of messages into a single text using LLM.

        Returns None if LLM is unavailable.
        """
        if not messages:
            return None

        # Build a summarization prompt
        conversation = []
        for m in messages:
            role = m.get('role', 'user')
            content = m.get('content', '')
            if isinstance(content, str) and content.strip():
                conversation.append(f"[{role}]: {content[:300]}")

        if not conversation:
            return None

        summary_input = '\n'.join(conversation)

        try:
            from services.llm_client import get_llm_client
            llm = get_llm_client()

            summary_messages = [
                {
                    'role': 'system',
                    'content': (
                        '你是一个对话摘要助手。将以下对话压缩成简洁的摘要，'
                        '保留关键信息（用户需求、重要结论、待办事项）。'
                        '用中文，不超过200字。'
                    ),
                },
                {'role': 'user', 'content': summary_input},
            ]

            result = llm.chat(
                summary_messages,
                max_tokens=300,
                temperature=0.3,
                agent_name='context_compressor',
            )
            return result.get('content', '')

        except Exception as e:
            logger.warning(f"LLM summarization failed, falling back to truncation: {e}")
            return None

    def sliding_window(self, messages: list, max_tokens: int) -> list:
        """Keep system messages + last N messages that fit in budget."""
        return self._sliding_window(messages, max_tokens)

    def _sliding_window(self, messages: list, max_tokens: int) -> list:
        """Sliding window: system messages + as many recent messages as fit."""
        system_msgs = [m for m in messages if m.get('role') == 'system']
        other_msgs = [m for m in messages if m.get('role') != 'system']

        system_tokens = estimate_messages_tokens(system_msgs)
        remaining_budget = max_tokens - system_tokens - 50  # buffer

        if remaining_budget <= 0:
            # System messages alone exceed budget — truncate system
            return self._truncate_messages(system_msgs, max_tokens)

        # Add messages from the end, stopping when budget is exhausted
        selected = []
        used_tokens = 0
        for msg in reversed(other_msgs):
            msg_tokens = estimate_messages_tokens([msg])
            if used_tokens + msg_tokens > remaining_budget:
                break
            selected.insert(0, msg)
            used_tokens += msg_tokens

        if not selected:
            # Even one message exceeds budget — truncate the last one
            selected = [self._truncate_messages([other_msgs[-1]], remaining_budget)[0]] if other_msgs else []

        return system_msgs + selected

    def _summarize_strategy(self, messages: list, max_tokens: int) -> list:
        """Summarize older messages, keep recent ones intact."""
        system_msgs = [m for m in messages if m.get('role') == 'system']
        other_msgs = [m for m in messages if m.get('role') != 'system']

        if len(other_msgs) <= 3:
            return self._sliding_window(messages, max_tokens)

        # Split: older messages for summarization, recent ones to keep
        split_point = max(1, len(other_msgs) - 3)
        old_msgs = other_msgs[:split_point]
        recent_msgs = other_msgs[split_point:]

        summary = self.summarize_messages(old_msgs)
        if summary:
            summary_msg = {
                'role': 'system',
                'content': f'## 之前的对话摘要\n{summary}',
            }
            result = system_msgs + [summary_msg] + recent_msgs
        else:
            # LLM unavailable — fall back to truncation
            truncated_old = self._truncate_messages(old_msgs, 500)
            result = system_msgs + truncated_old + recent_msgs

        # Final budget check
        if estimate_messages_tokens(result) > max_tokens:
            result = self._sliding_window(result, max_tokens)

        return result

    def _hybrid_strategy(self, messages: list, max_tokens: int) -> list:
        """Try LLM summarization, fall back to sliding window."""
        system_msgs = [m for m in messages if m.get('role') == 'system']
        other_msgs = [m for m in messages if m.get('role') != 'system']

        if len(other_msgs) <= 4:
            return self._sliding_window(messages, max_tokens)

        # Try summarization for older messages
        split_point = max(1, len(other_msgs) - 3)
        old_msgs = other_msgs[:split_point]

        summary = self.summarize_messages(old_msgs)
        if summary:
            summary_msg = {
                'role': 'system',
                'content': f'## 之前的对话摘要\n{summary}',
            }
            recent_msgs = other_msgs[split_point:]
            result = system_msgs + [summary_msg] + recent_msgs

            if estimate_messages_tokens(result) <= max_tokens:
                return result

        # Fallback to sliding window
        return self._sliding_window(messages, max_tokens)

    def _truncate_messages(self, messages: list, max_tokens: int) -> list:
        """Truncate messages to fit within token budget (character-level)."""
        result = []
        used_tokens = 0

        for msg in messages:
            msg_tokens = estimate_messages_tokens([msg])
            if used_tokens + msg_tokens > max_tokens:
                # Truncate content
                remaining = max_tokens - used_tokens
                if remaining <= 10:
                    break
                content = msg.get('content', '')
                # Estimate chars from tokens (rough: 2.5 chars per token)
                max_chars = int(remaining * 2.5)
                truncated = content[:max_chars] + '...(截断)'
                result.append({**msg, 'content': truncated})
                break

            result.append(msg)
            used_tokens += msg_tokens

        return result
