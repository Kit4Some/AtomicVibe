"""Execute Engine — Supervisor loop, dispatcher, and support modules."""

from architect.execute.dispatcher import dispatch, dispatch_parallel
from architect.execute.engine import ExecuteEngine
from architect.execute.fixer import apply_fix
from architect.execute.knowledge import KnowledgeManager
from architect.execute.states import ExecuteStateV2
from architect.execute.validator import all_passed, validate
from architect.execute.workspace import Workspace

__all__ = [
    "ExecuteEngine",
    "ExecuteStateV2",
    "KnowledgeManager",
    "Workspace",
    "all_passed",
    "apply_fix",
    "dispatch",
    "dispatch_parallel",
    "validate",
]
