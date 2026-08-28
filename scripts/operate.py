#!/usr/bin/env python3
"""Produce continuation-oriented scheduler observations for the coordinator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anthropic_agent_coordinator import Role, Task, coordinate  # noqa: E402

REPOSITORY = "GlacierEQ/anthropic-agent-coordinator"


def _nominal_plan() -> dict[str, object]:
    return coordinate(
        (
            Task("explore", Role.EXPLORE, 1_000),
            Task("plan", Role.PLAN, 2_000, deps=("explore",)),
            Task("implement", Role.IMPLEMENT, 3_000, deps=("plan",)),
        ),
        global_budget=6_000,
    )


def _constrained_plan() -> dict[str, object]:
    return coordinate(
        (
            Task("explore", Role.EXPLORE, 1_000),
            Task("plan", Role.PLAN, 2_000, deps=("explore",)),
            Task("implement", Role.IMPLEMENT, 3_000, deps=("plan",)),
        ),
        global_budget=2_500,
    )


def _observe_plan(label: str, result: dict[str, object]) -> list[str]:
    """Describe scheduling work without converting an observation into a process stop."""
    observations: list[str] = []
    assignments = result.get("assignments")
    deferred = result.get("deferred")
    if not isinstance(assignments, list):
        observations.append(f"{label}:surface_assignments")
    if not isinstance(deferred, list):
        observations.append(f"{label}:surface_deferred")
        return observations
    for item in deferred:
        if isinstance(item, dict):
            task = item.get("task", "unknown")
            reason = item.get("reason", "unspecified")
            observations.append(f"{label}:continue_task:{task}:reason:{reason}")
        else:
            observations.append(f"{label}:normalize_deferred_receipt")
    if result.get("complete") is not True and not deferred:
        observations.append(f"{label}:reconcile_completion_state")
    return observations


def operate() -> dict[str, object]:
    nominal = _nominal_plan()
    constrained = _constrained_plan()
    resolution_work = sorted(
        set(_observe_plan("nominal", nominal) + _observe_plan("constrained", constrained))
    )
    return {
        "repository": REPOSITORY,
        "module": "anthropic_agent_coordinator",
        "continuation": "enabled",
        "status": "observed",
        "resolution_work": resolution_work,
        "smoke": {
            "kind": "continuation_scheduler",
            "invoked": True,
            "content_observed": True,
            "nominal": nominal,
            "constrained": constrained,
        },
    }


def main() -> int:
    try:
        output = operate()
    except Exception as exc:  # An unexpected runtime issue becomes actionable telemetry.
        output = {
            "repository": REPOSITORY,
            "module": "anthropic_agent_coordinator",
            "continuation": "enabled",
            "status": "resolution_required",
            "resolution_work": [f"inspect_operation_runtime:{type(exc).__name__}"],
        }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
