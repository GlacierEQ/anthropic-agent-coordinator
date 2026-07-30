from __future__ import annotations

import json

from .coordinator import Role, Task, build_plan


def main() -> int:
    tasks = (
        Task("discover", Role.EXPLORE, 3_000),
        Task("design", Role.PLAN, 2_000, deps=("discover",)),
        Task("implement", Role.IMPLEMENT, 6_000, deps=("design",)),
        Task("review", Role.REVIEW, 1_000, deps=("implement",)),
    )
    print(json.dumps(build_plan(tasks).to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
