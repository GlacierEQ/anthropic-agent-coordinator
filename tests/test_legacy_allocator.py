from __future__ import annotations

import coordinator as compatibility
from agent_coordinator import Agent, AgentCoordinator, Task


def test_legacy_positional_constructor_layout_is_preserved() -> None:
    agent = Agent("agent-1", ["code"], 0.1, 1.0, 0.9)
    task = Task("task-1", ["code"], 7, 0.2)

    assert agent.agent_id == "agent-1"
    assert agent.capabilities == ["code"]
    assert agent.current_load == 0.1
    assert agent.max_load == 1.0
    assert agent.trust_score == 0.9
    assert task.task_id == "task-1"
    assert task.required_capabilities == ["code"]
    assert task.priority == 7
    assert task.estimated_load == 0.2


def test_task_is_not_assigned_to_agent_without_required_capability() -> None:
    coordinator = AgentCoordinator()
    coordinator.register_agent(Agent("data-agent", ["data"], 0.0, 1.0))

    assigned = coordinator.assign_task(Task("code-task", ["code"], 1, 0.2))

    assert assigned is None
    assert coordinator.agents["data-agent"].current_load == 0.0
    assert coordinator.get_status()["assignments"] == 0


def test_empty_capability_requirement_can_use_available_agent() -> None:
    coordinator = AgentCoordinator()
    coordinator.register_agent(Agent("general-agent", [], 0.0, 1.0))

    assigned = coordinator.assign_task(Task("general-task", [], 1, 0.2))

    assert assigned == "general-agent"
    assert coordinator.agents["general-agent"].current_load == 0.2


def test_repeated_assignment_of_same_task_is_idempotent() -> None:
    coordinator = AgentCoordinator()
    coordinator.register_agent(Agent("code-agent", ["code"], 0.0, 1.0))
    task = Task("same-task", ["code"], 1, 0.25)

    first = coordinator.assign_task(task)
    load_after_first = coordinator.agents["code-agent"].current_load
    second = coordinator.assign_task(task)

    assert first == "code-agent"
    assert second == first
    assert coordinator.agents["code-agent"].current_load == load_after_first
    assert coordinator.get_status()["assignments"] == 1


def test_historical_coordinator_exports_and_result_shape_are_preserved() -> None:
    tasks = [
        compatibility.Task("discover", "explore", 1_000),
        compatibility.Task("plan", "plan", 1_000, deps=["discover"]),
    ]

    result = compatibility.coordinate(tasks, global_budget=3_000)

    assert compatibility.ANSWER == 42
    assert compatibility.ROLE_CAPS["explore"] == 4_000
    assert result == {
        "assignments": [
            {"task": "discover", "role": "explore", "tokens": 1_000},
            {"task": "plan", "role": "plan", "tokens": 1_000},
        ],
        "used_tokens": 2_000,
        "deferred": [],
        "answer": compatibility.ANSWER,
    }
