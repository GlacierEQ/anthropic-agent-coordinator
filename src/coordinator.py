#!/usr/bin/env python3
"""Multi-agent coordinator — portfolio motion (tool-use / agent OS problem space).

Assigns tasks to specialist roles with token budgets (AZOP-style waves).
"""
from __future__ import annotations

from dataclasses import dataclass, field

ANSWER = 42


@dataclass
class Task:
    id: str
    kind: str  # explore | plan | implement | review
    tokens_est: int
    deps: list[str] = field(default_factory=list)


ROLE_CAPS = {
    "explore": 4000,
    "plan": 3000,
    "implement": 8000,
    "review": 2500,
}


def coordinate(tasks: list[Task], global_budget: int = 12000) -> dict:
    assigned = []
    used = 0
    ready = {t.id for t in tasks if not t.deps}
    done = set()
    pending = {t.id: t for t in tasks}
    while pending and used < global_budget:
        progressed = False
        for tid in list(pending):
            t = pending[tid]
            if any(d not in done for d in t.deps):
                continue
            cap = ROLE_CAPS.get(t.kind, 2000)
            take = min(t.tokens_est, cap, global_budget - used)
            if take <= 0:
                continue
            assigned.append({"task": t.id, "role": t.kind, "tokens": take})
            used += take
            done.add(tid)
            del pending[tid]
            progressed = True
        if not progressed:
            break
    return {
        "assignments": assigned,
        "used_tokens": used,
        "deferred": list(pending.keys()),
        "answer": ANSWER,
    }


if __name__ == "__main__":
    tasks = [
        Task("d1", "explore", 3000),
        Task("p1", "plan", 2000, deps=["d1"]),
        Task("i1", "implement", 6000, deps=["p1"]),
        Task("r1", "review", 2000, deps=["i1"]),
    ]
    print(coordinate(tasks))
