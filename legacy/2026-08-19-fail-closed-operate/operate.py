#!/usr/bin/env python3
"""Cold-start the canonical coordinator and verify deterministic scheduler behavior."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from anthropic_agent_coordinator import (  # noqa: E402
    DeferralReason,
    Role,
    Task,
    coordinate,
)

REPOSITORY = "GlacierEQ/anthropic-agent-coordinator"


def _nominal_plan() -> dict[str, object]:
    tasks = (
        Task("explore", Role.EXPLORE, 1_000),
        Task("plan", Role.PLAN, 2_000, deps=("explore",)),
        Task("implement", Role.IMPLEMENT, 3_000, deps=("plan",)),
    )
    return coordinate(tasks, global_budget=6_000)


def _deferred_plan() -> dict[str, object]:
    tasks = (
        Task("explore", Role.EXPLORE, 1_000),
        Task("plan", Role.PLAN, 2_000, deps=("explore",)),
        Task("implement", Role.IMPLEMENT, 3_000, deps=("plan",)),
    )
    return coordinate(tasks, global_budget=2_500)


def _assert_nominal(result: dict[str, object]) -> None:
    assignments = result.get("assignments")
    if not isinstance(assignments, list):
        raise RuntimeError("nominal plan omitted assignments")
    if [item["task"] for item in assignments] != ["explore", "plan", "implement"]:
        raise RuntimeError("nominal plan changed stable dependency order")
    if [item["wave"] for item in assignments] != [1, 2, 3]:
        raise RuntimeError("nominal plan changed dependency waves")
    if result.get("used_tokens") != 6_000 or result.get("complete") is not True:
        raise RuntimeError("nominal plan changed full-funding accounting")
    if result.get("deferred") != []:
        raise RuntimeError("nominal plan unexpectedly deferred work")


def _assert_deferral(result: dict[str, object]) -> None:
    deferred = result.get("deferred")
    if not isinstance(deferred, list) or len(deferred) != 2:
        raise RuntimeError("bounded plan did not preserve both deferred tasks")
    by_task = {item["task"]: item for item in deferred}
    plan = by_task.get("plan")
    implement = by_task.get("implement")
    if plan is None or implement is None:
        raise RuntimeError("bounded plan lost dependency-linked deferrals")
    if plan.get("reason") != DeferralReason.GLOBAL_BUDGET.value:
        raise RuntimeError("plan task did not fail closed on global budget")
    if implement.get("reason") != DeferralReason.DEPENDENCY_NOT_COMPLETED.value:
        raise RuntimeError("dependent task was not blocked by deferred prerequisite")
    if implement.get("blocking_dependencies") != ["plan"]:
        raise RuntimeError("dependent task lost its blocking dependency")
    if result.get("used_tokens") != 1_000 or result.get("complete") is not False:
        raise RuntimeError("bounded plan changed non-completion accounting")


def operate() -> dict[str, object]:
    nominal = _nominal_plan()
    bounded = _deferred_plan()
    _assert_nominal(nominal)
    _assert_deferral(bounded)
    return {
        "repository": REPOSITORY,
        "module": "anthropic_agent_coordinator",
        "ok": True,
        "smoke": {
            "kind": "canonical_scheduler",
            "invoked": True,
            "content_checked": True,
            "nominal": nominal,
            "bounded": bounded,
        },
    }


def main() -> int:
    try:
        output = operate()
    except Exception as exc:
        output = {
            "repository": REPOSITORY,
            "module": "anthropic_agent_coordinator",
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        print(json.dumps(output, sort_keys=True))
        return 1
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
