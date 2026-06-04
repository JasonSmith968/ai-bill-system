"""Core data structures for the multi-agent system."""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime


class AgentContext:
    """Shared context passed between agents during a multi-agent operation."""

    def __init__(self, user_id, request_id=''):
        self.user_id = user_id
        self.request_id = request_id or str(uuid.uuid4())[:8]
        self._data = {}
        self._sources = {}
        self._timestamps = {}
        self.call_chain = []
        self._memory = None
        self._tools = None
        self._llm = None

    def set(self, key, value, source_agent):
        self._data[key] = value
        self._sources[key] = source_agent
        self._timestamps[key] = datetime.utcnow()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def get_source(self, key):
        return self._sources.get(key, 'unknown')

    def keys(self):
        return self._data.keys()

    def add_call(self, agent_name, status, duration_ms, input_keys, output_keys):
        self.call_chain.append({
            'agent': agent_name,
            'status': status,
            'duration_ms': round(duration_ms, 2),
            'input_keys': input_keys,
            'output_keys': output_keys,
            'timestamp': datetime.utcnow().isoformat()
        })

    def add_workflow_step(self, step_name, agent_name, status, duration_ms):
        self.call_chain.append({
            'step': step_name,
            'agent': agent_name,
            'type': 'workflow_step',
            'status': status,
            'duration_ms': round(duration_ms, 2),
            'timestamp': datetime.utcnow().isoformat()
        })

    def add_tool_call(self, tool_name, status, duration_ms, params_snippet=''):
        self.call_chain.append({
            'tool': tool_name,
            'type': 'tool_call',
            'status': status,
            'duration_ms': round(duration_ms, 2),
            'params': params_snippet,
            'timestamp': datetime.utcnow().isoformat()
        })

    def recall(self, key, default=None):
        """Convenience: recall a memory from AgentMemory service."""
        if self._memory is None:
            from agents.memory import AgentMemoryService
            self._memory = AgentMemoryService()
        value = self._memory.recall(self.user_id, key)
        return value if value is not None else default

    def remember(self, key, value, memory_type='fact', source='inferred', confidence=0.8):
        """Convenience: store a memory via AgentMemory service."""
        if self._memory is None:
            from agents.memory import AgentMemoryService
            self._memory = AgentMemoryService()
        self._memory.remember(self.user_id, key, value, memory_type, source, confidence)

    @property
    def llm(self):
        """Lazy-load LLMClient."""
        if self._llm is None:
            from services.llm_client import get_llm_client
            self._llm = get_llm_client()
        return self._llm

    @property
    def tools(self):
        """Lazy-load ToolRegistry."""
        if self._tools is None:
            from agents.tools import get_tool_registry
            self._tools = get_tool_registry()
        return self._tools

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'request_id': self.request_id,
            'data_keys': list(self._data.keys()),
            'call_chain': self.call_chain
        }


class AgentResult:
    """Uniform return type from every agent."""

    def __init__(self, success, data=None, error='', agent_name='', duration_ms=0):
        self.success = success
        self.data = data or {}
        self.error = error
        self.agent_name = agent_name
        self.duration_ms = duration_ms

    def to_dict(self):
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'agent': self.agent_name,
            'duration_ms': self.duration_ms
        }


class BaseAgent(ABC):
    """Abstract base for all agents."""

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def description(self):
        pass

    @property
    @abstractmethod
    def capabilities(self):
        pass

    @abstractmethod
    def execute(self, context, **kwargs):
        """Execute the agent's primary action. Returns AgentResult."""
        pass

    def _record_call(self, context, status, duration_ms, input_keys, output_keys):
        context.add_call(self.name, status, duration_ms, input_keys, output_keys)
