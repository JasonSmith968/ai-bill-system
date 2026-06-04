"""Multi-agent system package."""

_manager = None


def get_manager():
    """Get or create the singleton AgentManager instance."""
    global _manager
    if _manager is None:
        from agents.manager import AgentManager
        _manager = AgentManager()
    return _manager


# Convenience re-exports for easy importing
def get_router():
    return get_manager().router


def get_workflow_engine():
    from agents.workflow import get_workflow_engine as _get
    return _get()


def get_tool_registry():
    from agents.tools import get_tool_registry as _get
    return _get()


def get_prompt_manager():
    from agents.prompt_manager import get_prompt_manager as _get
    return _get()
