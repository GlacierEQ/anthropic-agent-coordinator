from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Final

HEADINGS: Final = (
    "## For recruiters and non-technical reviewers",
    "## For senior engineers and domain experts",
    "## For AI systems and toolchains",
)
FILE_URL_PREFIX: Final = "file:" + "/" * 3
MAC_USER_PREFIX: Final = "/" + "Users" + "/"
LOCAL_PATH: Final = re.compile(
    "|".join(
        (
            re.escape(FILE_URL_PREFIX),
            re.escape(MAC_USER_PREFIX),
            r"[A-Za-z]:\\Users\\",
            r"/(?:home|root|tmp|var|private|mnt|opt)/[^\s)`\]}>]+",
            r"(?<![A-Za-z0-9_])~/[^\s)`\]}>]+",
        )
    ),
    re.IGNORECASE,
)
REQUIRED_EVIDENCE: Final = (
    ".github/workflows/ci.yml",
    "scripts/verify_junit.py",
    "glaciereq.agent-coordinator.test-receipt.v1",
    "blocked_scope:",
    "unverified_scope:",
    "relationships:",
)
FENCE_PATTERN: Final = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def _visible_markdown_lines(text: str) -> Iterator[tuple[int, str]]:
    fence_character: str | None = None
    fence_length = 0

    for line_number, line in enumerate(text.splitlines()):
        fence_match = FENCE_PATTERN.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence_character is None:
                fence_character = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_character and len(marker) >= fence_length:
                fence_character = None
                fence_length = 0
            continue
        if fence_character is None:
            yield line_number, line


def _heading_positions(text: str) -> tuple[dict[str, list[int]], tuple[str, ...]]:
    matches = {heading: [] for heading in HEADINGS}
    patterns = {
        heading: re.compile(rf"^{re.escape(heading)}(?:[ \t]+#+)?[ \t]*$")
        for heading in HEADINGS
    }

    for line_number, line in _visible_markdown_lines(text):
        for heading, pattern in patterns.items():
            if pattern.fullmatch(line):
                matches[heading].append(line_number)

    duplicates = tuple(heading for heading, positions in matches.items() if len(positions) > 1)
    return matches, duplicates


def verify_readme(path: Path) -> tuple[str, ...]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    positions_by_heading, duplicates = _heading_positions(text)

    missing = [heading for heading, positions in positions_by_heading.items() if not positions]
    if missing:
        errors.append(f"missing required audience headings: {missing}")
    if duplicates:
        errors.append(f"duplicate required audience headings: {list(duplicates)}")
    if not missing and not duplicates:
        positions = [positions_by_heading[heading][0] for heading in HEADINGS]
        if positions != sorted(positions):
            errors.append("audience headings are out of order")

    if LOCAL_PATH.search(text):
        errors.append("README exposes a machine-local path")

    missing_evidence = [value for value in REQUIRED_EVIDENCE if value not in text]
    if missing_evidence:
        errors.append(f"machine contract is incomplete: {missing_evidence}")
    return tuple(errors)


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    errors = verify_readme(repository_root / "README.md")
    if errors:
        raise SystemExit("README contract failed: " + "; ".join(errors))
    print("Agent Coordinator README contract verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
