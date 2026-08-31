"""Deterministic bridge from scheduled assignments to reviewable tool proposals.

The coordinator still does not execute tools. This module emits a bounded,
hash-bound proposal batch whose individual call shape is compatible with the
Anthropic Safety Monitor ToolCall contract.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from .coordinator import CoordinationResult

PROPOSAL_SCHEMA = "glaciereq.agent-coordinator.tool-proposal-batch.v1"
MAX_PROPOSAL_ARGUMENT_BYTES = 65_536


class ToolProposalError(ValueError):
    """Raised when a proposed tool batch does not match the scheduled plan."""


@dataclass(frozen=True, slots=True)
class ToolProposal:
    task_id: str
    tool_name: str
    args: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        for name, value in (("task_id", self.task_id), ("tool_name", self.tool_name)):
            if not isinstance(value, str) or not value.strip():
                raise ToolProposalError(f"{name} must be non-empty text")
        if not isinstance(self.args, str):
            raise ToolProposalError("args must be text")
        if len(self.args.encode("utf-8")) > MAX_PROPOSAL_ARGUMENT_BYTES:
            raise ToolProposalError("args exceed bounded proposal size")
        if not isinstance(self.metadata, Mapping):
            raise ToolProposalError("metadata must be a string mapping")
        for key, value in self.metadata.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ToolProposalError("metadata keys and values must be text")

    def call_dict(self) -> dict[str, object]:
        self.validate()
        return {
            "name": self.tool_name.strip(),
            "args": self.args,
            "metadata": dict(sorted(self.metadata.items())),
        }


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def bind_tool_proposals(
    plan: CoordinationResult,
    proposals: list[ToolProposal],
) -> dict[str, object]:
    """Bind proposals only to fully assigned tasks and preserve assignment order."""

    assignment_order = {assignment.task_id: index for index, assignment in enumerate(plan.assignments)}
    assigned = set(assignment_order)
    deferred = {task.task_id for task in plan.deferred}
    by_task: dict[str, ToolProposal] = {}

    for proposal in proposals:
        proposal.validate()
        task_id = proposal.task_id.strip()
        if task_id in by_task:
            raise ToolProposalError("each task may have at most one tool proposal")
        if task_id in deferred or task_id not in assigned:
            raise ToolProposalError(
                f"tool proposal task {task_id!r} is not a fully assigned task"
            )
        by_task[task_id] = proposal

    ordered = sorted(by_task.values(), key=lambda item: assignment_order[item.task_id.strip()])
    plan_payload = plan.to_dict()
    body: dict[str, object] = {
        "schema": PROPOSAL_SCHEMA,
        "plan_sha256": _digest(plan_payload),
        "complete_plan": plan.complete,
        "proposal_count": len(ordered),
        "proposals": [
            {
                "task_id": proposal.task_id.strip(),
                "call": proposal.call_dict(),
            }
            for proposal in ordered
        ],
        "review_contract": "anthropic-safety-monitor.ToolCall-compatible",
        "tool_execution": False,
        "provider_calls": False,
    }
    body["receipt_sha256"] = _digest(body)
    return body
