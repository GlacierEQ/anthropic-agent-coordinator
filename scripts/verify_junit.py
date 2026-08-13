from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import os
import platform
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path
from typing import Final

RECEIPT_SCHEMA: Final = "glaciereq.agent-coordinator.test-receipt.v1"
MAX_JUNIT_BYTES: Final = 10 * 1024 * 1024
FORBIDDEN_XML_DECLARATIONS: Final = ("<!DOCTYPE", "<!ENTITY")
UNSUPPORTED_XML_BOMS: Final = (
    codecs.BOM_UTF16_LE,
    codecs.BOM_UTF16_BE,
    codecs.BOM_UTF32_LE,
    codecs.BOM_UTF32_BE,
)
COUNT_FIELDS: Final = ("tests", "failures", "errors", "skipped")


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
        for name in COUNT_FIELDS
    }


def _reconcile_counts(
    testcase_counts: dict[str, int],
    suite_counts: dict[str, int],
) -> None:
    mismatches = {
        field: {"testcases": testcase_counts[field], "suites": suite_counts[field]}
        for field in COUNT_FIELDS
        if testcase_counts[field] != suite_counts[field]
    }
    if mismatches:
        raise ValueError(
            "JUnit testcase outcomes do not match leaf-suite summaries: "
            + json.dumps(mismatches, sort_keys=True)
        )


def read_bounded_junit(path: Path) -> bytes:
    """Read at most the supported JUnit size, including concurrent-growth defense."""

    size = path.stat().st_size
    if size > MAX_JUNIT_BYTES:
        raise ValueError(
            f"JUnit artifact exceeds the {MAX_JUNIT_BYTES}-byte verification limit"
        )

    with path.open("rb") as handle:
        data = handle.read(MAX_JUNIT_BYTES + 1)
    if len(data) > MAX_JUNIT_BYTES:
        raise ValueError(
            f"JUnit artifact exceeds the {MAX_JUNIT_BYTES}-byte verification limit"
        )
    return data


def _decode_supported_xml(data: bytes) -> str:
    if data.startswith(UNSUPPORTED_XML_BOMS) or b"\x00" in data:
        raise ValueError("JUnit artifact must use UTF-8 XML encoding")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("JUnit artifact must use UTF-8 XML encoding") from exc

    normalized = text.upper()
    if any(declaration in normalized for declaration in FORBIDDEN_XML_DECLARATIONS):
        raise ValueError("JUnit artifact contains a forbidden DTD or entity declaration")
    return text


def parse_junit_bytes(data: bytes) -> dict[str, int]:
    if len(data) > MAX_JUNIT_BYTES:
        raise ValueError(
            f"JUnit artifact exceeds the {MAX_JUNIT_BYTES}-byte verification limit"
        )

    xml_text = _decode_supported_xml(data)
    root = ET.fromstring(xml_text)
    suite_counts = _counts_from_leaf_suites(root)
    testcase_counts = _counts_from_testcases(root)
    if testcase_counts is not None:
        _reconcile_counts(testcase_counts, suite_counts)
        counts = testcase_counts
    else:
        counts = suite_counts

    if counts["failures"] + counts["errors"] + counts["skipped"] > counts["tests"]:
        raise ValueError("JUnit outcome counts exceed the declared test count")
    counts["executed"] = counts["tests"] - counts["skipped"]
    return counts


def parse_junit(path: Path) -> dict[str, int]:
    return parse_junit_bytes(read_bounded_junit(path))


def current_repository_sha() -> str:
    """Return the exact checked-out Git commit or fail closed."""

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("cannot derive current repository SHA") from exc

    sha = completed.stdout.strip().lower()
    if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha):
        raise ValueError(f"invalid repository SHA returned by git: {sha!r}")
    return sha


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
    expected_sha: str | None = None,
) -> dict[str, object]:
    started_ns = time.time_ns()
    receipt: dict[str, object] = {
        "schema": RECEIPT_SCHEMA,
        "repository": "GlacierEQ/anthropic-agent-coordinator",
        "python": platform.python_version(),
        "pytest_exit_code": pytest_exit_code,
        "started_at_epoch_ns": started_ns,
    }

    try:
        repository_sha = current_repository_sha()
        receipt["commit"] = repository_sha
        if expected_sha is not None:
            normalized_expected = expected_sha.strip().lower()
            receipt["expected_commit"] = normalized_expected
            if repository_sha != normalized_expected:
                raise ValueError(
                    "repository SHA does not match expected verification SHA: "
                    f"actual={repository_sha} expected={normalized_expected}"
                )

        if not junit_path.is_file():
            raise FileNotFoundError(f"JUnit artifact does not exist: {junit_path}")
        junit_bytes = read_bounded_junit(junit_path)
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
        description="Convert a pytest JUnit artifact into an exact-SHA-bound atomic evidence receipt."
    )
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pytest-exit-code", type=int, required=True)
    parser.add_argument(
        "--expected-sha",
        required=True,
        help="Exact checked-out Git commit that the JUnit evidence must verify.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    receipt = verify_junit(
        args.junit,
        args.output,
        pytest_exit_code=args.pytest_exit_code,
        expected_sha=args.expected_sha,
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["conclusion"] == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
