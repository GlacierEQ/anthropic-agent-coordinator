from __future__ import annotations

import json
import sys

from .coordinator import CoordinationError, Role, Task, build_plan


def main() -> int:
    try:
        tasks = (
            Task("discover", Role.EXPLORE, 3_000),
            Task("design", Role.PLAN, 2_000, deps=("discover",)),
            Task("implement", Role.IMPLEMENT, 6_000, deps=("design",)),
            Task("review", Role.REVIEW, 1_000, deps=("implement",)),
        )
        result = build_plan(tasks)
    except CoordinationError as exc:
        print(f"coordination failed: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
