#!/usr/bin/env python3
"""Compatibility entry point for the typed coordinator package."""

from __future__ import annotations

from anthropic_agent_coordinator import (
    DEFAULT_ROLE_CAPS,
    Assignment,
    CoordinationError,
    CoordinationResult,
    DeferredTask,
    DeferralReason,
    Role,
    SchedulingPolicy,
    Task,
    build_plan,
    coordinate,
)
from anthropic_agent_coordinator.__main__ import main

__all__ = [
    "DEFAULT_ROLE_CAPS",
    "Assignment",
    "CoordinationError",
    "CoordinationResult",
    "DeferredTask",
    "DeferralReason",
    "Role",
    "SchedulingPolicy",
    "Task",
    "build_plan",
    "coordinate",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
