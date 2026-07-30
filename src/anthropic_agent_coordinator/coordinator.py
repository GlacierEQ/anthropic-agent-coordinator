from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

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


class SchedulingPolicy(StrEnum):
    """Supported deterministic task-order policies."""

    STABLE_PRIORITY = "stable_priority"


DEFAULT_ROLE_CAPS: Final[Mapping[Role, int]] = MappingProxyType(
    {
        Role.EXPLORE: 4_000,
        Role.PLAN: 3_000,
        Role.IMPLEMENT: 8_000,
        Role.REVIEW: 2_500,
    }
)


def _require_positive_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CoordinationError(f"{label} must be a positive integer")
    return value


def _normalize_policy(policy: SchedulingPolicy | str) -> SchedulingPolicy:
    try:
        return policy if isinstance(policy, SchedulingPolicy) else SchedulingPolicy(policy)
    except (TypeError, ValueError) as exc:
        raise CoordinationError(f"unsupported scheduling policy: {policy!r}") from exc


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    role: Role
    tokens_est: int
    deps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise CoordinationError("task id must be a string")
        task_id = self.id.strip()
        if not task_id:
            raise CoordinationError("task id must be non-empty")

        try:
            role = self.role if isinstance(self.role, Role) else Role(self.role)
        except (TypeError, ValueError) as exc:
            raise CoordinationError(f"task {task_id!r} has unsupported role {self.role!r}") from exc

        tokens_est = _require_positive_integer(
            self.tokens_est,
            f"task {task_id!r} tokens_est",
        )

        if isinstance(self.deps, (str, bytes)) or not isinstance(self.deps, Sequence):
            raise CoordinationError(
                f"task {task_id!r} dependencies must be an ordered collection of strings"
            )
        raw_dependencies = tuple(self.deps)
        if not all(isinstance(dependency, str) for dependency in raw_dependencies):
            raise CoordinationError(f"task {task_id!r} dependencies must be strings")

        dependencies = tuple(dependency.strip() for dependency in raw_dependencies)
        if any(not dependency for dependency in dependencies):
            raise CoordinationError(f"task {task_id!r} contains an empty dependency id")
        if len(set(dependencies)) != len(dependencies):
            raise CoordinationError(f"task {task_id!r} contains duplicate dependencies")
        if task_id in dependencies:
            raise CoordinationError(f"task {task_id!r} cannot depend on itself")

        object.__setattr__(self, "id", task_id)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "tokens_est", tokens_est)
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
    scheduling_policy: SchedulingPolicy

    @property
    def complete(self) -> bool:
        return not self.deferred

    @property
    def remaining_tokens(self) -> int:
        return self.global_budget - self.used_tokens

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": RESULT_SCHEMA,
            "scheduling_policy": self.scheduling_policy.value,
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
    if not all(isinstance(task, Task) for task in normalized):
        raise CoordinationError("tasks must contain Task instances")
    if not normalized:
        return normalized

    counts = Counter(task.id for task in normalized)
    duplicates = sorted(task_id for task_id, count in counts.items() if count > 1)
    if duplicates:
        raise CoordinationError(f"duplicate task ids: {duplicates}")

    known = set(counts)
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

    for start in normalized:
        if state.get(start.id) == 2:
            continue

        stack: list[tuple[str, int]] = [(start.id, 0)]
        path: list[str] = []
        path_positions: dict[str, int] = {}
        while stack:
            task_id, dependency_index = stack[-1]
            if state.get(task_id, 0) == 0:
                state[task_id] = 1
                path_positions[task_id] = len(path)
                path.append(task_id)

            dependencies = task_by_id[task_id].deps
            if dependency_index >= len(dependencies):
                state[task_id] = 2
                stack.pop()
                path.pop()
                path_positions.pop(task_id)
                continue

            dependency = dependencies[dependency_index]
            stack[-1] = (task_id, dependency_index + 1)
            dependency_state = state.get(dependency, 0)
            if dependency_state == 0:
                stack.append((dependency, 0))
            elif dependency_state == 1:
                cycle_start = path_positions[dependency]
                cycle = [*path[cycle_start:], dependency]
                raise CoordinationError("dependency cycle: " + " -> ".join(cycle))

    return normalized


def _normalize_role_caps(role_caps: Mapping[Role | str, int] | None) -> dict[Role, int]:
    normalized = dict(DEFAULT_ROLE_CAPS)
    if role_caps is None:
        return normalized

    for raw_role, raw_capacity in role_caps.items():
        try:
            role = raw_role if isinstance(raw_role, Role) else Role(raw_role)
        except (TypeError, ValueError) as exc:
            raise CoordinationError(f"unsupported role capacity key: {raw_role!r}") from exc
        normalized[role] = _require_positive_integer(
            raw_capacity,
            f"role capacity for {role.value!r}",
        )
    return normalized


def build_plan(
    tasks: Sequence[Task],
    *,
    global_budget: int = 12_000,
    role_caps: Mapping[Role | str, int] | None = None,
    policy: SchedulingPolicy | str = SchedulingPolicy.STABLE_PRIORITY,
) -> CoordinationResult:
    """Build a deterministic full-funding plan under explicit stable priority.

    Declaration order is the priority order among tasks that become ready in the
    same wave. Tasks are assigned only when their full estimate fits both the
    remaining global budget and aggregate role capacity. Deferred prerequisites
    never unlock downstream work.
    """

    budget = _require_positive_integer(global_budget, "global_budget")
    scheduling_policy = _normalize_policy(policy)
    ordered_tasks = _validate_tasks(tasks)
    caps = _normalize_role_caps(role_caps)
    usage = {role: 0 for role in Role}
    task_by_id = {task.id: task for task in ordered_tasks}
    input_index = {task.id: index for index, task in enumerate(ordered_tasks)}
    unresolved_dependencies = {task.id: len(task.deps) for task in ordered_tasks}
    dependents: dict[str, list[str]] = {task.id: [] for task in ordered_tasks}
    for task in ordered_tasks:
        for dependency in task.deps:
            dependents[dependency].append(task.id)

    ready = [task.id for task in ordered_tasks if not task.deps]
    pending = set(task_by_id)
    completed: set[str] = set()
    assignments: list[Assignment] = []
    deferred: list[DeferredTask] = []
    used_tokens = 0
    wave = 0

    while ready:
        wave += 1
        next_ready: list[str] = []
        for task_id in ready:
            task = task_by_id[task_id]
            pending.remove(task_id)
            remaining_global = budget - used_tokens
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

            for dependent_id in dependents[task.id]:
                unresolved_dependencies[dependent_id] -= 1
                if unresolved_dependencies[dependent_id] == 0:
                    next_ready.append(dependent_id)

        ready = sorted(next_ready, key=input_index.__getitem__)

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
                remaining_global_budget=budget - used_tokens,
                remaining_role_capacity=caps[task.role] - usage[task.role],
            )
        )

    return CoordinationResult(
        assignments=tuple(assignments),
        deferred=tuple(deferred),
        used_tokens=used_tokens,
        global_budget=budget,
        role_usage=tuple((role, usage[role]) for role in Role),
        role_caps=tuple((role, caps[role]) for role in Role),
        scheduling_policy=scheduling_policy,
    )


def coordinate(
    tasks: Sequence[Task],
    global_budget: int = 12_000,
    *,
    role_caps: Mapping[Role | str, int] | None = None,
    policy: SchedulingPolicy | str = SchedulingPolicy.STABLE_PRIORITY,
) -> dict[str, object]:
    """Compatibility wrapper returning the machine-readable result dictionary."""

    return build_plan(
        tasks,
        global_budget=global_budget,
        role_caps=role_caps,
        policy=policy,
    ).to_dict()
