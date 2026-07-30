"""Legacy capability-matching allocator retained as a source-only example.

The package-quality dependency and budget scheduler lives in
``anthropic_agent_coordinator``. This module preserves the earlier independent
agent-capability experiment without presenting it as the canonical runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class Agent:
    agent_id: str
    capabilities: list[str]
    current_load: float
    max_load: float
    trust_score: float = 1.0

    @property
    def available_capacity(self) -> float:
        return max(0.0, self.max_load - self.current_load)

    @property
    def can_accept_work(self) -> bool:
        return self.available_capacity > 0.1


@dataclass
class Task:
    task_id: str
    required_capabilities: list[str]
    priority: int
    estimated_load: float


class AgentCoordinator:
    def __init__(self) -> None:
        self.agents: dict[str, Agent] = {}
        self._assignments: dict[str, str] = {}

    def register_agent(self, agent: Agent) -> None:
        self.agents[agent.agent_id] = agent

    def assign_task(self, task: Task) -> str | None:
        existing_assignment = self._assignments.get(task.task_id)
        if existing_assignment is not None:
            return existing_assignment

        required = set(task.required_capabilities)
        candidates: list[tuple[str, float]] = []
        for agent_id, agent in self.agents.items():
            if not agent.can_accept_work or agent.available_capacity < task.estimated_load:
                continue

            capability_matches = len(required & set(agent.capabilities))
            if required and capability_matches == 0:
                continue
            capability_ratio = 1.0 if not required else capability_matches / len(required)
            remaining_ratio = 1 - agent.current_load / agent.max_load
            score = capability_ratio * agent.trust_score * remaining_ratio
            candidates.append((agent_id, score))

        if not candidates:
            return None

        candidates.sort(key=lambda candidate: candidate[1], reverse=True)
        best_id = candidates[0][0]
        self.agents[best_id].current_load += task.estimated_load
        self._assignments[task.task_id] = best_id
        return best_id

    def get_status(self) -> dict[str, int]:
        return {
            "agents": len(self.agents),
            "available": sum(1 for agent in self.agents.values() if agent.can_accept_work),
            "assignments": len(self._assignments),
        }


if __name__ == "__main__":
    coordinator = AgentCoordinator()
    coordinator.register_agent(Agent("a1", ["code", "review"], 0.3, 1.0))
    coordinator.register_agent(Agent("a2", ["data", "analysis"], 0.1, 1.0))
    coordinator.register_agent(Agent("a3", ["code", "deploy"], 0.5, 1.0))

    sample_task = Task("t1", ["code"], priority=1, estimated_load=0.3)
    assigned = coordinator.assign_task(sample_task)
    print(f"Task {sample_task.task_id} assigned to: {assigned}")
    print(json.dumps(coordinator.get_status(), indent=2))
