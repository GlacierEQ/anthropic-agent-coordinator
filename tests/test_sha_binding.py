from __future__ import annotations

from pathlib import Path

from scripts.verify_junit import current_repository_sha, verify_junit


def write_success_junit(path: Path) -> None:
    path.write_text(
        '<testsuites><testsuite name="suite" tests="1" failures="0" errors="0" skipped="0"><testcase name="pass" /></testsuite></testsuites>',
        encoding="utf-8",
    )


def test_verification_receipt_binds_exact_checked_out_sha(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    write_success_junit(report)
    expected = current_repository_sha()
    receipt = verify_junit(
        report,
        tmp_path / "receipt.json",
        pytest_exit_code=0,
        expected_sha=expected,
    )
    assert receipt["conclusion"] == "VERIFIED"
    assert receipt["commit"] == expected
    assert receipt["expected_commit"] == expected


def test_verification_receipt_fails_closed_on_sha_mismatch(tmp_path: Path) -> None:
    report = tmp_path / "report.xml"
    write_success_junit(report)
    receipt = verify_junit(
        report,
        tmp_path / "receipt.json",
        pytest_exit_code=0,
        expected_sha="0" * 40,
    )
    assert receipt["conclusion"] == "FAILED"
    assert receipt["error_type"] == "ValueError"
    assert "repository SHA does not match expected verification SHA" in receipt["reason"]
