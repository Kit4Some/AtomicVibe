"""Supervisor sub-roles for the Execute Engine."""

from architect.execute.supervisor.assigner import assign_tasks
from architect.execute.supervisor.diagnostician import diagnose
from architect.execute.supervisor.planner import plan_sprint
from architect.execute.supervisor.reviewer import review_code
from architect.execute.supervisor.strategist import strategize

__all__ = [
    "assign_tasks",
    "diagnose",
    "plan_sprint",
    "review_code",
    "strategize",
]
