from __future__ import annotations

import pytest

from anthropic_agent_coordinator import (
    CONTINUATION_SCHEMA,
    CoordinationError,
    Role,
    Task,
    build_continuation_plan,
    continue_coordinate,
)


def test_continuation_resumes_after_dependency_closed_checkpoint() -> None:
    tasks = (
        Task("discover", Role.EXPLORE, 500),
        Task("design", Role.PLAN, 500, deps=("discover",)),
        Task("build", Role.IMPLEMENT, 1_000, deps=("design",)),
        Task("review", Role.REVIEW, 250, deps=("build",)),
    )
    result = build_continuation_plan(
        tasks,
        completed_task_ids=("discover", "design"),
        global_budget=2_000,
    )
    assert [item.task_id for item in result.plan.assignments] == ["build", "review"]
    assert [item.wave for item in result.plan.assignments] == [1, 2]
    assert result.plan.used_tokens == 1_250
    assert result.completed_before == ("discover", "design")
    assert len(result.checkpoint_sha256) == 64


def test_completed_work_is_not_recharged_against_continuation_budget() -> None:
    tasks = (
        Task("expensive", Role.IMPLEMENT, 7_000),
        Task("review", Role.REVIEW, 500, deps=("expensive",)),
    )
    result = build_continuation_plan(
        tasks,
        completed_task_ids=("expensive",),
        global_budget=500,
    )
    assert [item.task_id for item in result.plan.assignments] == ["review"]
    assert result.plan.used_tokens == 500


def test_checkpoint_must_be_dependency_closed() -> None:
    tasks = (
        Task("discover", Role.EXPLORE, 100),
        Task("design", Role.PLAN, 100, deps=("discover",)),
    )
    with pytest.raises(CoordinationError, match="not dependency-closed"):
        build_continuation_plan(tasks, completed_task_ids=("design",))


def test_unknown_and_duplicate_completed_ids_fail_closed() -> None:
    tasks = (Task("a", Role.EXPLORE, 100),)
    with pytest.raises(CoordinationError, match="unknown completed task ids"):
        build_continuation_plan(tasks, completed_task_ids=("missing",))
    with pytest.raises(CoordinationError, match="contains duplicates"):
        build_continuation_plan(tasks, completed_task_ids=("a", "a"))


def test_checkpoint_hash_is_order_sensitive_and_deterministic() -> None:
    tasks = (
        Task("a", Role.EXPLORE, 100),
        Task("b", Role.PLAN, 100),
    )
    first = build_continuation_plan(tasks, completed_task_ids=("a", "b"))
    repeat = build_continuation_plan(tasks, completed_task_ids=("a", "b"))
    reversed_checkpoint = build_continuation_plan(tasks, completed_task_ids=("b", "a"))
    assert first.checkpoint_sha256 == repeat.checkpoint_sha256
    assert first.checkpoint_sha256 != reversed_checkpoint.checkpoint_sha256


def test_machine_wrapper_emits_continuation_contract() -> None:
    payload = continue_coordinate(
        (
            Task("a", Role.EXPLORE, 100),
            Task("b", Role.PLAN, 100, deps=("a",)),
        ),
        completed_task_ids=("a",),
        global_budget=100,
    )
    assert payload["schema"] == CONTINUATION_SCHEMA
    assert payload["completed_before"] == ["a"]
    assert payload["plan"]["complete"] is True
    assert payload["plan"]["assignments"][0]["task"] == "b"
