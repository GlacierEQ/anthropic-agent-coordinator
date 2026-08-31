from __future__ import annotations

import pytest

from anthropic_agent_coordinator import Role, Task, build_plan
from anthropic_agent_coordinator.tool_proposal import (
    ToolProposal,
    ToolProposalError,
    bind_tool_proposals,
)


def test_assigned_tool_proposals_are_hash_bound_in_plan_order() -> None:
    plan = build_plan(
        (
            Task("discover", Role.EXPLORE, 100),
            Task("build", Role.IMPLEMENT, 100, deps=("discover",)),
        ),
        global_budget=500,
    )
    result = bind_tool_proposals(
        plan,
        [
            ToolProposal("build", "python", "-m pytest", {"scope": "repo"}),
            ToolProposal("discover", "git", "status --short", {"scope": "repo"}),
        ],
    )
    assert [row["task_id"] for row in result["proposals"]] == ["discover", "build"]
    assert result["proposals"][0]["call"] == {
        "name": "git",
        "args": "status --short",
        "metadata": {"scope": "repo"},
    }
    assert result["tool_execution"] is False
    assert result["provider_calls"] is False
    assert len(result["plan_sha256"]) == 64
    assert len(result["receipt_sha256"]) == 64
    assert result == bind_tool_proposals(
        plan,
        [
            ToolProposal("build", "python", "-m pytest", {"scope": "repo"}),
            ToolProposal("discover", "git", "status --short", {"scope": "repo"}),
        ],
    )


def test_deferred_task_cannot_emit_tool_proposal() -> None:
    plan = build_plan(
        (Task("oversized", Role.IMPLEMENT, 1_000),),
        global_budget=100,
    )
    with pytest.raises(ToolProposalError, match="not a fully assigned task"):
        bind_tool_proposals(plan, [ToolProposal("oversized", "bash", "echo no")])


def test_unknown_and_duplicate_proposals_fail_closed() -> None:
    plan = build_plan((Task("a", Role.EXPLORE, 100),), global_budget=500)
    with pytest.raises(ToolProposalError, match="not a fully assigned task"):
        bind_tool_proposals(plan, [ToolProposal("missing", "git", "status")])
    with pytest.raises(ToolProposalError, match="at most one"):
        bind_tool_proposals(
            plan,
            [
                ToolProposal("a", "git", "status"),
                ToolProposal("a", "git", "diff"),
            ],
        )


def test_non_string_metadata_and_oversized_args_fail_closed() -> None:
    plan = build_plan((Task("a", Role.EXPLORE, 100),), global_budget=500)
    with pytest.raises(ToolProposalError, match="metadata"):
        bind_tool_proposals(
            plan,
            [ToolProposal("a", "git", "status", {"attempt": 1})],  # type: ignore[dict-item]
        )
    with pytest.raises(ToolProposalError, match="bounded"):
        bind_tool_proposals(plan, [ToolProposal("a", "bash", "x" * 65_537)])
