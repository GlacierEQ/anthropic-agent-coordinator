from __future__ import annotations

import re
from pathlib import Path

HEADINGS = (
    "## For recruiters and non-technical reviewers",
    "## For senior engineers and domain experts",
    "## For AI systems and toolchains",
)
FILE_URL_PREFIX = "file:" + "/" * 3
MAC_USER_PREFIX = "/" + "Users" + "/"
LOCAL_PATH = re.compile(
    "|".join(
        (
            re.escape(FILE_URL_PREFIX),
            re.escape(MAC_USER_PREFIX),
            r"[A-Za-z]:\\Users\\",
        )
    )
)
REQUIRED_EVIDENCE = (
    ".github/workflows/ci.yml",
    "scripts/verify_junit.py",
    "glaciereq.agent-coordinator.test-receipt.v1",
    "blocked_scope:",
    "unverified_scope:",
    "relationships:",
)


def verify_readme(path: Path) -> tuple[str, ...]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    missing = [heading for heading in HEADINGS if heading not in text]
    if missing:
        errors.append(f"missing required audience headings: {missing}")
    else:
        positions = [text.index(heading) for heading in HEADINGS]
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
