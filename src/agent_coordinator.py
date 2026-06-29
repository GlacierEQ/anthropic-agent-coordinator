"""Anthropic Agent Coordinator — Multi-agent task allocation.

Their pain: Coordinating multiple agents without central control.

Innovation: Distributed task allocation with consensus-based assignment.
Agents self-organize based on capability matching and load balancing.
"""

import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Agent:
    agent_id: str
    capabilities: List[str]
    current_load: float
    max_load: float
    trust_score: float = 1.0

    @property
    def available_capacity(self) -> float:
        return max(0, self.max_load - self.current_load)

    @property
    def can_accept_work(self) -> bool:
        return self.available_capacity > 0.1


@dataclass
class Task:
    task_id: str
    required_capabilities: List[str]
    priority: int
    estimated_load: float


class AgentCoordinator:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self._assignments: Dict[str, str] = {}

    def register_agent(self, agent: Agent):
        self.agents[agent.agent_id] = agent

    def assign_task(self, task: Task) -> Optional[str]:
        candidates = []
        for agent_id, agent in self.agents.items():
            if not agent.can_accept_work:
                continue
            if agent.available_capacity < task.estimated_load:
                continue

            cap_match = len(set(task.required_capabilities) & set(agent.capabilities)) / max(len(task.required_capabilities), 1)
            score = cap_match * agent.trust_score * (1 - agent.current_load / agent.max_load)
            candidates.append((agent_id, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        best_id = candidates[0][0]
        self.agents[best_id].current_load += task.estimated_load
        self._assignments[task.task_id] = best_id
        return best_id

    def get_status(self) -> dict:
        return {
            "agents": len(self.agents),
            "available": sum(1 for a in self.agents.values() if a.can_accept_work),
            "assignments": len(self._assignments),
        }


if __name__ == "__main__":
    c = AgentCoordinator()
    c.register_agent(Agent("a1", ["code", "review"], 0.3, 1.0))
    c.register_agent(Agent("a2", ["data", "analysis"], 0.1, 1.0))
    c.register_agent(Agent("a3", ["code", "deploy"], 0.5, 1.0))

    task = Task("t1", ["code"], priority=1, estimated_load=0.3)
    assigned = c.assign_task(task)
    print(f"Task {task.task_id} assigned to: {assigned}")
    print(json.dumps(c.get_status(), indent=2))
