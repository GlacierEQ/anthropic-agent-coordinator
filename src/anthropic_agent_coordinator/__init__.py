"""Deterministic, budget-aware specialist task coordination."""

from .continuation import (
    CONTINUATION_SCHEMA,
    ContinuationResult,
    build_continuation_plan,
    continue_coordinate,
)
from .coordinator import (
    DEFAULT_ROLE_CAPS,
    Assignment,
    CoordinationError,
    CoordinationResult,
    DeferralReason,
    DeferredTask,
    Role,
    SchedulingPolicy,
    Task,
    build_plan,
    coordinate,
)
from .tool_proposal import (
    MAX_PROPOSAL_ARGUMENT_BYTES,
    PROPOSAL_SCHEMA,
    ToolProposal,
    ToolProposalError,
    bind_tool_proposals,
)

__all__ = [
    "CONTINUATION_SCHEMA",
    "DEFAULT_ROLE_CAPS",
    "MAX_PROPOSAL_ARGUMENT_BYTES",
    "PROPOSAL_SCHEMA",
    "Assignment",
    "ContinuationResult",
    "CoordinationError",
    "CoordinationResult",
    "DeferralReason",
    "DeferredTask",
    "Role",
    "SchedulingPolicy",
    "Task",
    "ToolProposal",
    "ToolProposalError",
    "bind_tool_proposals",
    "build_continuation_plan",
    "build_plan",
    "continue_coordinate",
    "coordinate",
]
