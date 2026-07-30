from __future__ import annotations

import json
from pathlib import Path

from scripts.verify_junit import (
    MAX_JUNIT_BYTES,
    atomic_write_json,
    parse_junit,
    verify_junit,
)
from scripts.verify_readme_contract import HEADINGS, REQUIRED_EVIDENCE, verify_readme


def write_junit(
    path: Path,
    *,
    tests: int,
    failures: int = 0,
    errors: int = 0,
    skipped: int = 0,
) -> None:
    path.write_text(
        (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<testsuites><testsuite name="suite" tests="{tests}" '
            f'failures="{failures}" errors="{errors}" skipped="{skipped}" />'
            "</testsuites>"
        ),
        encoding="utf-8",
    )


def test_parse_junit_aggregates_direct_suites(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    report.write_text(
        (
            "<testsuites>"
            '<testsuite tests="2" failures="0" errors="0" skipped="1" />'
            '<testsuite tests="3" failures="1" errors="0" skipped="0" />'
            "</testsuites>"
        ),
        encoding="utf-8",
    )
    assert parse_junit(report) == {
        "tests": 5,
        "executed": 4,
        "failures": 1,
        "errors": 0,
        "skipped": 1,
    }


def test_nested_junit_counts_each_testcase_once(tmp_path: Path) -> None:
    report = tmp_path / "nested.xml"
    report.write_text(
        (
            '<testsuites tests="3" failures="1" errors="0" skipped="1">'
            '<testsuite name="parent" tests="3" failures="1" errors="0" skipped="1">'
            '<testsuite name="child-a" tests="2" failures="0" errors="0" skipped="1">'
            '<testcase name="pass" />'
            '<testcase name="skip"><skipped /></testcase>'
            "</testsuite>"
            '<testsuite name="child-b" tests="1" failures="1" errors="0" skipped="0">'
            '<testcase name="fail"><failure /></testcase>'
            "</testsuite>"
            "</testsuite>"
            "</testsuites>"
        ),
        encoding="utf-8",
    )
    assert parse_junit(report) == {
        "tests": 3,
        "executed": 2,
        "failures": 1,
        "errors": 0,
        "skipped": 1,
    }


def test_junit_rejects_suite_and_testcase_count_mismatch(tmp_path: Path) -> None:
    report = tmp_path / "mismatch.xml"
    report.write_text(
        (
            '<testsuite name="suite" tests="2" failures="0" errors="0" skipped="0">'
            '<testcase name="only-case" />'
            "</testsuite>"
        ),
        encoding="utf-8",
    )
    receipt = verify_junit(report, tmp_path / "receipt.json", pytest_exit_code=0)
    assert receipt["conclusion"] == "FAILED"
    assert receipt["error_type"] == "ValueError"
    assert "do not match leaf-suite summaries" in receipt["reason"]


def test_verified_junit_writes_positive_count_receipt(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    receipt_path = tmp_path / "receipt.json"
    write_junit(report, tests=7, skipped=1)
    receipt = verify_junit(report, receipt_path, pytest_exit_code=0)
    assert receipt["conclusion"] == "VERIFIED"
    assert receipt["evidence_level"] == "TEST"
    assert receipt["tests"] == 7
    assert receipt["executed"] == 6
    assert receipt["skipped"] == 1
    assert len(receipt["junit_sha256"]) == 64
    assert json.loads(receipt_path.read_text(encoding="utf-8")) == receipt


def test_zero_test_junit_remains_unverified(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    receipt_path = tmp_path / "receipt.json"
    write_junit(report, tests=0)
    receipt = verify_junit(report, receipt_path, pytest_exit_code=0)
    assert receipt["conclusion"] == "UNVERIFIED"
    assert receipt["tests"] == 0
    assert receipt["executed"] == 0


def test_all_skipped_junit_does_not_establish_test_evidence(tmp_path: Path) -> None:
    report = tmp_path / "skipped.xml"
    receipt_path = tmp_path / "receipt.json"
    write_junit(report, tests=4, skipped=4)
    receipt = verify_junit(report, receipt_path, pytest_exit_code=0)
    assert receipt["conclusion"] == "UNVERIFIED"
    assert receipt["tests"] == 4
    assert receipt["executed"] == 0


def test_pytest_or_junit_failure_produces_failed_receipt(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    receipt_path = tmp_path / "receipt.json"
    write_junit(report, tests=2, failures=1)
    receipt = verify_junit(report, receipt_path, pytest_exit_code=1)
    assert receipt["conclusion"] == "FAILED"
    assert receipt["failures"] == 1


def test_missing_or_invalid_junit_still_writes_failed_evidence(tmp_path: Path) -> None:
    missing = tmp_path / "missing.xml"
    missing_receipt = tmp_path / "missing-receipt.json"
    missing_result = verify_junit(missing, missing_receipt, pytest_exit_code=2)
    assert missing_result["conclusion"] == "FAILED"
    assert missing_receipt.is_file()

    invalid = tmp_path / "invalid.xml"
    invalid.write_text("not xml", encoding="utf-8")
    invalid_receipt = tmp_path / "invalid-receipt.json"
    invalid_result = verify_junit(invalid, invalid_receipt, pytest_exit_code=2)
    assert invalid_result["conclusion"] == "FAILED"
    assert invalid_result["error_type"] == "ParseError"


def test_entity_bearing_junit_is_rejected_before_xml_parsing(tmp_path: Path) -> None:
    report = tmp_path / "entity.xml"
    report.write_text(
        (
            '<?xml version="1.0"?>'
            '<!DOCTYPE testsuites [<!ENTITY expansion "expanded">]>'
            '<testsuites><testsuite name="&expansion;" tests="1" '
            'failures="0" errors="0" skipped="0" /></testsuites>'
        ),
        encoding="utf-8",
    )
    receipt = verify_junit(report, tmp_path / "receipt.json", pytest_exit_code=0)
    assert receipt["conclusion"] == "FAILED"
    assert receipt["error_type"] == "ValueError"
    assert "forbidden DTD or entity declaration" in receipt["reason"]


def test_oversized_junit_is_rejected_before_xml_parsing(tmp_path: Path) -> None:
    report = tmp_path / "oversized.xml"
    report.write_bytes(b" " * (MAX_JUNIT_BYTES + 1))
    receipt = verify_junit(report, tmp_path / "receipt.json", pytest_exit_code=0)
    assert receipt["conclusion"] == "FAILED"
    assert receipt["error_type"] == "ValueError"
    assert "verification limit" in receipt["reason"]


def test_atomic_write_replaces_stale_success(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    atomic_write_json(receipt, {"conclusion": "VERIFIED"})
    atomic_write_json(receipt, {"conclusion": "FAILED"})
    assert json.loads(receipt.read_text(encoding="utf-8")) == {"conclusion": "FAILED"}
    assert list(tmp_path.glob(".receipt.json.*.tmp")) == []


def valid_readme() -> str:
    return "\n".join((*HEADINGS, *REQUIRED_EVIDENCE)) + "\n"


def test_readme_contract_accepts_portable_ordered_document(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(valid_readme(), encoding="utf-8")
    assert verify_readme(readme) == ()


def test_readme_contract_rejects_wrong_order_and_local_paths(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    windows_path = "C:" + "\\" + "Users" + "\\" + "casey" + "\\repo"
    readme.write_text(
        "\n".join(
            (*reversed(HEADINGS), *REQUIRED_EVIDENCE, windows_path, "/home/casey/repo")
        )
        + "\n",
        encoding="utf-8",
    )
    errors = verify_readme(readme)
    assert "audience headings are out of order" in errors
    assert "README exposes a machine-local path" in errors


def test_headings_inside_fenced_code_do_not_satisfy_contract(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "\n".join(("```markdown", *HEADINGS, "```", *REQUIRED_EVIDENCE)) + "\n",
        encoding="utf-8",
    )
    errors = verify_readme(readme)
    assert any(error.startswith("missing required audience headings") for error in errors)
