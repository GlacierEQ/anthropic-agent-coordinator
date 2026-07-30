from __future__ import annotations

import pytest

from anthropic_agent_coordinator import (
    DEFAULT_ROLE_CAPS,
    CoordinationError,
    DeferralReason,
    Role,
    Task,
    build_plan,
    coordinate,
)


def assignment_ids(result) -> list[str]:
    return [assignment.task_id for assignment in result.assignments]


def deferred_by_id(result) -> dict[str, object]:
    return {task.task_id: task for task in result.deferred}


def test_dependency_chain_executes_in_stable_waves() -> None:
    tasks = (
        Task("discover", Role.EXPLORE, 1_000),
        Task("design", Role.PLAN, 1_000, deps=("discover",)),
        Task("build", Role.IMPLEMENT, 2_000, deps=("design",)),
        Task("review", Role.REVIEW, 500, deps=("build",)),
    )

    result = build_plan(tasks, global_budget=5_000)

    assert assignment_ids(result) == ["discover", "design", "build", "review"]
    assert [assignment.wave for assignment in result.assignments] == [1, 2, 3, 4]
    assert result.complete is True
    assert result.used_tokens == 4_500
    assert result.remaining_tokens == 500


def test_independent_tasks_share_a_wave_in_input_order() -> None:
    tasks = (
        Task("first", Role.EXPLORE, 500),
        Task("second", Role.PLAN, 500),
        Task("third", Role.REVIEW, 500),
    )

    result = build_plan(tasks)

    assert assignment_ids(result) == ["first", "second", "third"]
    assert [assignment.wave for assignment in result.assignments] == [1, 1, 1]


def test_task_is_never_partially_funded_or_marked_complete() -> None:
    tasks = (
        Task("oversized", Role.IMPLEMENT, 6_000),
        Task("downstream", Role.REVIEW, 500, deps=("oversized",)),
    )

    result = build_plan(tasks, global_budget=5_000)
    deferred = deferred_by_id(result)

    assert result.assignments == ()
    assert deferred["oversized"].reason is DeferralReason.GLOBAL_BUDGET
    assert deferred["oversized"].remaining_global_budget == 5_000
    assert deferred["downstream"].reason is DeferralReason.DEPENDENCY_NOT_COMPLETED
    assert deferred["downstream"].blocking_dependencies == ("oversized",)


def test_role_capacity_is_aggregate_across_tasks() -> None:
    tasks = (
        Task("explore-a", Role.EXPLORE, 2_500),
        Task("explore-b", Role.EXPLORE, 2_000),
    )

    result = build_plan(tasks, global_budget=10_000)
    deferred = deferred_by_id(result)

    assert assignment_ids(result) == ["explore-a"]
    assert deferred["explore-b"].reason is DeferralReason.ROLE_CAPACITY
    assert deferred["explore-b"].remaining_role_capacity == 1_500
    assert dict(result.role_usage)[Role.EXPLORE] == 2_500


def test_custom_role_capacity_is_applied_without_mutating_defaults() -> None:
    task = Task("large-review", Role.REVIEW, 3_000)

    default_result = build_plan((task,), global_budget=5_000)
    custom_result = build_plan(
        (task,),
        global_budget=5_000,
        role_caps={Role.REVIEW: 4_000},
    )

    assert default_result.deferred[0].reason is DeferralReason.ROLE_CAPACITY
    assert assignment_ids(custom_result) == ["large-review"]
    assert DEFAULT_ROLE_CAPS[Role.REVIEW] == 2_500


def test_default_role_cap_mapping_is_runtime_immutable() -> None:
    with pytest.raises(TypeError):
        DEFAULT_ROLE_CAPS[Role.EXPLORE] = 1  # type: ignore[index]


def test_global_budget_is_shared_across_roles() -> None:
    tasks = (
        Task("explore", Role.EXPLORE, 2_000),
        Task("plan", Role.PLAN, 2_000),
        Task("review", Role.REVIEW, 1_000),
    )

    result = build_plan(tasks, global_budget=4_500)
    deferred = deferred_by_id(result)

    assert assignment_ids(result) == ["explore", "plan"]
    assert deferred["review"].reason is DeferralReason.GLOBAL_BUDGET
    assert deferred["review"].remaining_global_budget == 500


def test_empty_task_set_returns_a_complete_zero_usage_plan() -> None:
    result = build_plan((), global_budget=1_000)

    assert result.complete is True
    assert result.assignments == ()
    assert result.deferred == ()
    assert result.used_tokens == 0
    assert result.remaining_tokens == 1_000


def test_result_serialization_is_stable_and_machine_readable() -> None:
    payload = coordinate(
        (
            Task("a", "explore", 1_000),
            Task("b", "plan", 1_000, deps=("a",)),
        ),
        global_budget=3_000,
    )

    assert payload["schema"] == "glaciereq.agent-coordinator.result.v1"
    assert payload["scheduling_policy"] == "stable_priority"
    assert payload["complete"] is True
    assert payload["assignments"] == [
        {"task": "a", "role": "explore", "tokens": 1_000, "wave": 1},
        {"task": "b", "role": "plan", "tokens": 1_000, "wave": 2},
    ]
    assert payload["deferred"] == []


def test_duplicate_task_ids_are_rejected() -> None:
    tasks = (
        Task("same", Role.EXPLORE, 100),
        Task("same", Role.PLAN, 100),
    )

    with pytest.raises(CoordinationError, match="duplicate task ids"):
        build_plan(tasks)


def test_unknown_dependencies_are_rejected() -> None:
    task = Task("plan", Role.PLAN, 100, deps=("missing",))

    with pytest.raises(CoordinationError, match="unknown dependency ids"):
        build_plan((task,))


def test_dependency_cycles_are_rejected_with_a_trace() -> None:
    tasks = (
        Task("a", Role.EXPLORE, 100, deps=("c",)),
        Task("b", Role.PLAN, 100, deps=("a",)),
        Task("c", Role.REVIEW, 100, deps=("b",)),
    )

    with pytest.raises(CoordinationError, match=r"dependency cycle: .+ -> .+"):
        build_plan(tasks)


def test_deep_acyclic_chain_does_not_depend_on_python_recursion_depth() -> None:
    task_count = 1_200
    tasks = tuple(
        Task(
            f"task-{index}",
            Role.EXPLORE,
            1,
            deps=(f"task-{index - 1}",) if index else (),
        )
        for index in range(task_count)
    )

    result = build_plan(
        tasks,
        global_budget=task_count,
        role_caps={Role.EXPLORE: task_count},
    )

    assert result.complete is True
    assert len(result.assignments) == task_count
    assert result.assignments[-1].wave == task_count


def test_reverse_declared_deep_chain_is_supported_without_recursion() -> None:
    task_count = 1_200
    tasks = tuple(
        Task(
            f"task-{index}",
            Role.EXPLORE,
            1,
            deps=(f"task-{index - 1}",) if index else (),
        )
        for index in reversed(range(task_count))
    )

    result = build_plan(
        tasks,
        global_budget=task_count,
        role_caps={Role.EXPLORE: task_count},
    )

    assert result.complete is True
    assert len(result.assignments) == task_count
    assert result.assignments[0].task_id == "task-0"
    assert result.assignments[-1].task_id == f"task-{task_count - 1}"


@pytest.mark.parametrize("task_id", ["", "   "])
def test_empty_task_ids_are_rejected(task_id: str) -> None:
    with pytest.raises(CoordinationError, match="task id must be non-empty"):
        Task(task_id, Role.EXPLORE, 100)


def test_non_string_ids_and_dependencies_are_rejected() -> None:
    with pytest.raises(CoordinationError, match="task id must be a string"):
        Task(7, Role.EXPLORE, 100)  # type: ignore[arg-type]
    with pytest.raises(CoordinationError, match="dependencies must be strings"):
        Task("a", Role.EXPLORE, 100, deps=(7,))  # type: ignore[arg-type]


@pytest.mark.parametrize("dependencies", ["discover", b"discover"])
def test_bare_string_dependency_collections_are_rejected(dependencies: object) -> None:
    with pytest.raises(CoordinationError, match="collection of strings"):
        Task("a", Role.EXPLORE, 100, deps=dependencies)  # type: ignore[arg-type]


def test_self_and_duplicate_dependencies_are_rejected() -> None:
    with pytest.raises(CoordinationError, match="cannot depend on itself"):
        Task("a", Role.EXPLORE, 100, deps=("a",))
    with pytest.raises(CoordinationError, match="duplicate dependencies"):
        Task("a", Role.EXPLORE, 100, deps=("b", "b"))


def test_task_collection_rejects_non_task_values() -> None:
    with pytest.raises(CoordinationError, match="tasks must contain Task instances"):
        build_plan(("not-a-task",))  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "100"])
def test_invalid_task_estimates_are_rejected(value: object) -> None:
    with pytest.raises(CoordinationError, match="tokens_est must be a positive integer"):
        Task("a", Role.EXPLORE, value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "100"])
def test_invalid_global_budgets_are_rejected(value: object) -> None:
    with pytest.raises(CoordinationError, match="global_budget must be a positive integer"):
        build_plan((Task("a", Role.EXPLORE, 100),), global_budget=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "100"])
def test_invalid_role_capacities_are_rejected(value: object) -> None:
    with pytest.raises(
        CoordinationError,
        match=r"role capacity.*must be a positive integer",
    ):
        build_plan(
            (Task("a", Role.EXPLORE, 100),),
            role_caps={Role.EXPLORE: value},  # type: ignore[dict-item]
        )


def test_unsupported_roles_are_rejected() -> None:
    with pytest.raises(CoordinationError, match="unsupported role"):
        Task("a", "invent", 100)  # type: ignore[arg-type]
