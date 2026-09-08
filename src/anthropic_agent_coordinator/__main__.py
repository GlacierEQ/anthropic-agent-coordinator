from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from .continuation import build_continuation_plan
from .coordinator import CoordinationError, Role, Task, build_plan


def _demo_tasks() -> tuple[Task, ...]:
    return (
        Task("discover", Role.EXPLORE, 3_000),
        Task("design", Role.PLAN, 2_000, deps=("discover",)),
        Task("implement", Role.IMPLEMENT, 6_000, deps=("design",)),
        Task("review", Role.REVIEW, 1_000, deps=("implement",)),
    )


def _tasks_from_payload(payload: Any) -> tuple[Task, ...]:
    if isinstance(payload, dict):
        payload = payload.get("tasks")
    if not isinstance(payload, list):
        raise CoordinationError("input must be a JSON task array or an object containing a 'tasks' array")

    tasks: list[Task] = []
    for index, raw in enumerate(payload):
        if not isinstance(raw, dict):
            raise CoordinationError(f"task at index {index} must be an object")
        try:
            task_id = raw["id"]
            role = raw["role"]
            tokens_est = raw["tokens_est"]
        except KeyError as exc:
            raise CoordinationError(
                f"task at index {index} is missing required field {exc.args[0]!r}"
            ) from exc

        deps = raw.get("deps", ())
        tasks.append(Task(task_id, role, tokens_est, deps=deps))

    return tuple(tasks)


def _load_tasks(source: str | None) -> tuple[Task, ...]:
    if source is None:
        return _demo_tasks()

    try:
        if source == "-":
            payload = json.load(sys.stdin)
        else:
            with Path(source).open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise CoordinationError(f"unable to load task graph from {source!r}: {exc}") from exc

    return _tasks_from_payload(payload)


def _write_result(result: dict[str, Any], destination: str | None) -> None:
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if destination is None or destination == "-":
        sys.stdout.write(rendered)
        return

    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(rendered)
            temp_path = Path(handle.name)
        os.replace(temp_path, target)
    except OSError as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except UnboundLocalError:
            pass
        raise CoordinationError(f"unable to write coordination result to {destination!r}: {exc}") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic bounded agent coordination")
    parser.add_argument(
        "--input",
        metavar="PATH",
        help="JSON task graph file; use '-' to read JSON from stdin. Omit for the built-in demo graph.",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Atomically write the machine-readable coordination result to PATH; use '-' or omit for stdout.",
    )
    parser.add_argument(
        "--completed",
        action="append",
        default=[],
        metavar="TASK_ID",
        help="Resume from a dependency-closed completed task. Repeat for multiple tasks.",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=12_000,
        help="Token budget for work scheduled in this invocation (default: 12000).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        tasks = _load_tasks(args.input)
        if args.completed:
            result = build_continuation_plan(
                tasks,
                completed_task_ids=args.completed,
                global_budget=args.budget,
            ).to_dict()
        else:
            result = build_plan(tasks, global_budget=args.budget).to_dict()
        _write_result(result, args.output)
    except CoordinationError as exc:
        print(f"coordination failed: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
