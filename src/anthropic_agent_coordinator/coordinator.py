from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Mapping, Sequence

RESULT_SCHEMA: Final = "glaciereq.agent-coordinator.result.v1"


class CoordinationError(ValueError):
    """Raised when a task graph or resource policy cannot be coordinated safely."""


class Role(StrEnum):
    EXPLORE = "explore"
    PLAN = "plan"
    IMPLEMENT = "implement"
    REVIEW = "review"


class DeferralReason(StrEnum):
    GLOBAL_BUDGET = "global_budget"
    ROLE_CAPACITY = "role_capacity"
    DEPENDENCY_NOT_COMPLETED = "dependency_not_completed"


DEFAULT_ROLE_CAPS: Final[dict[Role, int]] = {
    Role.EXPLORE: 4_000,
    Role.PLAN: 3_000,
    Role.IMPLEMENT: 8_000,
    Role.REVIEW: 2_500,
}


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    role: Role
    tokens_est: int
    deps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        task_id = self.id.strip()
        if not task_id:
            raise CoordinationError("task id must be non-empty")
        try:
            role = self.role if isinstance(self.role, Role) else Role(self.role)
        except ValueError as exc:
            raise CoordinationError(f"task {task_id!r} has unsupported role {self.role!r}") from exc
        if isinstance(self.tokens_est, bool) or self.tokens_est <= 0:
            raise CoordinationError(f"task {task_id!r} tokens_est must be a positive integer")

        dependencies = tuple(dependency.strip() for dependency in self.deps)
        if any(not dependency for dependency in dependencies):
            raise CoordinationError(f"task {task_id!r} contains an empty dependency id")
        if len(set(dependencies)) != len(dependencies):
            raise CoordinationError(f"task {task_id!r} contains duplicate dependencies")
        if task_id in dependencies:
            raise CoordinationError(f"task {task_id!r} cannot depend on itself")

        object.__setattr__(self, "id", task_id)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "deps", dependencies)


@dataclass(frozen=True, slots=True)
class Assignment:
    task_id: str
    role: Role
    tokens: int
    wave: int

    def to_dict(self) -> dict[str, object]:
        return {
            "task": self.task_id,
            "role": self.role.value,
            "tokens": self.tokens,
            "wave": self.wave,
        }


@dataclass(frozen=True, slots=True)
class DeferredTask:
    task_id: str
    role: Role
    tokens_est: int
    reason: DeferralReason
    blocking_dependencies: tuple[str, ...] = ()
    remaining_global_budget: int = 0
    remaining_role_capacity: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "task": self.task_id,
            "role": self.role.value,
            "tokens_est": self.tokens_est,
            "reason": self.reason.value,
            "blocking_dependencies": list(self.blocking_dependencies),
            "remaining_global_budget": self.remaining_global_budget,
            "remaining_role_capacity": self.remaining_role_capacity,
        }


@dataclass(frozen=True, slots=True)
class CoordinationResult:
    assignments: tuple[Assignment, ...]
    deferred: tuple[DeferredTask, ...]
    used_tokens: int
    global_budget: int
    role_usage: tuple[tuple[Role, int], ...]
    role_caps: tuple[tuple[Role, int], ...]

    @property
    def complete(self) -> bool:
        return not self.deferred

    @property
    def remaining_tokens(self) -> int:
        return self.global_budget - self.used_tokens

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": RESULT_SCHEMA,
            "complete": self.complete,
            "global_budget": self.global_budget,
            "used_tokens": self.used_tokens,
            "remaining_tokens": self.remaining_tokens,
            "role_caps": {role.value: value for role, value in self.role_caps},
            "role_usage": {role.value: value for role, value in self.role_usage},
            "assignments": [assignment.to_dict() for assignment in self.assignments],
            "deferred": [task.to_dict() for task in self.deferred],
        }


def _validate_tasks(tasks: Sequence[Task]) -> tuple[Task, ...]:
    normalized = tuple(tasks)
    if not normalized:
        return normalized

    ids = [task.id for task in normalized]
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    if duplicates:
        raise CoordinationError(f"duplicate task ids: {duplicates}")

    known = set(ids)
    unknown = sorted(
        {
            dependency
            for task in normalized
            for dependency in task.deps
            if dependency not in known
        }
    )
    if unknown:
        raise CoordinationError(f"unknown dependency ids: {unknown}")

    task_by_id = {task.id: task for task in normalized}
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(task_id: str) -> None:
        marker = state.get(task_id, 0)
        if marker == 2:
            return
        if marker == 1:
            cycle_start = stack.index(task_id)
            cycle = [*stack[cycle_start:], task_id]
            raise CoordinationError("dependency cycle: " + " -> ".join(cycle))

        state[task_id] = 1
        stack.append(task_id)
        for dependency in task_by_id[task_id].deps:
            visit(dependency)
        stack.pop()
        state[task_id] = 2

    for task in normalized:
        visit(task.id)
    return normalized


def _normalize_role_caps(role_caps: Mapping[Role | str, int] | None) -> dict[Role, int]:
    normalized = dict(DEFAULT_ROLE_CAPS)
    if role_caps is None:
        return normalized

    for raw_role, capacity in role_caps.items():
        try:
            role = raw_role if isinstance(raw_role, Role) else Role(raw_role)
        except ValueError as exc:
            raise CoordinationError(f"unsupported role capacity key: {raw_role!r}") from exc
        if isinstance(capacity, bool) or capacity <= 0:
            raise CoordinationError(f"role capacity for {role.value!r} must be positive")
        normalized[role] = capacity
    return normalized


def build_plan(
    tasks: Sequence[Task],
    *,
    global_budget: int = 12_000,
    role_caps: Mapping[Role | str, int] | None = None,
) -> CoordinationResult:
    """Build a deterministic plan without treating partial funding as completion.

    Tasks are processed in stable input order. A task is assigned only when its full
    estimate fits both the remaining global budget and the remaining aggregate capacity
    for its role. Deferred prerequisites never unlock downstream work.
    """

    if isinstance(global_budget, bool) or global_budget <= 0:
        raise CoordinationError("global_budget must be a positive integer")

    ordered_tasks = _validate_tasks(tasks)
    caps = _normalize_role_caps(role_caps)
    usage = {role: 0 for role in Role}
    pending = {task.id: task for task in ordered_tasks}
    completed: set[str] = set()
    assignments: list[Assignment] = []
    deferred: list[DeferredTask] = []
    used_tokens = 0
    wave = 0

    while pending:
        ready = [
            task
            for task in ordered_tasks
            if task.id in pending and all(dependency in completed for dependency in task.deps)
        ]
        if not ready:
            break

        wave += 1
        for task in ready:
            pending.pop(task.id)
            remaining_global = global_budget - used_tokens
            remaining_role = caps[task.role] - usage[task.role]

            if task.tokens_est > remaining_global:
                deferred.append(
                    DeferredTask(
                        task_id=task.id,
                        role=task.role,
                        tokens_est=task.tokens_est,
                        reason=DeferralReason.GLOBAL_BUDGET,
                        remaining_global_budget=remaining_global,
                        remaining_role_capacity=remaining_role,
                    )
                )
                continue

            if task.tokens_est > remaining_role:
                deferred.append(
                    DeferredTask(
                        task_id=task.id,
                        role=task.role,
                        tokens_est=task.tokens_est,
                        reason=DeferralReason.ROLE_CAPACITY,
                        remaining_global_budget=remaining_global,
                        remaining_role_capacity=remaining_role,
                    )
                )
                continue

            assignments.append(
                Assignment(
                    task_id=task.id,
                    role=task.role,
                    tokens=task.tokens_est,
                    wave=wave,
                )
            )
            used_tokens += task.tokens_est
            usage[task.role] += task.tokens_est
            completed.add(task.id)

    for task in ordered_tasks:
        if task.id not in pending:
            continue
        blocking = tuple(dependency for dependency in task.deps if dependency not in completed)
        deferred.append(
            DeferredTask(
                task_id=task.id,
                role=task.role,
                tokens_est=task.tokens_est,
                reason=DeferralReason.DEPENDENCY_NOT_COMPLETED,
                blocking_dependencies=blocking,
                remaining_global_budget=global_budget - used_tokens,
                remaining_role_capacity=caps[task.role] - usage[task.role],
            )
        )

    return CoordinationResult(
        assignments=tuple(assignments),
        deferred=tuple(deferred),
        used_tokens=used_tokens,
        global_budget=global_budget,
        role_usage=tuple((role, usage[role]) for role in Role),
        role_caps=tuple((role, caps[role]) for role in Role),
    )


def coordinate(
    tasks: Sequence[Task],
    global_budget: int = 12_000,
    *,
    role_caps: Mapping[Role | str, int] | None = None,
) -> dict[str, object]:
    """Compatibility wrapper returning the machine-readable result dictionary."""

    return build_plan(tasks, global_budget=global_budget, role_caps=role_caps).to_dict()
