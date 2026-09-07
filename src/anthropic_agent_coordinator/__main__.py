from __future__ import annotations

import argparse
import json
import sys

from .continuation import build_continuation_plan
from .coordinator import CoordinationError, Role, Task, build_plan


def _demo_tasks() -> tuple[Task, ...]:
    return (
        Task("discover", Role.EXPLORE, 3_000),
        Task("design", Role.PLAN, 2_000, deps=("discover",)),
        Task("implement", Role.IMPLEMENT, 6_000, deps=("design",)),
        Task("review", Role.REVIEW, 1_000, deps=("implement",)),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic bounded agent coordination demo")
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
        tasks = _demo_tasks()
        if args.completed:
            result = build_continuation_plan(
                tasks,
                completed_task_ids=args.completed,
                global_budget=args.budget,
            ).to_dict()
        else:
            result = build_plan(tasks, global_budget=args.budget).to_dict()
    except CoordinationError as exc:
        print(f"coordination failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
