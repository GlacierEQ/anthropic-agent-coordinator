from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path
from typing import Final

RECEIPT_SCHEMA: Final = "glaciereq.agent-coordinator.test-receipt.v1"
MAX_JUNIT_BYTES: Final = 10 * 1024 * 1024
FORBIDDEN_XML_DECLARATIONS: Final = (b"<!DOCTYPE", b"<!ENTITY")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _integer_attribute(element: ET.Element, name: str) -> int:
    raw = element.attrib.get(name, "0")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"JUnit attribute {name!r} must be an integer, got {raw!r}") from exc
    if value < 0:
        raise ValueError(f"JUnit attribute {name!r} cannot be negative")
    return value


def _counts_from_testcases(root: ET.Element) -> dict[str, int] | None:
    testcases = [element for element in root.iter() if _local_name(element.tag) == "testcase"]
    if not testcases:
        return None

    counts = {"tests": len(testcases), "failures": 0, "errors": 0, "skipped": 0}
    for testcase in testcases:
        outcomes = {_local_name(child.tag) for child in testcase}
        if "failure" in outcomes:
            counts["failures"] += 1
        elif "error" in outcomes:
            counts["errors"] += 1
        elif "skipped" in outcomes:
            counts["skipped"] += 1
    return counts


def _counts_from_leaf_suites(root: ET.Element) -> dict[str, int]:
    suites = [element for element in root.iter() if _local_name(element.tag) == "testsuite"]
    leaf_suites = [
        suite
        for suite in suites
        if not any(_local_name(child.tag) == "testsuite" for child in suite)
    ]
    if not leaf_suites:
        raise ValueError("JUnit document contains no testsuite elements")

    return {
        name: sum(_integer_attribute(suite, name) for suite in leaf_suites)
        for name in ("tests", "failures", "errors", "skipped")
    }


def parse_junit_bytes(data: bytes) -> dict[str, int]:
    if len(data) > MAX_JUNIT_BYTES:
        raise ValueError(
            f"JUnit artifact exceeds the {MAX_JUNIT_BYTES}-byte verification limit"
        )
    normalized = data.upper()
    if any(declaration in normalized for declaration in FORBIDDEN_XML_DECLARATIONS):
        raise ValueError("JUnit artifact contains a forbidden DTD or entity declaration")

    root = ET.fromstring(data)
    counts = _counts_from_testcases(root) or _counts_from_leaf_suites(root)
    if counts["failures"] + counts["errors"] + counts["skipped"] > counts["tests"]:
        raise ValueError("JUnit outcome counts exceed the declared test count")
    counts["executed"] = counts["tests"] - counts["skipped"]
    return counts


def parse_junit(path: Path) -> dict[str, int]:
    return parse_junit_bytes(path.read_bytes())


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def verify_junit(
    junit_path: Path,
    output_path: Path,
    *,
    pytest_exit_code: int,
) -> dict[str, object]:
    started_ns = time.time_ns()
    receipt: dict[str, object] = {
        "schema": RECEIPT_SCHEMA,
        "repository": "GlacierEQ/anthropic-agent-coordinator",
        "commit": os.getenv("GITHUB_SHA", "LOCAL"),
        "python": platform.python_version(),
        "pytest_exit_code": pytest_exit_code,
        "started_at_epoch_ns": started_ns,
    }

    try:
        if not junit_path.is_file():
            raise FileNotFoundError(f"JUnit artifact does not exist: {junit_path}")
        junit_bytes = junit_path.read_bytes()
        counts = parse_junit_bytes(junit_bytes)
        receipt.update(counts)
        receipt["junit_sha256"] = hashlib.sha256(junit_bytes).hexdigest()

        if pytest_exit_code != 0 or counts["failures"] or counts["errors"]:
            receipt["conclusion"] = "FAILED"
            receipt["reason"] = "pytest or JUnit reported failed or errored tests"
        elif counts["executed"] <= 0:
            receipt["conclusion"] = "UNVERIFIED"
            receipt["reason"] = "pytest produced no executed, non-skipped tests"
        else:
            receipt["conclusion"] = "VERIFIED"
            receipt["evidence_level"] = "TEST"
    except (FileNotFoundError, OSError, ET.ParseError, ValueError) as exc:
        receipt.update(
            {
                "tests": 0,
                "executed": 0,
                "failures": 0,
                "errors": 1,
                "skipped": 0,
                "conclusion": "FAILED",
                "reason": str(exc),
                "error_type": type(exc).__name__,
            }
        )

    receipt["completed_at_epoch_ns"] = time.time_ns()
    atomic_write_json(output_path, receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a pytest JUnit artifact into an atomic evidence receipt."
    )
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pytest-exit-code", type=int, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    receipt = verify_junit(
        args.junit,
        args.output,
        pytest_exit_code=args.pytest_exit_code,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["conclusion"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
