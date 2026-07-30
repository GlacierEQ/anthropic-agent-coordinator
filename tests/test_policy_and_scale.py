from __future__ import annotations

import pytest

from anthropic_agent_coordinator import (
    CoordinationError,
    DeferralReason,
    Role,
    SchedulingPolicy,
    Task,
    build_plan,
)


def test_stable_priority_is_explicit_even_when_it_does_not_repack_budget() -> None:
    tasks = (
        Task("highest-priority", Role.EXPLORE, 2_500),
        Task("second", Role.EXPLORE, 2_000),
        Task("third", Role.EXPLORE, 2_000),
    )

    result = build_plan(
        tasks,
        global_budget=10_000,
        role_caps={Role.EXPLORE: 4_000},
    )

    assert result.scheduling_policy is SchedulingPolicy.STABLE_PRIORITY
    assert [assignment.task_id for assignment in result.assignments] == ["highest-priority"]
    assert [task.reason for task in result.deferred] == [
        DeferralReason.ROLE_CAPACITY,
        DeferralReason.ROLE_CAPACITY,
    ]
    assert result.used_tokens == 2_500
    assert result.to_dict()["scheduling_policy"] == "stable_priority"


def test_unsupported_scheduling_policy_is_rejected() -> None:
    with pytest.raises(CoordinationError, match="unsupported scheduling policy"):
        build_plan(
            (Task("a", Role.EXPLORE, 1),),
            policy="pack-for-utilization",
        )


def test_unordered_dependency_collections_are_rejected() -> None:
    with pytest.raises(CoordinationError, match="ordered collection of strings"):
        Task(
            "dependent",
            Role.PLAN,
            1,
            deps={"first", "second"},  # type: ignore[arg-type]
        )
