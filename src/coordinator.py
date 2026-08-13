#!/usr/bin/env python3
"""Compatibility entry point for the typed coordinator package."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from anthropic_agent_coordinator import (
    DEFAULT_ROLE_CAPS,
    Assignment,
    CoordinationError,
    CoordinationResult,
    DeferralReason,
    DeferredTask,
    Role,
    SchedulingPolicy,
    build_plan,
)
from anthropic_agent_coordinator import Task as CanonicalTask
from anthropic_agent_coordinator import coordinate as canonical_coordinate
from anthropic_agent_coordinator.__main__ import main

ROLE_CAPS: Final = {role.value: capacity for role, capacity in DEFAULT_ROLE_CAPS.items()}


@dataclass
class Task:
    """Historical task declaration retained for source and wheel callers."""

    id: str
    kind: str
    tokens_est: int
    deps: list[str] = field(default_factory=list)


def coordinate(tasks: list[Task | CanonicalTask], global_budget: int = 12_000) -> dict:
    """Return the historical result shape using the canonical scheduling engine."""

    normalized = tuple(
        task
        if isinstance(task, CanonicalTask)
        else CanonicalTask(task.id, task.kind, task.tokens_est, deps=tuple(task.deps))
        for task in tasks
    )
    result = canonical_coordinate(normalized, global_budget=global_budget)
    return {
        "assignments": [
            {
                "task": assignment["task"],
                "role": assignment["role"],
                "tokens": assignment["tokens"],
            }
            for assignment in result["assignments"]
        ],
        "used_tokens": result["used_tokens"],
        "deferred": [deferred["task"] for deferred in result["deferred"]],
    }


__all__ = [
    "DEFAULT_ROLE_CAPS",
    "ROLE_CAPS",
    "Assignment",
    "CanonicalTask",
    "CoordinationError",
    "CoordinationResult",
    "DeferralReason",
    "DeferredTask",
    "Role",
    "SchedulingPolicy",
    "Task",
    "build_plan",
    "coordinate",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
