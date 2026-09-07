from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from json import dumps
from typing import Final

from .coordinator import (
    CoordinationError,
    CoordinationResult,
    Role,
    SchedulingPolicy,
    Task,
    build_plan,
)

CONTINUATION_SCHEMA: Final = "glaciereq.agent-coordinator.continuation.v1"


@dataclass(frozen=True, slots=True)
class ContinuationResult:
    completed_before: tuple[str, ...]
    checkpoint_sha256: str
    plan: CoordinationResult

    @property
    def complete(self) -> bool:
        return self.plan.complete

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": CONTINUATION_SCHEMA,
            "completed_before": list(self.completed_before),
            "checkpoint_sha256": self.checkpoint_sha256,
            "plan": self.plan.to_dict(),
        }


def _normalize_completed(tasks: tuple[Task, ...], completed_task_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(completed_task_ids, (str, bytes)):
        raise CoordinationError("completed_task_ids must be an ordered collection of strings")
    completed = tuple(completed_task_ids)
    if not all(isinstance(task_id, str) for task_id in completed):
        raise CoordinationError("completed_task_ids must contain strings")
    completed = tuple(task_id.strip() for task_id in completed)
    if any(not task_id for task_id in completed):
        raise CoordinationError("completed_task_ids cannot contain empty ids")
    if len(set(completed)) != len(completed):
        raise CoordinationError("completed_task_ids contains duplicates")

    task_by_id = {task.id: task for task in tasks}
    unknown = sorted(set(completed) - set(task_by_id))
    if unknown:
        raise CoordinationError(f"unknown completed task ids: {unknown}")

    completed_set = set(completed)
    for task_id in completed:
        missing = tuple(dep for dep in task_by_id[task_id].deps if dep not in completed_set)
        if missing:
            raise CoordinationError(
                f"completed task {task_id!r} is not dependency-closed; missing completed deps: {missing}"
            )
    return completed


def _checkpoint_hash(completed: tuple[str, ...]) -> str:
    payload = dumps({"schema": CONTINUATION_SCHEMA, "completed_before": completed}, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def build_continuation_plan(
    tasks: Sequence[Task],
    *,
    completed_task_ids: Sequence[str],
    global_budget: int = 12_000,
    role_caps: Mapping[Role | str, int] | None = None,
    policy: SchedulingPolicy | str = SchedulingPolicy.STABLE_PRIORITY,
) -> ContinuationResult:
    """Resume a validated DAG from a dependency-closed completion checkpoint.

    Completed tasks are treated as authoritative prior work and are not charged
    against the continuation budget. Their dependency edges are removed from
    remaining tasks before the canonical deterministic scheduler runs.
    """
    normalized_tasks = tuple(tasks)
    completed = _normalize_completed(normalized_tasks, completed_task_ids)
    completed_set = set(completed)
    remaining = tuple(
        Task(
            task.id,
            task.role,
            task.tokens_est,
            deps=tuple(dep for dep in task.deps if dep not in completed_set),
        )
        for task in normalized_tasks
        if task.id not in completed_set
    )
    plan = build_plan(
        remaining,
        global_budget=global_budget,
        role_caps=role_caps,
        policy=policy,
    )
    return ContinuationResult(
        completed_before=completed,
        checkpoint_sha256=_checkpoint_hash(completed),
        plan=plan,
    )


def continue_coordinate(
    tasks: Sequence[Task],
    *,
    completed_task_ids: Sequence[str],
    global_budget: int = 12_000,
    role_caps: Mapping[Role | str, int] | None = None,
    policy: SchedulingPolicy | str = SchedulingPolicy.STABLE_PRIORITY,
) -> dict[str, object]:
    return build_continuation_plan(
        tasks,
        completed_task_ids=completed_task_ids,
        global_budget=global_budget,
        role_caps=role_caps,
        policy=policy,
    ).to_dict()
