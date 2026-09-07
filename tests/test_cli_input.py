from __future__ import annotations

import io
import json

from anthropic_agent_coordinator.__main__ import _load_tasks, _tasks_from_payload, main
from anthropic_agent_coordinator.coordinator import CoordinationError, Role


def test_tasks_from_payload_accepts_wrapped_graph() -> None:
    tasks = _tasks_from_payload(
        {
            "tasks": [
                {"id": "discover", "role": "explore", "tokens_est": 100},
                {
                    "id": "implement",
                    "role": "implement",
                    "tokens_est": 200,
                    "deps": ["discover"],
                },
            ]
        }
    )

    assert [task.id for task in tasks] == ["discover", "implement"]
    assert tasks[1].role is Role.IMPLEMENT
    assert tasks[1].deps == ("discover",)


def test_load_tasks_reads_stdin(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            json.dumps(
                [
                    {"id": "a", "role": "explore", "tokens_est": 100},
                    {"id": "b", "role": "plan", "tokens_est": 100, "deps": ["a"]},
                ]
            )
        ),
    )

    tasks = _load_tasks("-")
    assert [task.id for task in tasks] == ["a", "b"]


def test_main_executes_external_graph_with_continuation(tmp_path, capsys) -> None:
    graph = tmp_path / "graph.json"
    graph.write_text(
        json.dumps(
            {
                "tasks": [
                    {"id": "discover", "role": "explore", "tokens_est": 100},
                    {"id": "design", "role": "plan", "tokens_est": 100, "deps": ["discover"]},
                    {
                        "id": "implement",
                        "role": "implement",
                        "tokens_est": 200,
                        "deps": ["design"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["--input", str(graph), "--completed", "discover", "--budget", "300"])
    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert exit_code == 0
    assert result["completed_task_ids"] == ["discover"]
    assert [assignment["task"] for assignment in result["assignments"]] == ["design", "implement"]


def test_main_rejects_malformed_graph(tmp_path, capsys) -> None:
    graph = tmp_path / "graph.json"
    graph.write_text('{"tasks":[{"id":"x","role":"explore"}]}', encoding="utf-8")

    assert main(["--input", str(graph)]) == 2
    assert "missing required field 'tokens_est'" in capsys.readouterr().err


def test_tasks_from_payload_rejects_non_array() -> None:
    try:
        _tasks_from_payload({"tasks": "not-a-list"})
    except CoordinationError as exc:
        assert "task array" in str(exc)
    else:
        raise AssertionError("expected CoordinationError")
